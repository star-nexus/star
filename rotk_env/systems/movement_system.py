"""
Movement System - Handles unit movement end-to-end:
- destination legality (must be unoccupied) and faction-relative pathfinding,
  both via map_query -- see that module for the movement invariants
- resource spending (movement points)
- animation kickoff and fallback instant move
- HexPosition committed per hex; it is the occupancy truth
- terrain-triggered events on arrival

Legality is decided once, when the order is processed. An accepted move is
never revalidated: the route is not re-checked while the unit travels.
"""

from typing import Any, Dict, List, Optional, Set, Tuple
from framework import System, World
from ..components import (
    HexPosition,
    MovementPoints,
    Unit,
    UnitCount,
    MovementAnimation,
    UnitStatus,
)
from ..prefabs.config import TerrainType, UnitState
from ..utils.hex_utils import HexMath
from .resource_recovery_system import mark_movement_points_spent


class MovementSystem(System):
    """System responsible for executing unit movement."""

    def __init__(self):
        super().__init__(required_components={HexPosition, MovementPoints, Unit})

    def initialize(self, world: World) -> None:
        self.world = world

    def subscribe_events(self):
        pass

    def update(self, delta_time: float) -> None:
        """Update movement system (no-op; movement is event/command driven)."""
        pass

    def move_unit(self, entity: int, target_pos: Tuple[int, int]) -> Dict[str, Any]:
        """Judge the order once against the world as it is now, then commit to it.

        Destination must be unoccupied, a faction-relative route must exist, and
        that route must fit the budget. Once those pass the move is accepted for
        good: nothing below revalidates it while the unit travels.
        """
        position = self.world.get_component(entity, HexPosition)
        movement_points = self.world.get_component(entity, MovementPoints)
        unit_count = self.world.get_component(entity, UnitCount)

        missing = []
        if not position:
            missing.append("HexPosition")
        if not movement_points:
            missing.append("MovementPoints")
        if not unit_count:
            missing.append("UnitCount")
        if missing:
            return {
                "success": False,
                "reason": "missing_components",
                "message": f"Unit {entity} missing required components: {', '.join(missing)}",
                "unit_id": entity,
                "missing_components": missing,
            }

        anim = self.world.get_component(entity, MovementAnimation)
        if anim and anim.is_moving:
            return {
                "success": False,
                "reason": "already_moving",
                "message": f"Unit {entity} is already moving",
                "unit_id": entity,
            }

        unit_status = self.world.get_component(entity, UnitStatus)
        if unit_status is not None:
            status = unit_status.current_status
            confused = status == UnitState.CONFUSION or status == UnitState.CONFUSION.value
            if confused:
                return {
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

        current_mp = movement_points.current_mp
        current_pos = (position.col, position.row)
        if current_mp <= 0:
            return {
                "success": False,
                "reason": "no_mp",
                "message": f"Unit has no movement points left: {current_mp}",
                "unit_id": entity,
                "current_movement_points": current_mp,
                "suggestion": "Use end_turn tool or wait for movement points to recover",
            }

        effective_movement = movement_points.get_effective_movement(unit_count)
        spendable = movement_points.spendable(unit_count)
        from ..utils.map_query import occupied_cells, plan_hex_path

        # Invariant 1: the destination must be free of units, either faction.
        # Checked before planning so "someone is standing there" is never
        # reported as "no route exists".
        if target_pos in occupied_cells(self.world, exclude_entity=entity):
            return self._destination_occupied_result(entity, current_pos, target_pos)

        # Plan the uncapped cheapest route so terrain cost above remaining MP is
        # reported as insufficient movement rather than an unreachable target.
        path = plan_hex_path(
            self.world,
            current_pos,
            target_pos,
            mover=entity,
        )
        if not path or len(path) < 2:
            return self._no_path_result(
                entity,
                current_pos,
                target_pos,
                effective_movement,
                path,
            )

        total_cost = self._calculate_total_movement_cost(path)
        if total_cost > spendable:
            return self._insufficient_mp_result(
                entity,
                current_pos,
                target_pos,
                path,
                effective_movement,
                total_cost,
                current_mp,
                spendable,
            )

        print(f"✓ Unit {entity} moves to {target_pos}")

        movement_points.current_mp -= total_cost
        mark_movement_points_spent(self.world, entity)

        statistics_system = self._get_statistics_system()
        if statistics_system:
            statistics_system.record_movement_action(entity, current_pos, target_pos)

        animation_system = self._get_animation_system()
        animated = False
        if animation_system:
            animation_system.start_unit_movement(entity, path)
            animated = True
        else:
            self.commit_hex_position(
                entity, target_pos[0], target_pos[1], arrived=True
            )

        return {
            "success": True,
            "path": path,
            "cost": total_cost,
            "from": current_pos,
            "to": target_pos,
            "animated": animated,
        }

    def commit_hex_position(
        self, entity: int, col: int, row: int, *, arrived: bool = False
    ) -> None:
        """Write the unit's committed hex. HexPosition is the occupancy truth.

        The move was already judged legal when the order was accepted and is not
        revalidated here, so this writes the planned hex even if another unit
        stepped onto it in the meantime.
        """
        position = self.world.get_component(entity, HexPosition)
        if position is not None:
            position.col, position.row = col, row
        if arrived:
            self._trigger_terrain_events(entity, "move_end")

    def _destination_occupied_result(
        self,
        entity: int,
        current_pos: Tuple[int, int],
        target_pos: Tuple[int, int],
    ) -> Dict[str, Any]:
        """Invariant 1 rejection.

        Says nothing about who is standing there: the occupant may be a unit
        this faction cannot see, and the occupant's faction is not a fact the
        mover is entitled to.
        """
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
        current_pos: Tuple[int, int],
        target_pos: Tuple[int, int],
        effective_movement: int,
        path: Optional[List[Tuple[int, int]]],
    ) -> Dict[str, Any]:
        blockers = self._get_obstacles(exclude_entity=entity)
        hex_distance = HexMath.hex_distance(current_pos, target_pos)
        distance_issue = hex_distance > effective_movement
        target_blocked = target_pos in blockers
        adjacent_free = self._adjacent_free(
            current_pos, blockers | self._occupied(entity)
        )
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
            # No global blocker dump here: since friendly units stopped being
            # blockers, that sample was a list of enemy positions, most of them
            # outside this faction's vision. Facts about the hex the agent named
            # are fair game; the rest of the board is not.
            "adjacent_free_positions": adjacent_free,
            "possible_causes": [
                c
                for c in (
                    "Target position out of movement range"
                    if distance_issue
                    else None,
                    "Target position blocked by obstacles"
                    if target_blocked
                    else None,
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
        current_pos: Tuple[int, int],
        target_pos: Tuple[int, int],
        path: List[Tuple[int, int]],
        effective_movement: int,
        total_cost: int,
        current_mp: int,
        spendable: int,
    ) -> Dict[str, Any]:
        occupied = self._occupied(entity)
        cumulative_cost = 0
        reachable_along_path = []
        for pos in path[1:]:
            step_cost = self._get_terrain_movement_cost(pos)
            if cumulative_cost + step_cost > spendable:
                break
            cumulative_cost += step_cost
            # Friendly hexes are legal to walk through, not to stand on.
            if pos not in occupied:
                reachable_along_path.append(pos)
        closest = reachable_along_path[-1] if reachable_along_path else current_pos

        blocked = self._get_obstacles(exclude_entity=entity) | occupied
        nearby = []
        for cand in self._adjacent_free(current_pos, blocked):
            if self._get_terrain_movement_cost(cand) <= spendable:
                nearby.append((HexMath.hex_distance(cand, target_pos), cand))
        nearby.sort(key=lambda x: x[0])
        nearby_positions = [c for _, c in nearby[:3]]

        farthest = {"col": closest[0], "row": closest[1]}
        if closest != current_pos:
            suggestion = (
                f"Try moving to the farthest hex on this path this turn: {closest}"
            )
            suggested_target = closest
        elif nearby_positions:
            suggestion = (
                "No step along the path is reachable this turn. "
                f"Try one of these nearby positions: {nearby_positions}"
            )
            suggested_target = nearby_positions[0]
        else:
            suggestion = (
                "No nearby reachable positions this turn. "
                "Wait to recover movement points."
            )
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

    def _adjacent_free(
        self, center: Tuple[int, int], blocked: Set[Tuple[int, int]]
    ) -> List[Tuple[int, int]]:
        """On-board neighbours a unit could actually stand on right now."""
        from ..utils.map_query import board_hexes

        walkable = board_hexes(self.world)
        return [
            n
            for n in HexMath.hex_neighbors(*center)
            if n not in blocked and (walkable is None or n in walkable)
        ]

    def _path_terrain_breakdown(
        self, path: List[Tuple[int, int]]
    ) -> List[Dict[str, Any]]:
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
        """Sum terrain movement costs along the path."""
        total_cost = 0
        for i in range(1, len(path)):
            total_cost += self._get_terrain_movement_cost(path[i])
        return total_cost

    def _get_terrain_movement_cost(self, position: Tuple[int, int]) -> int:
        """Enter-cost of the tile. Missing hexes are impassable."""
        from ..components.terrain import movement_cost_at

        return movement_cost_at(self.world, position)

    def _get_terrain_at_position(self, position: Tuple[int, int]) -> TerrainType:
        """Get terrain type at position (q, r)."""
        from ..components.terrain import terrain_at

        terrain = terrain_at(self.world, position)
        return terrain.terrain_type if terrain else TerrainType.PLAIN

    def _get_obstacles(
        self, exclude_entity: Optional[int] = None
    ) -> Set[Tuple[int, int]]:
        """Hexes this mover may not traverse: impassable terrain and enemies.

        Friendly units are not obstacles (invariant 2); they are only excluded
        as destinations, which is `_occupied`'s job.
        """
        from ..utils.map_query import faction_of, path_blockers

        return path_blockers(
            self.world,
            faction_of(self.world, exclude_entity),
            exclude_entity=exclude_entity,
        )

    def _occupied(self, exclude_entity: Optional[int] = None) -> Set[Tuple[int, int]]:
        """Hexes holding a unit of any faction: illegal destinations (invariant 1)."""
        from ..utils.map_query import occupied_cells

        return occupied_cells(self.world, exclude_entity=exclude_entity)

    def _trigger_terrain_events(self, entity: int, action: str):
        """Trigger terrain events in RandomEventSystem for a given action."""
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
