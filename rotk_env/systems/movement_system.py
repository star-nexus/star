"""
Movement System - movement domain API with orthogonal planning and execution.

Normal benchmark/gameplay keeps calling ``move_unit``. That compatibility facade
performs ``plan_move`` followed immediately by ``execute_move_plan`` and therefore
preserves the existing one-shot legality semantics. Scale/debug tooling may call
the two phases independently without duplicating movement rules.

Movement invariants remain:
- normal destinations must be unoccupied;
- enemy-held traversal cells are blocked while friendly-held cells are transparent;
- legality is judged once at planning/admission time and is not revalidated while
  an accepted path is executing;
- HexPosition is authoritative occupancy state.
"""

from __future__ import annotations

from typing import AbstractSet, Any, Dict, List, Mapping, Optional, Set, Tuple

from framework import System, World
from framework.ecs import profiling

from ..components import (
    HexPosition,
    MovementPoints,
    Unit,
    UnitCount,
    MovementAnimation,
    UnitStatus,
)
from ..prefabs.config import Faction, TerrainType, UnitState
from ..utils.hex_utils import HexMath, PathFinding
from .movement_planning import (
    EndpointUnblockedObstacles,
    MovePlan,
    MovementPlanResult,
    MovementPlanningPolicy,
    MovementPlanningSnapshot,
)
from .resource_recovery_system import mark_movement_points_spent

Hex = Tuple[int, int]


class MovementSystem(System):
    """Movement domain service: pure planning plus side-effecting execution."""

    def __init__(self):
        super().__init__(required_components={HexPosition, MovementPoints, Unit})

    def initialize(self, world: World) -> None:
        self.world = world

    def subscribe_events(self):
        pass

    def update(self, delta_time: float) -> None:
        """Movement is command driven; ongoing visual motion lives in AnimationSystem."""
        pass

    # ------------------------------------------------------------------
    # Public domain API
    # ------------------------------------------------------------------
    def move_unit(self, entity: int, target_pos: Hex) -> Dict[str, Any]:
        """Normal ENV facade: plan once, then execute immediately.

        This is intentionally the same API existing callers use. Stress/scale
        tooling should use ``plan_move`` and ``execute_move_plan`` separately.
        """
        planned = self.plan_move(entity, target_pos)
        if not planned.success or planned.plan is None:
            return planned.response
        return self.execute_move_plan(planned.plan)

    def plan_move(
        self,
        entity: int,
        target_pos: Hex,
        *,
        policy: MovementPlanningPolicy | str = MovementPlanningPolicy.NORMAL,
        snapshot: Optional[MovementPlanningSnapshot] = None,
        correct_to_budget: bool = False,
    ) -> MovementPlanResult:
        """Pure movement planning: inspect state and return a MovePlan.

        No resources are spent and no world/animation/statistics state is changed.
        ``correct_to_budget`` is a planning-tool feature: when a requested target
        is reachable by route but exceeds the unit's current budget, resolve the
        plan to the farthest legal endpoint on that same route within budget.
        Normal ``move_unit`` leaves it False, preserving the existing
        ``insufficient_mp`` rejection contract.
        """
        policy = MovementPlanningPolicy.coerce(policy)

        position = self.world.get_component(entity, HexPosition)
        movement_points = self.world.get_component(entity, MovementPoints)
        unit_count = self.world.get_component(entity, UnitCount)
        unit = self.world.get_component(entity, Unit)

        missing = []
        if not position:
            missing.append("HexPosition")
        if not movement_points:
            missing.append("MovementPoints")
        if not unit_count:
            missing.append("UnitCount")
        if not unit:
            missing.append("Unit")
        if missing:
            return MovementPlanResult.rejected(
                {
                    "success": False,
                    "reason": "missing_components",
                    "message": f"Unit {entity} missing required components: {', '.join(missing)}",
                    "unit_id": entity,
                    "missing_components": missing,
                }
            )

        anim = self.world.get_component(entity, MovementAnimation)
        if anim and anim.is_moving:
            return MovementPlanResult.rejected(
                {
                    "success": False,
                    "reason": "already_moving",
                    "message": f"Unit {entity} is already moving",
                    "unit_id": entity,
                }
            )

        unit_status = self.world.get_component(entity, UnitStatus)
        if unit_status is not None:
            status = unit_status.current_status
            confused = status == UnitState.CONFUSION or status == UnitState.CONFUSION.value
            if confused:
                return MovementPlanResult.rejected(
                    {
                        "success": False,
                        "reason": "confused",
                        "message": f"Unit {entity} is confused and cannot move",
                        "unit_id": entity,
                        "current_status": (
                            status.value if hasattr(status, "value") else status
                        ),
                        "blocking_statuses": [UnitState.CONFUSION.value],
                        "suggestion": "Wait for confusion to clear or use skill to remove it",
                    }
                )

        current_mp = movement_points.current_mp
        current_pos = (position.col, position.row)
        if current_mp <= 0:
            return MovementPlanResult.rejected(
                {
                    "success": False,
                    "reason": "no_mp",
                    "message": f"Unit has no movement points left: {current_mp}",
                    "unit_id": entity,
                    "current_movement_points": current_mp,
                    "suggestion": "Use end_turn tool or wait for movement points to recover",
                }
            )

        effective_movement = movement_points.get_effective_movement(unit_count)
        spendable = movement_points.spendable(unit_count)
        occupied, blockers, costs, walkable, planning_revision = self._planning_context(
            entity, unit.faction, snapshot
        )

        if policy == MovementPlanningPolicy.NORMAL and target_pos in occupied:
            return MovementPlanResult.rejected(
                self._destination_occupied_result(entity, current_pos, target_pos)
            )

        # Stress stacking changes only endpoint legality. Enemy traversal remains
        # blocked everywhere else; remove only the requested endpoint from the
        # blocker set so a planner may route *to* an enemy-held cell, never
        # through arbitrary enemy-held cells.
        path_blockers = blockers
        if policy == MovementPlanningPolicy.STRESS_STACK_ENDPOINT:
            path_blockers = EndpointUnblockedObstacles(blockers, target_pos)

        with profiling.profiler.time_system("move_pathfinding", category="input"):
            path = PathFinding.find_path(
                current_pos,
                target_pos,
                path_blockers,
                None,
                walkable=walkable,
                step_cost=lambda pos: costs.get(pos, 999),
            )
        if not path or len(path) < 2:
            diagnostic_blockers = self._diagnostic_blockers(
                blockers, target_pos, policy
            )
            return MovementPlanResult.rejected(
                self._no_path_result(
                    entity,
                    current_pos,
                    target_pos,
                    effective_movement,
                    path,
                    blockers=diagnostic_blockers,
                    occupied=set(occupied),
                )
            )

        total_cost = self._path_cost(path, costs)
        resolved_target = target_pos
        resolved_path = list(path)
        resolved_cost = total_cost
        corrected = False

        if total_cost > spendable:
            if not correct_to_budget:
                return MovementPlanResult.rejected(
                    self._insufficient_mp_result(
                        entity,
                        current_pos,
                        target_pos,
                        path,
                        effective_movement,
                        total_cost,
                        current_mp,
                        spendable,
                        blockers=self._diagnostic_blockers(
                            blockers, target_pos, policy
                        ),
                        occupied=set(occupied),
                    )
                )

            corrected_path, corrected_cost = self._trim_path_to_budget(
                path,
                spendable,
                occupied=occupied,
                policy=policy,
                costs=costs,
            )
            if not corrected_path or len(corrected_path) < 2:
                return MovementPlanResult.rejected(
                    self._insufficient_mp_result(
                        entity,
                        current_pos,
                        target_pos,
                        path,
                        effective_movement,
                        total_cost,
                        current_mp,
                        spendable,
                        blockers=self._diagnostic_blockers(
                            blockers, target_pos, policy
                        ),
                        occupied=set(occupied),
                    )
                )
            resolved_path = corrected_path
            resolved_target = corrected_path[-1]
            resolved_cost = corrected_cost
            corrected = resolved_target != target_pos

        plan = MovePlan(
            entity=entity,
            start=current_pos,
            requested_target=target_pos,
            resolved_target=resolved_target,
            path=tuple(resolved_path),
            cost=resolved_cost,
            spendable_at_plan=spendable,
            policy=policy,
            corrected=corrected,
            planning_revision=planning_revision,
        )
        return MovementPlanResult.accepted(plan)

    def execute_move_plan(
        self,
        plan: MovePlan,
        *,
        emit_log: bool = True,
    ) -> Dict[str, Any]:
        """Execute an already-approved plan without re-running pathfinding.

        The executor verifies only that the plan still belongs to this unit/start
        and that the unit still has enough movement budget. It deliberately does
        not re-run occupancy/path legality: normal immediate moves retain the old
        admission-once semantics, while prepared scale batches remain separable
        from planning cost.
        """
        entity = plan.entity
        position = self.world.get_component(entity, HexPosition)
        movement_points = self.world.get_component(entity, MovementPoints)
        unit_count = self.world.get_component(entity, UnitCount)
        if position is None or movement_points is None or unit_count is None:
            return {
                "success": False,
                "reason": "stale_move_plan",
                "message": f"Unit {entity} no longer has the components required by its move plan",
                "unit_id": entity,
            }

        current_pos = (position.col, position.row)
        if current_pos != plan.start:
            return {
                "success": False,
                "reason": "stale_move_plan",
                "message": (
                    f"Unit {entity} moved since planning: expected {plan.start}, "
                    f"found {current_pos}"
                ),
                "unit_id": entity,
                "planned_from": plan.start,
                "current_position": current_pos,
            }

        anim = self.world.get_component(entity, MovementAnimation)
        if anim and anim.is_moving:
            return {
                "success": False,
                "reason": "already_moving",
                "message": f"Unit {entity} is already moving",
                "unit_id": entity,
            }

        spendable = movement_points.spendable(unit_count)
        if plan.cost > spendable:
            return {
                "success": False,
                "reason": "stale_move_plan_resources",
                "message": (
                    f"Move plan costs {plan.cost} MP but unit {entity} now has "
                    f"only {spendable} spendable MP"
                ),
                "unit_id": entity,
                "required_movement_points": plan.cost,
                "current_movement_points": movement_points.current_mp,
            }

        if emit_log:
            print(f"✓ Unit {entity} moves to {plan.resolved_target}")

        # Preserve the existing move contract: spending a path budget did not
        # toggle MovementPoints.has_moved in this system.
        movement_points.current_mp -= plan.cost
        mark_movement_points_spent(self.world, entity)

        statistics_system = self._get_statistics_system()
        if statistics_system:
            statistics_system.record_movement_action(
                entity, plan.start, plan.resolved_target
            )

        path = list(plan.path)
        animation_system = self._get_animation_system()
        animated = False
        if animation_system:
            animation_system.start_unit_movement(entity, path)
            animated = True
        else:
            self.commit_hex_position(
                entity,
                plan.resolved_target[0],
                plan.resolved_target[1],
                arrived=True,
            )

        return {
            "success": True,
            "path": path,
            "cost": plan.cost,
            "from": plan.start,
            "to": plan.resolved_target,
            "animated": animated,
        }

    def build_planning_snapshot(self) -> MovementPlanningSnapshot:
        """Capture shared planning inputs once for a batch.

        Window-scale MovementSystem overrides this with the maintained spatial
        index; the base implementation still avoids N repeated occupancy scans
        for headless/testing batch planners.
        """
        from ..utils.map_query import (
            board_hexes,
            impassable_terrain,
            movement_costs,
            unit_cells,
        )

        cells = unit_cells(self.world)
        occupied = frozenset(cells)
        impassable = frozenset(impassable_terrain(self.world))
        blockers_by_faction = {}
        for faction in (Faction.WEI, Faction.SHU, Faction.WU):
            enemy = {
                cell
                for cell, factions in cells.items()
                if any(other != faction for other in factions)
            }
            blockers_by_faction[faction] = frozenset(set(impassable) | enemy)
        board = board_hexes(self.world)
        return MovementPlanningSnapshot(
            walkable=frozenset(board) if board is not None else None,
            terrain_costs=movement_costs(self.world),
            occupied=occupied,
            blockers_by_faction=blockers_by_faction,
            revision=getattr(self.world, "revision", None),
        )

    # ------------------------------------------------------------------
    # Planning internals / override points
    # ------------------------------------------------------------------
    def _planning_context(
        self,
        entity: int,
        faction: Optional[Faction],
        snapshot: Optional[MovementPlanningSnapshot],
    ) -> tuple[
        AbstractSet[Hex],
        AbstractSet[Hex],
        Mapping[Hex, int],
        Optional[AbstractSet[Hex]],
        Optional[int],
    ]:
        if snapshot is not None:
            return (
                snapshot.occupied,
                snapshot.blockers_for(faction),
                snapshot.terrain_costs,
                snapshot.walkable,
                snapshot.revision,
            )

        from ..utils.map_query import (
            board_hexes,
            movement_costs,
            occupied_cells,
            path_blockers,
        )

        occupied = occupied_cells(self.world, exclude_entity=entity)
        blockers = path_blockers(
            self.world, faction=faction, exclude_entity=entity
        )
        costs = movement_costs(self.world)
        walkable = board_hexes(self.world)
        return (
            occupied,
            blockers,
            costs,
            set(walkable) if walkable is not None else None,
            getattr(self.world, "revision", None),
        )

    def _path_cost(self, path: List[Hex], costs: Mapping[Hex, int]) -> int:
        total = 0
        for pos in path[1:]:
            if pos in costs:
                total += int(costs[pos])
            else:
                total += self._get_terrain_movement_cost(pos)
        return total

    def _trim_path_to_budget(
        self,
        path: List[Hex],
        spendable: int,
        *,
        occupied: AbstractSet[Hex],
        policy: MovementPlanningPolicy,
        costs: Mapping[Hex, int],
    ) -> tuple[Optional[List[Hex]], int]:
        """Return the farthest affordable legal endpoint on an existing path."""
        cumulative = 0
        best_index = 0
        best_cost = 0
        for index, pos in enumerate(path[1:], start=1):
            step_cost = int(costs[pos]) if pos in costs else self._get_terrain_movement_cost(pos)
            if cumulative + step_cost > spendable:
                break
            cumulative += step_cost
            endpoint_legal = (
                policy == MovementPlanningPolicy.STRESS_STACK_ENDPOINT
                or pos not in occupied
            )
            if endpoint_legal:
                best_index = index
                best_cost = cumulative

        if best_index <= 0:
            return None, 0
        return list(path[: best_index + 1]), best_cost

    # ------------------------------------------------------------------
    # World mutation / diagnostics helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _diagnostic_blockers(
        blockers: AbstractSet[Hex],
        target_pos: Hex,
        policy: MovementPlanningPolicy,
    ) -> Set[Hex]:
        materialized = set(blockers)
        if policy == MovementPlanningPolicy.STRESS_STACK_ENDPOINT:
            materialized.discard(target_pos)
        return materialized

    def commit_hex_position(
        self, entity: int, col: int, row: int, *, arrived: bool = False
    ) -> None:
        """Write the unit's committed hex. HexPosition is the occupancy truth."""
        position = self.world.get_component(entity, HexPosition)
        if position is not None:
            position.col, position.row = col, row
        if arrived:
            self._trigger_terrain_events(entity, "move_end")

    def _destination_occupied_result(
        self,
        entity: int,
        current_pos: Hex,
        target_pos: Hex,
    ) -> Dict[str, Any]:
        return {
            "success": False,
            "reason": "destination_occupied",
            "message": f"Target position {target_pos} is already occupied by a unit",
            "unit_id": entity,
            "start_position": current_pos,
            "target_position": target_pos,
            "suggestion": (
                "Pick an unoccupied hex; this unit's reachable list only "
                "contains hexes that were free when it was computed"
            ),
        }

    def _no_path_result(
        self,
        entity: int,
        current_pos: Hex,
        target_pos: Hex,
        effective_movement: int,
        path: Optional[List[Hex]],
        *,
        blockers: Optional[Set[Hex]] = None,
        occupied: Optional[Set[Hex]] = None,
    ) -> Dict[str, Any]:
        blockers = blockers if blockers is not None else self._get_obstacles(exclude_entity=entity)
        occupied = occupied if occupied is not None else self._occupied(entity)
        hex_distance = HexMath.hex_distance(current_pos, target_pos)
        distance_issue = hex_distance > effective_movement
        target_blocked = target_pos in blockers
        adjacent_free = self._adjacent_free(current_pos, blockers | occupied)
        return {
            "success": False,
            "reason": "no_path",
            "message": f"No valid path to target position {target_pos}",
            "unit_id": entity,
            "start_position": current_pos,
            "target_position": target_pos,
            "effective_movement": effective_movement,
            "hex_distance": hex_distance,
            "distance_exceeds_range": distance_issue,
            "target_blocked": target_blocked,
            "path_found": bool(path),
            "path_length": len(path) if path else 0,
            "adjacent_free_positions": adjacent_free,
            "possible_causes": [
                c
                for c in (
                    "Target position out of movement range" if distance_issue else None,
                    "Target position blocked by obstacles" if target_blocked else None,
                    "No valid route exists",
                )
                if c
            ],
            "suggestion": (
                f"Try one of these nearby positions: {adjacent_free[:3]}"
                if adjacent_free
                else "No adjacent free positions available"
            ),
        }

    def _insufficient_mp_result(
        self,
        entity: int,
        current_pos: Hex,
        target_pos: Hex,
        path: List[Hex],
        effective_movement: int,
        total_cost: int,
        current_mp: int,
        spendable: int,
        *,
        blockers: Optional[Set[Hex]] = None,
        occupied: Optional[Set[Hex]] = None,
    ) -> Dict[str, Any]:
        occupied = occupied if occupied is not None else self._occupied(entity)
        cumulative_cost = 0
        reachable_along_path = []
        for pos in path[1:]:
            step_cost = self._get_terrain_movement_cost(pos)
            if cumulative_cost + step_cost > spendable:
                break
            cumulative_cost += step_cost
            if pos not in occupied:
                reachable_along_path.append(pos)
        closest = reachable_along_path[-1] if reachable_along_path else current_pos

        blockers = blockers if blockers is not None else self._get_obstacles(exclude_entity=entity)
        blocked = blockers | occupied
        nearby = []
        for cand in self._adjacent_free(current_pos, blocked):
            if self._get_terrain_movement_cost(cand) <= spendable:
                nearby.append((HexMath.hex_distance(cand, target_pos), cand))
        nearby.sort(key=lambda x: x[0])
        nearby_positions = [c for _, c in nearby[:3]]

        farthest = {"col": closest[0], "row": closest[1]}
        if closest != current_pos:
            suggestion = f"Try moving to the farthest hex on this path this turn: {closest}"
            suggested_target = closest
        elif nearby_positions:
            suggestion = (
                "No step along the path is reachable this turn. "
                f"Try one of these nearby positions: {nearby_positions}"
            )
            suggested_target = nearby_positions[0]
        else:
            suggestion = "No nearby reachable positions this turn. Wait to recover movement points."
            suggested_target = None

        payload = {
            "success": False,
            "reason": "insufficient_mp",
            "failure_reason": "insufficient_movement_points",
            "message": (
                f"Shortest path costs {total_cost} MP; unit has {spendable} MP. "
                f"Farthest reachable hex along this path: ({closest[0]}, {closest[1]})."
            ),
            "unit_id": entity,
            "required_movement_points": total_cost,
            "current_movement_points": current_mp,
            "deficit": total_cost - spendable,
            "path": [[col, row] for col, row in path],
            "path_length": len(path) - 1,
            "effective_movement": effective_movement,
            "terrain_costs": self._path_terrain_breakdown(path),
            "closest_reachable_position": farthest,
            "farthest_reachable_on_path": farthest,
            "reachable_steps": len(reachable_along_path),
            "nearby_reachable_positions": [
                {"col": p[0], "row": p[1]} for p in nearby_positions
            ],
            "suggestion": suggestion,
        }
        if suggested_target is not None:
            payload["suggested_action"] = {
                "action": "move",
                "params": {
                    "unit_id": entity,
                    "target_position": {
                        "col": suggested_target[0],
                        "row": suggested_target[1],
                    },
                },
            }
        return payload

    def _adjacent_free(self, center: Hex, blocked: Set[Hex]) -> List[Hex]:
        from ..utils.map_query import board_hexes

        walkable = board_hexes(self.world)
        return [
            n
            for n in HexMath.hex_neighbors(*center)
            if n not in blocked and (walkable is None or n in walkable)
        ]

    def _path_terrain_breakdown(self, path: List[Hex]) -> List[Dict[str, Any]]:
        breakdown = []
        for i, pos in enumerate(path):
            if i == 0:
                continue
            terrain_type = self._get_terrain_at_position(pos)
            breakdown.append(
                {
                    "position": {"col": pos[0], "row": pos[1]},
                    "terrain": terrain_type.value,
                    "movement_cost": self._get_terrain_movement_cost(pos),
                    "step": i,
                }
            )
        return breakdown

    def _calculate_total_movement_cost(self, path: list) -> int:
        total_cost = 0
        for i in range(1, len(path)):
            total_cost += self._get_terrain_movement_cost(path[i])
        return total_cost

    def _get_terrain_movement_cost(self, position: Hex) -> int:
        from ..components.terrain import movement_cost_at

        return movement_cost_at(self.world, position)

    def _get_terrain_at_position(self, position: Hex) -> TerrainType:
        from ..components.terrain import terrain_at

        terrain = terrain_at(self.world, position)
        return terrain.terrain_type if terrain else TerrainType.PLAIN

    def _get_obstacles(self, exclude_entity: Optional[int] = None) -> Set[Hex]:
        from ..utils.map_query import faction_of, path_blockers

        return path_blockers(
            self.world,
            faction_of(self.world, exclude_entity),
            exclude_entity=exclude_entity,
        )

    def _occupied(self, exclude_entity: Optional[int] = None) -> Set[Hex]:
        from ..utils.map_query import occupied_cells

        return occupied_cells(self.world, exclude_entity=exclude_entity)

    def _trigger_terrain_events(self, entity: int, action: str):
        for system in self.world.systems:
            if system.__class__.__name__ == "RandomEventSystem":
                system.trigger_terrain_event(entity, action)
                break

    def _get_statistics_system(self):
        for system in self.world.systems:
            if system.__class__.__name__ == "StatisticsSystem":
                return system
        return None

    def _get_animation_system(self):
        for system in self.world.systems:
            if system.__class__.__name__ == "AnimationSystem":
                return system
        return None
