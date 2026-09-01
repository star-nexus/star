"""Window movement path using the shared unit spatial index.

A move order previously rebuilt unit occupancy once for destination legality and
again inside path planning.  At 2000 units that duplicate O(N) allocation showed
up as rare 18-24 ms mouse-move tails.  This subclass derives destination and
enemy-blocker sets in one pass over the maintained spatial index, then runs the
same pathfinding and result semantics as MovementSystem.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Set, Tuple

from framework.ecs import profiling

from ..components import (
    HexPosition,
    MovementAnimation,
    MovementPoints,
    Unit,
    UnitCount,
    UnitStatus,
)
from ..prefabs.config import UnitState
from ..utils.hex_utils import PathFinding
from ..utils.map_query import board_hexes, impassable_terrain, movement_costs
from ..utils.unit_spatial_index import (
    get_unit_spatial_index,
    update_unit_spatial_index,
)
from .resource_recovery_system import mark_movement_points_spent
from .movement_system import MovementSystem as _BaseMovementSystem


class MovementSystem(_BaseMovementSystem):
    """MovementSystem with one shared occupancy snapshot per order."""

    def move_unit(self, entity: int, target_pos: Tuple[int, int]) -> Dict[str, Any]:
        index = get_unit_spatial_index(self.world)
        if index is None:
            return super().move_unit(entity, target_pos)

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
                    "current_status": status.value if hasattr(status, "value") else status,
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

        with profiling.profiler.time_system(
            "move_occupancy_snapshot", category="input"
        ):
            occupied, enemy_held = index.occupancy_for_mover(entity, unit.faction)
        profiling.profiler.set_frame_metric("move_occupied_cells", len(occupied))
        profiling.profiler.set_frame_metric("move_enemy_blockers", len(enemy_held))
        profiling.profiler.set_frame_metric("move_spatial_revision", index.revision)

        if target_pos in occupied:
            return self._destination_occupied_result(entity, current_pos, target_pos)

        blockers = impassable_terrain(self.world) | enemy_held
        costs = movement_costs(self.world)
        with profiling.profiler.time_system("move_pathfinding", category="input"):
            path = PathFinding.find_path(
                current_pos,
                target_pos,
                blockers,
                None,
                walkable=board_hexes(self.world),
                step_cost=lambda pos: costs.get(pos, 999),
            )

        if not path or len(path) < 2:
            return self._no_path_result_indexed(
                entity,
                current_pos,
                target_pos,
                effective_movement,
                path,
                blockers,
                occupied,
            )

        total_cost = self._calculate_total_movement_cost(path)
        if total_cost > spendable:
            return self._insufficient_mp_result_indexed(
                entity,
                current_pos,
                target_pos,
                path,
                effective_movement,
                total_cost,
                current_mp,
                spendable,
                blockers,
                occupied,
            )

        print(f"✓ Unit {entity} moves to {target_pos}")
        # Preserve the existing move contract: spending a path budget did not
        # toggle MovementPoints.has_moved in this system.
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
            self.commit_hex_position(entity, target_pos[0], target_pos[1], arrived=True)

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
        super().commit_hex_position(entity, col, row, arrived=arrived)
        update_unit_spatial_index(self.world, entity)

    def _get_obstacles(
        self, exclude_entity: Optional[int] = None
    ) -> Set[Tuple[int, int]]:
        index = get_unit_spatial_index(self.world)
        if index is None:
            return super()._get_obstacles(exclude_entity)
        unit = self.world.get_component(exclude_entity, Unit) if exclude_entity is not None else None
        _occupied, enemy_held = index.occupancy_for_mover(
            exclude_entity, unit.faction if unit else None
        )
        return set(impassable_terrain(self.world)) | enemy_held

    def _occupied(self, exclude_entity: Optional[int] = None) -> Set[Tuple[int, int]]:
        index = get_unit_spatial_index(self.world)
        if index is None:
            return super()._occupied(exclude_entity)
        unit = self.world.get_component(exclude_entity, Unit) if exclude_entity is not None else None
        occupied, _enemy = index.occupancy_for_mover(
            exclude_entity, unit.faction if unit else None
        )
        return occupied

    def _no_path_result_indexed(
        self,
        entity,
        current_pos,
        target_pos,
        effective_movement,
        path,
        blockers,
        occupied,
    ):
        from ..utils.hex_utils import HexMath

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
                cause
                for cause in (
                    "Target position out of movement range" if distance_issue else None,
                    "Target position blocked by obstacles" if target_blocked else None,
                    "No valid route exists",
                )
                if cause
            ],
            "suggestion": (
                f"Try one of these nearby positions: {adjacent_free[:3]}"
                if adjacent_free
                else "No adjacent free positions available"
            ),
        }

    def _insufficient_mp_result_indexed(
        self,
        entity,
        current_pos,
        target_pos,
        path,
        effective_movement,
        total_cost,
        current_mp,
        spendable,
        blockers,
        occupied,
    ):
        from ..utils.hex_utils import HexMath

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

        nearby = []
        for cand in self._adjacent_free(current_pos, blockers | occupied):
            if self._get_terrain_movement_cost(cand) <= spendable:
                nearby.append((HexMath.hex_distance(cand, target_pos), cand))
        nearby.sort(key=lambda item: item[0])
        nearby_positions = [cell for _, cell in nearby[:3]]

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
                {"col": cell[0], "row": cell[1]} for cell in nearby_positions
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
