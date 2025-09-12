"""
LLM Action Handler V3 - Minimal, robust, and efficient action gateway
- Validates inputs and game state consistently
- Provides rich, structured error feedback for LLMs
- Bridges unit/system actions (move, attack, occupy, fortify, skills)
- Observation, faction state queries, and turn control

Designed for clarity and reliability when driven by language models.
"""

from typing import Dict, List, Any, Optional, Tuple, Set
from framework import World
from ..components import (
    Unit,
    UnitCount,
    HexPosition,
    MovementPoints,
    Combat,
    Vision,
    Player,
    TurnManager,
    GameState,
    Selected,
    UnitStatus,
    UnitSkills,
    ActionPoints,  # now points to the new multi-layer ActionPoints
    AttackPoints,
    ConstructionPoints,
    SkillPoints,
    Terrain,
    Tile,
    BattleLog,
    MapData,
    TerritoryControl,
    FogOfWar,
)
from ..prefabs.config import (
    Faction,
    UnitType,
    ActionType,
    TerrainType,
    UnitState,
    GameConfig,
)
from ..utils.hex_utils import HexMath


class LLMActionHandlerV3:
    """LLM Action Handler V3 - clean and efficient interface design."""

    def __init__(self, world: World):
        self.world = world

        # Supported action handlers
        self.action_handlers = {
            # Unit control actions
            "move": self.handle_move_action,
            "attack": self.handle_attack_action,
            "rest": self.handle_rest_action,
            "occupy": self.handle_occupy_action,
            "fortify": self.handle_fortify_action,
            "skill": self.handle_skill_action,
            # Observation actions
            "observation": self.handle_observation_action,
            # Faction info actions
            "get_faction_state": self.handle_faction_state,
            # System
            "get_action_list": self.handle_action_list,
            "end_turn": self.handle_end_turn,  # added end_turn
            "register_agent_info": self.handle_register_agent_info,
        }

    def execute_action(
        self, action_type: str, params: Dict[str, Any] = {}
    ) -> Dict[str, Any]:
        """Unified entry point for executing an action."""
        try:
            # parse action payload (if using wrapper)
            # action_type = action_data.get("action")
            # params = action_data.get("params", {})

            if not action_type:
                return self._create_error_response("Missing action field")

            if action_type not in self.action_handlers:
                return self._create_error_response(
                    f"Unsupported action: {action_type}",
                    {"supported_actions": list(self.action_handlers.keys())},
                )

            # dispatch
            print(f"Executing action: {action_type} with params: {params}")
            return self.action_handlers[action_type](params)

        except Exception as e:
            return self._create_error_response(f"Action execution failed: {str(e)}")

    # ==================== Unit control actions ====================

    def handle_move_action(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle move action - multi-layer resource model with detailed errors."""
        print(f"[MOVE_ACTION] Begin processing move action, params: {params}")

        # Parameter validation and feedback
        unit_id = params.get("unit_id")
        target_position = params.get("target_position")

        print(
            f"[MOVE_ACTION] Parsed params: unit_id={unit_id}, target_position={target_position}"
        )

        if not isinstance(unit_id, int):
            error_msg = (
                f"Invalid unit_id type: expected int, got {type(unit_id).__name__}"
            )
            print(f"[MOVE_ACTION] Param validation failed: {error_msg}")
            return self._create_error_response(
                error_msg,
                {
                    "received_unit_id": unit_id,
                    "expected_type": "int",
                    "valid_example": {"unit_id": 123},
                },
            )

        if not target_position or not isinstance(target_position, dict):
            error_msg = f"Invalid target_position: expected dict with col/row, got {type(target_position).__name__}"
            print(f"[MOVE_ACTION] Param validation failed: {error_msg}")
            return self._create_error_response(
                error_msg,
                {
                    "received_target_position": target_position,
                    "expected_format": {"col": "int", "row": "int"},
                    "valid_example": {"target_position": {"col": 5, "row": 8}},
                },
            )

        target_col = target_position.get("col")
        target_row = target_position.get("row")

        # 检查目标位置坐标类型
        if not isinstance(target_col, int) or not isinstance(target_row, int):
            error_msg = f"Invalid coordinate types: col must be int, row must be int"
            print(f"[MOVE_ACTION] Coordinate type validation failed: {error_msg}")
            return self._create_error_response(
                error_msg,
                {
                    "received_col": target_col,
                    "received_row": target_row,
                    "received_col_type": type(target_col).__name__,
                    "received_row_type": type(target_row).__name__,
                    "expected_types": {"col": "int", "row": "int"},
                    "valid_example": {"target_position": {"col": 5, "row": 8}},
                },
            )

        # Check map bounds for target
        print(
            f"[MOVE_ACTION] Checking target within map bounds: ({target_col}, {target_row})"
        )
        if not self._is_position_within_map_bounds(target_col, target_row):
            from ..prefabs.config import GameConfig

            center = GameConfig.MAP_WIDTH // 2
            min_coord = -center
            max_coord = center - 1
            error_msg = f"Target position ({target_col}, {target_row}) is outside map boundaries"
            print(f"[MOVE_ACTION] Map boundary check failed: {error_msg}")
            return self._create_error_response(
                error_msg,
                {
                    "target_position": {"col": target_col, "row": target_row},
                    "map_boundaries": {
                        "min_col": min_coord,
                        "max_col": max_coord,
                        "min_row": min_coord,
                        "max_row": max_coord,
                    },
                    "map_size": {
                        "width": GameConfig.MAP_WIDTH,
                        "height": GameConfig.MAP_HEIGHT,
                    },
                    "coordinate_system": "center-based",
                    "explanation": f"Map uses center-based coordinates with (0,0) at center. For {GameConfig.MAP_WIDTH}x{GameConfig.MAP_HEIGHT} map, valid range is [{min_coord}, {max_coord}]",
                    "suggestion": f"Choose a position within bounds: col ({min_coord} to {max_coord}), row ({min_coord} to {max_coord})",
                },
            )

        print(f"[MOVE_ACTION] Target within bounds: ({target_col}, {target_row})")

        # Unit existence check
        print(f"[MOVE_ACTION] Checking if unit {unit_id} exists...")
        unit = self.world.get_component(unit_id, Unit)
        if not unit:
            error_msg = f"Unit {unit_id} not found in world"
            print(f"[MOVE_ACTION] Unit not found: {error_msg}")
            return self._create_error_response(
                error_msg,
                {
                    "requested_unit_id": unit_id,
                    "suggestion": "Use get_faction_state action to see all units for a faction",
                },
            )

        print(
            f"[MOVE_ACTION] Unit {unit_id} exists, type: {unit.unit_type.value}, faction: {unit.faction.value}"
        )

        # === 阵营回合权限验证 ===
        print(f"[MOVE_ACTION] Checking faction turn permission for unit {unit_id}...")
        permission_error = self._validate_faction_turn_permission(unit_id, "move")
        if permission_error:
            print(
                f"[MOVE_ACTION] Faction permission denied: {permission_error['message']}"
            )
            return permission_error
        print(f"[MOVE_ACTION] Faction permission granted for {unit.faction.value}")

        # Required components
        print(f"[MOVE_ACTION] Checking required components for unit {unit_id}...")
        position = self.world.get_component(unit_id, HexPosition)
        movement_points = self.world.get_component(unit_id, MovementPoints)
        unit_count = self.world.get_component(unit_id, UnitCount)
        action_points = self.world.get_component(unit_id, ActionPoints)
        unit_status = self.world.get_component(unit_id, UnitStatus)

        # Detailed missing-components report
        missing_components = []
        component_info = {}

        if not position:
            missing_components.append("HexPosition")
        else:
            component_info["position"] = {"col": position.col, "row": position.row}
            print(f"[MOVE_ACTION] Current position: ({position.col}, {position.row})")

        if not movement_points:
            missing_components.append("MovementPoints")
        else:
            component_info["movement_points"] = {
                "current_mp": movement_points.current_mp,
                "max_mp": movement_points.max_mp,
                "recovery_rate": getattr(movement_points, "recovery_rate", "unknown"),
            }
            print(
                f"[MOVE_ACTION] Movement points: {movement_points.current_mp}/{movement_points.max_mp}"
            )

        if not unit_count:
            missing_components.append("UnitCount")
        else:
            component_info["unit_count"] = {
                "current_count": unit_count.current_count,
                "max_count": unit_count.max_count,
                "health_percentage": unit_count.current_count
                / unit_count.max_count
                * 100,
            }
            print(
                f"[MOVE_ACTION] Unit strength: {unit_count.current_count}/{unit_count.max_count}"
            )

        if not action_points:
            missing_components.append("ActionPoints")
        else:
            component_info["action_points"] = {
                "current_ap": action_points.current_ap,
                "max_ap": action_points.max_ap,
            }
            print(
                f"[MOVE_ACTION] Action points: {action_points.current_ap}/{action_points.max_ap}"
            )

        if missing_components:
            error_msg = f"Unit {unit_id} missing required components: {', '.join(missing_components)}"
            print(f"[MOVE_ACTION] Missing components: {error_msg}")
            return self._create_error_response(
                error_msg,
                {
                    "unit_id": unit_id,
                    "missing_components": missing_components,
                    "existing_components": component_info,
                    "required_components": [
                        "HexPosition",
                        "MovementPoints",
                        "UnitCount",
                        "ActionPoints",
                    ],
                    "suggestion": "This unit may not be properly initialized",
                },
            )

        # Unit status check
        if unit_status:
            print(f"[MOVE_ACTION] Unit status: {unit_status.current_status}")
            if unit_status.current_status == UnitState.CONFUSION:
                error_msg = f"Unit {unit_id} is confused and cannot move"
                print(f"[MOVE_ACTION] Status blocks movement: {error_msg}")
                return self._create_error_response(
                    error_msg,
                    {
                        "unit_id": unit_id,
                        "current_status": unit_status.current_status.value,
                        "blocking_statuses": [UnitState.CONFUSION.value],
                        "suggestion": "Wait for confusion to clear or use skill to remove it",
                        "unit_info": component_info,
                    },
                )
        else:
            print(f"[MOVE_ACTION] Unit status component missing; assume normal")

        # === Layer 1: Action points (decision layer) ===
        print(f"[MOVE_ACTION] Checking action points...")
        required_ap = 1
        current_ap = action_points.current_ap

        if current_ap < required_ap:
            error_msg = f"Insufficient action points to initiate movement decision: need {required_ap}, have {current_ap}"
            print(f"[MOVE_ACTION] Insufficient AP: {error_msg}")
            return self._create_error_response(
                error_msg,
                {
                    "unit_id": unit_id,
                    "required_action_points": required_ap,
                    "current_action_points": current_ap,
                    "deficit": required_ap - current_ap,
                    "action_point_info": component_info.get("action_points", {}),
                    "suggestion": "Wait for action points to recover or use garrison action",
                },
            )
        print(f"[MOVE_ACTION] AP check passed: {current_ap}/{action_points.max_ap}")

        # === Layer 2: Movement points (execution layer) ===
        print(f"[MOVE_ACTION] Checking movement points...")
        current_mp = movement_points.current_mp

        if current_mp <= 0:
            error_msg = f"Unit has no movement points left: {current_mp}"
            print(f"[MOVE_ACTION] Insufficient MP: {error_msg}")
            return self._create_error_response(
                error_msg,
                {
                    "unit_id": unit_id,
                    "current_movement_points": current_mp,
                    "max_movement_points": movement_points.max_mp,
                    "movement_point_info": component_info.get("movement_points", {}),
                    "suggestion": "Wait for movement points to recover",
                },
            )
        print(f"[MOVE_ACTION] MP check passed: {current_mp}/{movement_points.max_mp}")

        # Compute effective movement (consider strength)
        effective_movement = movement_points.get_effective_movement(unit_count)
        current_pos = (position.col, position.row)
        target_pos = (target_col, target_row)

        print(
            f"[MOVE_ACTION] Effective movement: {effective_movement} (base: {current_mp}, strength: {unit_count.current_count}/{unit_count.max_count})"
        )
        print(f"[MOVE_ACTION] Path planning: {current_pos} -> {target_pos}")

        # Path and reachability
        print(f"[MOVE_ACTION] Gathering map obstacles...")
        obstacles = self._get_obstacles_excluding_unit(unit_id)  # exclude moving unit
        print(f"[MOVE_ACTION] Obstacles count: {len(obstacles) if obstacles else 0}")

        # 检查目标位置是否被占用
        if target_pos in obstacles:
            # Find the unit occupying the target tile
            occupying_unit_id = None
            occupying_unit_info = None
            for entity in self.world.query().with_all(HexPosition, Unit).entities():
                if entity == unit_id:
                    continue  # skip the moving unit itself
                pos = self.world.get_component(entity, HexPosition)
                if pos and (pos.col, pos.row) == target_pos:
                    occupying_unit_id = entity
                    unit_comp = self.world.get_component(entity, Unit)
                    if unit_comp:
                        occupying_unit_info = {
                            "unit_id": entity,
                            "unit_type": unit_comp.unit_type.value,
                            "faction": unit_comp.faction.value,
                        }
                    break

            error_msg = (
                f"Target position {target_pos} is occupied by unit {occupying_unit_id}"
            )
            print(f"[MOVE_ACTION] Target position occupied: {error_msg}")
            return self._create_error_response(
                error_msg,
                {
                    "unit_id": unit_id,
                    "target_position": target_pos,
                    "occupying_unit_id": occupying_unit_id,
                    "occupying_unit_info": occupying_unit_info,
                    "current_position": current_pos,
                    "suggestion": "Choose an unoccupied adjacent position",
                    "adjacent_positions": self._get_adjacent_free_positions(
                        current_pos, obstacles
                    ),
                },
            )

        from ..utils.hex_utils import PathFinding

        print(f"[MOVE_ACTION] Running pathfinding...")
        print(f"[MOVE_ACTION] Start: {current_pos}")
        print(f"[MOVE_ACTION] Target: {target_pos}")
        print(f"[MOVE_ACTION] Effective movement range: {effective_movement}")
        print(
            f"[MOVE_ACTION] Obstacles (sample): {list(obstacles)[:10]}..."
        )  # sample first 10

        path = PathFinding.find_path(
            current_pos, target_pos, obstacles, effective_movement
        )

        print(f"[MOVE_ACTION] Path result: {path}")

        if not path or len(path) < 2:
            # Provide details for pathfinding failure
            from ..utils.hex_utils import HexMath

            hex_distance = HexMath.hex_distance(current_pos, target_pos)

            # Range issue?
            distance_issue = hex_distance > effective_movement

            # Target blocked?
            target_blocked = target_pos in obstacles

            # Nearby reachable positions
            adjacent_free_positions = self._get_adjacent_free_positions(
                current_pos, obstacles
            )

            error_msg = f"No valid path to target position {target_pos}"
            print(f"[MOVE_ACTION] Pathfinding failed: {error_msg}")
            print(f"[MOVE_ACTION] Hex distance: {hex_distance}")
            print(f"[MOVE_ACTION] Effective movement: {effective_movement}")
            print(f"[MOVE_ACTION] Distance exceeds: {distance_issue}")
            print(f"[MOVE_ACTION] Target blocked: {target_blocked}")
            print(f"[MOVE_ACTION] Adjacent free: {adjacent_free_positions}")

            return self._create_error_response(
                error_msg,
                {
                    "unit_id": unit_id,
                    "start_position": current_pos,
                    "target_position": target_pos,
                    "effective_movement": effective_movement,
                    "hex_distance": hex_distance,
                    "distance_exceeds_range": distance_issue,
                    "target_blocked": target_blocked,
                    "path_found": path is not None,
                    "path_length": len(path) if path else 0,
                    "obstacle_count": len(obstacles),
                    "obstacles_sample": list(obstacles)[:10],  # first 10 samples
                    "adjacent_free_positions": adjacent_free_positions,
                    "possible_causes": [
                        (
                            "Target position out of movement range"
                            if distance_issue
                            else None
                        ),
                        (
                            "Target position blocked by obstacles"
                            if target_blocked
                            else None
                        ),
                        "No valid route exists",
                        "PathFinding algorithm limitation",
                    ],
                    "suggestion": (
                        f"Try one of these nearby positions: {adjacent_free_positions[:3]}"
                        if adjacent_free_positions
                        else "No adjacent free positions available"
                    ),
                },
            )

        print(f"[MOVE_ACTION] Path found, length: {len(path)}, path: {path}")

        # Total movement cost (terrain-aware)
        print(f"[MOVE_ACTION] Calculating path movement cost...")
        total_movement_cost = self._calculate_total_movement_cost(path)
        print(f"[MOVE_ACTION] Total cost: {total_movement_cost} MP")

        # Ensure current movement points suffice (using remaining MP)
        if total_movement_cost > current_mp:
            error_msg = f"Insufficient movement points this turn: need {total_movement_cost}, have {current_mp}."
            print(f"[MOVE_ACTION] Insufficient MP for target: {error_msg}")

            # Compute furthest reachable step along path with current MP
            cumulative_cost = 0
            reachable_positions_along_path = []
            for step_index, pos in enumerate(path[1:]):  # skip origin
                step_cost = self._get_terrain_movement_cost(pos)
                if cumulative_cost + step_cost <= current_mp:
                    cumulative_cost += step_cost
                    reachable_positions_along_path.append(pos)
                else:
                    break

            closest_reachable_position = (
                reachable_positions_along_path[-1]
                if reachable_positions_along_path
                else current_pos
            )

            # Offer nearby reachable suggestions (prefer closer to target)
            nearby_reachable_suggestions = []
            try:
                neighbor_candidates = self._get_adjacent_free_positions(
                    current_pos, obstacles
                )
                scored = []
                for cand in neighbor_candidates:
                    cand_cost = self._get_terrain_movement_cost(cand)
                    if cand_cost <= current_mp:
                        dist = HexMath.hex_distance(cand, target_pos)
                        scored.append((dist, cand))
                scored.sort(key=lambda x: x[0])
                nearby_reachable_suggestions = [c for _, c in scored[:3]]
            except Exception:
                pass

            suggestion_text = (
                f"Try moving to the closest reachable position this turn: {closest_reachable_position}"
                if closest_reachable_position != current_pos
                else (
                    f"No step along the path is reachable this turn. Try one of these nearby positions: {nearby_reachable_suggestions}"
                    if nearby_reachable_suggestions
                    else "No nearby reachable positions this turn. Wait to recover movement points."
                )
            )

            return self._create_error_response(
                error_msg,
                {
                    "failure_reason": "insufficient_movement_points",
                    "unit_id": unit_id,
                    "required_movement_points": total_movement_cost,
                    "current_movement_points": current_mp,
                    "deficit": total_movement_cost - current_mp,
                    "path": path,
                    "path_length": len(path) - 1,
                    "effective_movement": effective_movement,
                    "terrain_costs": self._get_path_terrain_breakdown(path),
                    "closest_reachable_position": (
                        {
                            "col": closest_reachable_position[0],
                            "row": closest_reachable_position[1],
                        }
                        if isinstance(closest_reachable_position, tuple)
                        else {
                            "col": current_pos[0],
                            "row": current_pos[1],
                        }
                    ),
                    "reachable_steps": len(reachable_positions_along_path),
                    "suggested_action": {
                        "action": "move",
                        "params": {
                            "unit_id": unit_id,
                            "target_position": {
                                "col": (
                                    closest_reachable_position[0]
                                    if isinstance(closest_reachable_position, tuple)
                                    else current_pos[0]
                                ),
                                "row": (
                                    closest_reachable_position[1]
                                    if isinstance(closest_reachable_position, tuple)
                                    else current_pos[1]
                                ),
                            },
                        },
                    },
                    "nearby_reachable_positions": [
                        {"col": p[0], "row": p[1]} for p in nearby_reachable_suggestions
                    ],
                    "suggestion": suggestion_text,
                },
            )

        print(
            f"[MOVE_ACTION] Movement sufficient, remaining: {current_mp - total_movement_cost}"
        )

        # 执行移动
        print(f"[MOVE_ACTION] Fetching MovementSystem...")
        movement_system = self._get_movement_system()
        if not movement_system:
            error_msg = "Movement system not available"
            print(f"[MOVE_ACTION] System error: {error_msg}")
            return self._create_error_response(
                error_msg,
                {
                    "unit_id": unit_id,
                    "system_error": "MovementSystem not found",
                    "suggestion": "This is a game engine error - contact administrator",
                },
            )

        print(f"[MOVE_ACTION] Executing move...")
        success = movement_system.move_unit(unit_id, target_pos)

        if success:
            print(f"[MOVE_ACTION] Move succeeded")

            # 从 MovementAnimation 组件获取默认速度，或者硬编码一个已知值
            # 这里我们使用在 rotk_env/components/animation.py 中定义的默认值 2.0
            animation_speed = 2.0
            path_length = len(path) - 1 if path else 0
            estimated_duration = (
                path_length / animation_speed if animation_speed > 0 else 0
            )

            result = {
                "success": True,
                "result": True,
                "message": f"Unit {unit_id} has started moving from {current_pos} to {target_pos}.",
                "details": f"Unit {unit_id} has started moving from {current_pos} to {target_pos}.",
                "action_status": "in_progress",
                "movement_descriptions": {
                    "start_position": {"col": current_pos[0], "row": current_pos[1]},
                    "target_position": {"col": target_pos[0], "row": target_pos[1]},
                    "path": path,
                    "path_length": path_length,
                    "estimated_duration_seconds": round(estimated_duration, 2),
                },
            }
            print(f"[MOVE_ACTION] Move done, result: {result}")
            return result
        else:
            error_msg = "Movement system failed to execute move"
            print(f"[MOVE_ACTION] Move execution failed: {error_msg}")
            return self._create_error_response(
                error_msg,
                {
                    "unit_id": unit_id,
                    "start_position": current_pos,
                    "target_position": target_pos,
                    "path": path,
                    "system_error": "MovementSystem.move_unit returned false",
                    "possible_causes": [
                        "Target position became occupied during execution",
                        "Unit state changed during execution",
                        "Internal movement system error",
                    ],
                    "suggestion": "Try the move again or check target position",
                },
            )

    def handle_attack_action(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle attack action - validation plus structured feedback."""
        print(f"[ATTACK_ACTION] Begin processing attack action, params: {params}")

        # === Layer 1: parameter format validation ===
        unit_id = params.get("unit_id")
        target_id = params.get("target_id")

        if not isinstance(unit_id, int) or not isinstance(target_id, int):
            return self._create_error_response(
                "unit_id and target_id must be integers",
                {
                    "received_unit_id": unit_id,
                    "received_target_id": target_id,
                    "expected_types": {"unit_id": "int", "target_id": "int"},
                    "valid_example": {"unit_id": 123, "target_id": 456},
                },
            )

        print(f"[ATTACK_ACTION] Params ok: attacker={unit_id}, target={target_id}")

        # === Layer 2: attacker/target existence validation ===
        attacker_unit = self.world.get_component(unit_id, Unit)
        if not attacker_unit:
            return self._create_error_response(
                f"Attacker unit {unit_id} not found",
                {
                    "unit_id": unit_id,
                    "suggestion": "Use get_faction_state action to see all available units",
                },
            )

        target_unit = self.world.get_component(target_id, Unit)
        if not target_unit:
            return self._create_error_response(
                f"Target unit {target_id} not found",
                {
                    "target_id": target_id,
                    "suggestion": "Use observation action to see visible enemy units",
                },
            )

        print(
            f"[ATTACK_ACTION] Units exist: {attacker_unit.unit_type.value}({attacker_unit.faction.value}) -> {target_unit.unit_type.value}({target_unit.faction.value})"
        )

        # === Layer 3: 阵营回合权限验证 ===
        print(f"[ATTACK_ACTION] Checking faction turn permission for unit {unit_id}...")
        permission_error = self._validate_faction_turn_permission(unit_id, "attack")
        if permission_error:
            print(
                f"[ATTACK_ACTION] Faction permission denied: {permission_error['message']}"
            )
            return permission_error
        print(
            f"[ATTACK_ACTION] Faction permission granted for {attacker_unit.faction.value}"
        )

        # === Layer 4: faction relation validation ===
        if attacker_unit.faction == target_unit.faction:
            return self._create_error_response(
                "Cannot attack units of same faction",
                {
                    "attacker_faction": attacker_unit.faction.value,
                    "target_faction": target_unit.faction.value,
                    "suggestion": "Select an enemy unit from a different faction",
                },
            )

        # === Layer 4: required components validation ===
        print(f"[ATTACK_ACTION] Checking attacker components...")
        attacker_pos = self.world.get_component(unit_id, HexPosition)
        attacker_combat = self.world.get_component(unit_id, Combat)
        attacker_action_points = self.world.get_component(unit_id, ActionPoints)
        attacker_count = self.world.get_component(unit_id, UnitCount)

        missing_attacker_components = []
        if not attacker_pos:
            missing_attacker_components.append("HexPosition")
        if not attacker_combat:
            missing_attacker_components.append("Combat")
        if not attacker_action_points:
            missing_attacker_components.append("ActionPoints")
        if not attacker_count:
            missing_attacker_components.append("UnitCount")

        if missing_attacker_components:
            return self._create_error_response(
                f"Attacker unit {unit_id} missing required components: {', '.join(missing_attacker_components)}",
                {
                    "unit_id": unit_id,
                    "missing_components": missing_attacker_components,
                    "required_components": [
                        "HexPosition",
                        "Combat",
                        "ActionPoints",
                        "UnitCount",
                    ],
                    "suggestion": "This unit may not be properly initialized",
                },
            )

        print(f"[ATTACK_ACTION] Checking target components...")
        target_pos = self.world.get_component(target_id, HexPosition)
        target_count = self.world.get_component(target_id, UnitCount)

        missing_target_components = []
        if not target_pos:
            missing_target_components.append("HexPosition")
        if not target_count:
            missing_target_components.append("UnitCount")

        if missing_target_components:
            return self._create_error_response(
                f"Target unit {target_id} missing required components: {', '.join(missing_target_components)}",
                {
                    "target_id": target_id,
                    "missing_components": missing_target_components,
                    "required_components": ["HexPosition", "UnitCount"],
                    "suggestion": "Target unit may not be properly initialized",
                },
            )

        # === Layer 5: action point validation ===
        print(f"[ATTACK_ACTION] Checking action points...")
        if not attacker_action_points.can_perform_action(ActionType.ATTACK):
            required_ap = 2  # requires 2 AP to attack
            current_ap = attacker_action_points.current_ap
            return self._create_error_response(
                f"Insufficient action points for attack: need {required_ap}, have {current_ap}",
                {
                    "unit_id": unit_id,
                    "required_action_points": required_ap,
                    "current_action_points": current_ap,
                    "deficit": required_ap - current_ap,
                    "suggestion": "Wait for action points to recover or use rest action",
                },
            )

        # === Layer 6: unit status validation ===
        print(f"[ATTACK_ACTION] Checking unit status...")

        # Prohibit attacking when strength ≤ 10%
        if attacker_count.ratio <= 0.1:
            return self._create_error_response(
                f"Unit {unit_id} has too few troops to attack: {attacker_count.current_count}/{attacker_count.max_count} ({attacker_count.ratio*100:.1f}%)",
                {
                    "unit_id": unit_id,
                    "current_count": attacker_count.current_count,
                    "max_count": attacker_count.max_count,
                    "ratio_percentage": round(attacker_count.ratio * 100, 1),
                    "minimum_required_percentage": 10.0,
                    "suggestion": "Unit needs more than 10% of original strength to attack",
                },
            )

        # Allow multiple attacks per turn as long as AP allow (no single-attack cap)
        # if attacker_combat.has_attacked:
        #     return self._create_error_response(
        #         f"Unit {unit_id} has already attacked this turn",
        #         {
        #             "unit_id": unit_id,
        #             "suggestion": "Each unit can only attack once per turn",
        #         },
        #     )

        # Target must be alive
        if target_count.current_count <= 0:
            return self._create_error_response(
                f"Target unit {target_id} is already destroyed",
                {
                    "target_id": target_id,
                    "current_count": target_count.current_count,
                    "suggestion": "Select a living enemy unit",
                },
            )

        # === Layer 7: range validation ===
        print(f"[ATTACK_ACTION] Checking attack range...")
        attacker_current_pos = (attacker_pos.col, attacker_pos.row)
        target_current_pos = (target_pos.col, target_pos.row)
        distance = HexMath.hex_distance(attacker_current_pos, target_current_pos)
        attack_range = attacker_combat.attack_range

        print(f"[ATTACK_ACTION] Distance={distance}, Attack range={attack_range}")

        if distance > attack_range:
            return self._create_error_response(
                f"Target out of attack range: distance {distance}, range {attack_range}",
                {
                    "unit_id": unit_id,
                    "target_id": target_id,
                    "attacker_position": attacker_current_pos,
                    "target_position": target_current_pos,
                    "distance": distance,
                    "attack_range": attack_range,
                    "range_deficit": distance - attack_range,
                    "unit_type": attacker_unit.unit_type.value,
                    "suggestion": f"Move {distance - attack_range} hexes closer or select a target within {attack_range} hexes",
                },
            )

        # === Layer 8: execute attack ===
        print(f"[ATTACK_ACTION] All validations passed, executing attack...")
        combat_system = self._get_combat_system()
        if not combat_system:
            return self._create_error_response(
                "Combat system not available",
                {
                    "system_error": "CombatSystem not found",
                    "suggestion": "This is a game engine error - contact administrator",
                },
            )

        # Record pre-attack snapshot for diff
        pre_attack_state = {
            "attacker_action_points": attacker_action_points.current_ap,
            "target_count": target_count.current_count,
            "attacker_has_attacked": attacker_combat.has_attacked,
        }

        # Invoke CombatSystem
        attack_result = combat_system.execute_attack(unit_id, target_id)

        if not attack_result:
            return self._create_error_response(
                "Attack execution failed",
                {
                    "unit_id": unit_id,
                    "target_id": target_id,
                    "suggestion": "Attack validation passed but execution failed - possible game state conflict",
                },
            )

        # === Layer 9: format result ===
        print(f"[ATTACK_ACTION] Attack executed successfully.")

        # Post-attack snapshot
        post_attack_state = {
            "attacker_action_points": attacker_action_points.current_ap,
            "target_count": target_count.current_count,
            "attacker_has_attacked": attacker_combat.has_attacked,
        }

        # Compute deltas
        action_points_used = (
            pre_attack_state["attacker_action_points"]
            - post_attack_state["attacker_action_points"]
        )
        casualties_inflicted = (
            pre_attack_state["target_count"] - post_attack_state["target_count"]
        )
        target_destroyed = post_attack_state["target_count"] <= 0

        # Terrain info
        attacker_terrain = self._get_terrain_at_position(attacker_current_pos)
        target_terrain = self._get_terrain_at_position(target_current_pos)

        result = {
            "success": True,
            "result": True,
            "message": f"Unit {unit_id} attacked unit {target_id} successfully",
            "details": f"Unit {unit_id} attacked unit {target_id} successfully",
            "battle_summary": {
                "attacker_info": {
                    "unit_id": unit_id,
                    "unit_type": attacker_unit.unit_type.value,
                    "faction": attacker_unit.faction.value,
                    "position": attacker_current_pos,
                    "terrain": attacker_terrain.value,
                },
                "target_info": {
                    "unit_id": target_id,
                    "unit_type": target_unit.unit_type.value,
                    "faction": target_unit.faction.value,
                    "position": target_current_pos,
                    "terrain": target_terrain.value,
                },
                "battle_result": attack_result,
                "casualties_inflicted": casualties_inflicted,
                "target_destroyed": target_destroyed,
                "distance": distance,
            },
            "resource_consumption": {
                "action_points_used": action_points_used,
            },
            "remaining_resources": {
                "action_points": post_attack_state["attacker_action_points"],
                # "can_attack_again": not post_attack_state["attacker_has_attacked"],  # 移除单次攻击限制
            },
            "tactical_info": {
                "attack_was_effective": casualties_inflicted > 0,
                "target_remaining_strength": f"{post_attack_state['target_count']}/{target_count.max_count}",
                "target_strength_percentage": (
                    round(
                        (post_attack_state["target_count"] / target_count.max_count)
                        * 100,
                        1,
                    )
                    if target_count.max_count > 0
                    else 0
                ),
            },
        }

        print(
            f"[ATTACK_ACTION] {casualties_inflicted} casualties, target {'destroyed' if target_destroyed else 'alive'}"
        )
        return result

    def handle_rest_action(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理待命动作"""
        unit_id = params.get("unit_id")

        if not isinstance(unit_id, int):
            return self._create_error_response("unit_id must be integer")

        # 检查单位存在性
        unit = self.world.get_component(unit_id, Unit)
        if not unit:
            return self._create_error_response(f"Unit {unit_id} not found")

        # 阵营回合权限验证
        permission_error = self._validate_faction_turn_permission(unit_id, "rest")
        if permission_error:
            return permission_error

        # 执行待命
        action_system = self._get_action_system()
        if action_system:
            success = action_system.perform_wait(unit_id)
            if success:
                action_points = self.world.get_component(unit_id, ActionPoints)
                unit_status = self.world.get_component(unit_id, UnitStatus)

                return {
                    "success": True,
                    "result": True,
                    "message": f"Unit {unit_id} is resting and recovering",
                    "details": f"Unit {unit_id} is resting and recovering",
                    # "effects": {
                    #     "morale_recovery": True,
                    #     "fatigue_removed": unit_status.current_status
                    #     != UnitState.FATIGUE,
                    #     "turn_ended": True,
                    # },
                    "remaining_action_points": (
                        action_points.current_ap - 1 if action_points else 0
                    ),
                }
            else:
                return self._create_error_response(
                    "Action system failed to execute wait"
                )
        else:
            return self._create_error_response("Action system not available")

    def handle_occupy_action(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理占领动作 - 占领区域不消耗建筑点，但消耗行动点"""
        unit_id = params.get("unit_id")
        position = params.get("position")

        if not isinstance(unit_id, int):
            return self._create_error_response("unit_id must be integer")

        if not position or not isinstance(position, dict):
            return self._create_error_response("position must be object with col/row")

        col = position.get("col")
        row = position.get("row")

        if not isinstance(col, int) or not isinstance(row, int):
            return self._create_error_response("position col/row must be integers")

        # 检查单位存在性
        unit = self.world.get_component(unit_id, Unit)
        if not unit:
            return self._create_error_response(f"Unit {unit_id} not found")

        # 阵营回合权限验证
        permission_error = self._validate_faction_turn_permission(unit_id, "occupy")
        if permission_error:
            return permission_error

        # 检查单位位置和行动点
        unit_pos = self.world.get_component(unit_id, HexPosition)
        action_points = self.world.get_component(unit_id, ActionPoints)

        if not unit_pos:
            return self._create_error_response("Unit missing position component")

        if not action_points or not action_points.can_perform_action(ActionType.OCCUPY):
            return self._create_error_response(
                f"Insufficient action points for occupy: need 1, have {action_points.current_ap if action_points else 0}",
            )

        # 检查是否在单位当前位置或相邻位置
        current_pos = (unit_pos.col, unit_pos.row)
        target_pos = (col, row)

        from ..utils.hex_utils import HexMath

        distance = HexMath.hex_distance(current_pos, target_pos)

        if distance > 1:
            return self._create_error_response(
                f"Cannot occupy position {target_pos}: too far from unit position {current_pos}. Can only occupy current or adjacent positions.",
            )

        # 检查目标位置是否已被占领
        territory_system = self._get_territory_system()
        if not territory_system:
            return self._create_error_response("Territory system not available")

        # 检查是否已被己方占领
        current_control = territory_system.get_territory_control(target_pos)
        if current_control and current_control == unit.faction:
            return self._create_error_response(
                f"Position {target_pos} already controlled by faction {unit.faction.value}",
            )

        # 执行占领
        success = territory_system.occupy_territory(unit_id, target_pos)

        if success:
            # 消耗行动点
            action_points.consume_ap(ActionType.OCCUPY)

            # 获取地形信息
            terrain_type = self._get_terrain_at_position(target_pos)

            return {
                "success": True,
                "result": True,
                "message": f"Unit {unit_id} occupied territory at {target_pos}",
                "details": f"Unit {unit_id} occupied territory at {target_pos}",
                # "occupation_details": {
                #     "position": target_pos,
                #     "terrain_type": terrain_type.value,
                #     "previous_controller": (
                #         current_control.value if current_control else "neutral"
                #     ),
                #     "new_controller": unit.faction.value,
                #     "occupation_method": "military_control",
                # },
                # "resource_consumption": {
                #     "action_points_used": 1,
                #     "construction_points_used": 0,  # 占领不消耗建筑点
                # },
                # "remaining_resources": {
                #     "action_points": action_points.current_ap,
                # },
                # "strategic_value": {
                #     "terrain_bonus": self._get_terrain_occupation_bonus(terrain_type),
                #     "resource_production": self._get_terrain_resource_value(
                #         terrain_type
                #     ),
                # },
            }
        else:
            return self._create_error_response(
                f"Failed to occupy position {target_pos}. Position may be contested or invalid."
            )

    def handle_fortify_action(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理工事建设动作"""
        unit_id = params.get("unit_id")
        position = params.get("position")

        if not isinstance(unit_id, int):
            return self._create_error_response("unit_id must be integer")

        if not position or not isinstance(position, dict):
            return self._create_error_response("position must be object with col/row")

        col = position.get("col")
        row = position.get("row")

        if not isinstance(col, int) or not isinstance(row, int):
            return self._create_error_response("position col/row must be integers")

        # 检查单位存在性
        unit = self.world.get_component(unit_id, Unit)
        if not unit:
            return self._create_error_response(f"Unit {unit_id} not found")

        # 阵营回合权限验证
        permission_error = self._validate_faction_turn_permission(unit_id, "fortify")
        if permission_error:
            return permission_error

        # 检查动作点和建造点
        action_points = self.world.get_component(unit_id, ActionPoints)
        construction_points = self.world.get_component(unit_id, ConstructionPoints)

        if not action_points or not action_points.can_perform_action(
            ActionType.FORTIFY
        ):
            return self._create_error_response(
                f"Insufficient action points for fortify: need 1, have {action_points.current_ap if action_points else 0}",
            )

        if not construction_points or not construction_points.can_build(1):
            return self._create_error_response(
                f"Insufficient construction points for fortify: need 1, have {construction_points.current_cp if construction_points else 0}",
            )

        # 获取地形类型和工事等级限制
        terrain_type = self._get_terrain_at_position((col, row))
        max_level = self._get_max_fortification_level(terrain_type)

        # 检查当前工事等级
        current_level = self._get_current_fortification_level((col, row))

        if current_level >= max_level:
            return self._create_error_response(
                f"Fortification already at max level for terrain {terrain_type.value}: {current_level}/{max_level}",
            )

        # 执行工事建设
        territory_system = self._get_territory_system()
        if territory_system:
            success = territory_system.build_fortification(unit_id, (col, row))
            if success:
                new_level = current_level + 1
                defense_bonus = self._calculate_fortification_defense_bonus(new_level)

                return {
                    "success": True,
                    "result": True,
                    "details": f"Unit {unit_id} built fortification at {(col, row)}, increasing level to {new_level}/{max_level}",
                    "message": f"Unit {unit_id} built fortification at {(col, row)}, increasing level to {new_level}/{max_level}",
                    # "defense_bonus": defense_bonus,
                    # "terrain_type": terrain_type.value,
                    "remaining_action_points": action_points.current_ap - 1,
                }
            else:
                return self._create_error_response(
                    "Cannot build fortification at this position"
                )
        else:
            return self._create_error_response("Territory system not available")

    def handle_skill_action(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理技能动作"""
        unit_id = params.get("unit_id")
        skill_name = params.get("skill_name")
        target = params.get("target")

        if not isinstance(unit_id, int):
            return self._create_error_response("unit_id must be integer")

        if not isinstance(skill_name, str):
            return self._create_error_response("skill_name must be string")

        # 检查单位存在性
        unit = self.world.get_component(unit_id, Unit)
        if not unit:
            return self._create_error_response(f"Unit {unit_id} not found")

        # 阵营回合权限验证
        permission_error = self._validate_faction_turn_permission(unit_id, "skill")
        if permission_error:
            return permission_error

        # 检查技能组件
        unit_skills = self.world.get_component(unit_id, UnitSkills)
        skill_points = self.world.get_component(unit_id, SkillPoints)

        if not unit_skills:
            return self._create_error_response("Unit has no skills")

        if not skill_points:
            return self._create_error_response("Unit has no skill points")

        # 检查技能是否可用（UnitSkills控制技能列表和冷却）
        if not unit_skills.can_use_skill(skill_name):
            if skill_name not in unit_skills.available_skills:
                return self._create_error_response(f"Skill {skill_name} not available")
            else:
                cooldown = unit_skills.skill_cooldowns.get(skill_name, 0)
                return self._create_error_response(
                    f"Skill {skill_name} on cooldown: {cooldown} turns"
                )

        # 检查技能点是否足够（SkillPoints控制消耗）
        if not skill_points.can_use_skill(skill_name, 1):
            return self._create_error_response(
                f"Insufficient skill points: need 1, have {skill_points.current_sp}",
            )

        # 检查动作点
        action_points = self.world.get_component(unit_id, ActionPoints)
        if not action_points or not action_points.can_perform_action(ActionType.SKILL):
            return self._create_error_response(
                f"Insufficient action points for skill: need 2, have {action_points.current_ap if action_points else 0}",
            )

        # 检查地形和技能要求
        unit_pos = self.world.get_component(unit_id, HexPosition)
        if unit_pos:
            current_terrain = self._get_terrain_at_position(
                (unit_pos.col, unit_pos.row)
            )
            skill_result = self._execute_terrain_skill(
                unit_id, skill_name, current_terrain, target
            )

            if skill_result["result"]:
                # 消耗资源：多层次资源系统
                # 1. 消耗行动点（决策层）
                action_points.consume_ap(ActionType.SKILL)

                # 2. 消耗技能点（执行层）
                skill_points.use_skill(skill_name, 1, skill_result.get("cooldown", 0))

                # 3. 设置冷却时间（通过UnitSkills）
                unit_skills.use_skill(skill_name, skill_result.get("cooldown", 0))

                return {
                    "success": True,
                    "result": True,
                    "message": f"Unit {unit_id} used skill {skill_name}",
                    "details": f"Unit {unit_id} used skill {skill_name}",
                    "skill_result": skill_result,
                    "remaining_action_points": action_points.current_ap,
                    "remaining_skill_points": skill_points.current_sp,
                }
            else:
                return self._create_error_response(
                    skill_result.get("error", "Skill execution failed")
                )
        else:
            return self._create_error_response("Unit position not found")

    # ==================== Observation ====================

    def handle_observation_action(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle unit observation."""
        unit_id = params.get("unit_id")
        observation_level = params.get("observation_level", "basic")

        if not isinstance(unit_id, int):
            return self._create_error_response("unit_id must be integer")

        # 检查单位存在性
        unit = self.world.get_component(unit_id, Unit)
        if not unit:
            return self._create_error_response(f"Unit {unit_id} not found")

        # Get unit info
        unit_info = self._get_detailed_unit_info(unit_id)

        # Get visible environment
        visible_environment = self._get_visible_environment(unit_id, observation_level)

        result = {
            "success": True,
            "result": True,
            "unit_info": unit_info,
            "visible_environment": visible_environment,
        }

        # Add extras based on observation level
        if observation_level in ["detailed", "tactical"]:
            result["tactical_info"] = self._get_tactical_info(unit_id)

        return result

    # ==================== Faction control ====================

    def handle_faction_state(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get high-level faction state."""
        faction_str = params.get("faction")

        if not faction_str:
            return self._create_error_response("faction parameter required")

        try:
            faction = Faction(faction_str)
            print(f"Handling faction state for {faction.value}")
        except ValueError:
            return self._create_error_response(f"Invalid faction: {faction_str}")

        # Get all units for faction
        faction_units = self._get_faction_units(faction)

        # Compute faction statistics
        total_units_count = len(faction_units)
        alive_units = [u for u in faction_units if self._is_unit_alive(u)]
        alive_units_count = len(alive_units)

        # 计算可行动单位（存活且有行动点）
        actionable_units = [u for u in alive_units if self._can_unit_take_action(u)]
        actionable_units_count = len(actionable_units)

        # Get current faction status
        faction_status = self._get_faction_status(faction)

        print(f"[FACTION_STATE] Completed for {faction.value}")
        return {
            "success": True,
            "result": True,
            "state": faction_status,
            "faction": faction.value,
            "total_units": total_units_count,
            "alive_units": alive_units_count,  # 存活单位数（人数>0）
            "actionable_units": actionable_units_count,  # 可行动单位数（存活且有行动点）
            "units": [
                self._get_detailed_unit_info(unit_id) for unit_id in alive_units[:10]
            ],  # 返回存活单位的详细信息
        }

    def handle_action_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Return concise documentation for available actions."""
        action_docs = {
            "actions": {
                "move": {
                    "description": "Move a unit to target position (may repeat until AP is exhausted)",
                    "parameters": {
                        "unit_id": {
                            "type": "int",
                            "required": True,
                            "description": "ID of the moving unit (must be alive)",
                        },
                        "target_position": {
                            "type": "object",
                            "required": True,
                            "description": "Target position (col/row)",
                            "properties": {
                                "col": {"type": "int", "description": "column"},
                                "row": {"type": "int", "description": "row"},
                            },
                        },
                    },
                },
                "attack": {
                    "description": "Attack a target enemy unit (may repeat until AP is exhausted)",
                    "parameters": {
                        "unit_id": {
                            "type": "int",
                            "required": True,
                            "description": "Attacker unit ID",
                        },
                        "target_id": {
                            "type": "int",
                            "required": True,
                            "description": "Target unit ID",
                        },
                    },
                },
                "get_faction_state": {
                    "description": "Get state for a faction: surviving unit positions and remaining strength",
                    "parameters": {
                        "faction": {
                            "type": "string",
                            "required": True,
                            "description": "Faction name (wei | shu | wu)",
                        }
                    },
                },
                "end_turn": {
                    "description": "End the current faction's turn and pass control to the next faction. After ending the turn, no further actions (such as move, attack, etc.) can be performed by this faction until their next turn; only observation and information queries are allowed. Use this action when you have completed all desired actions for your faction in the current turn. The optional 'force' parameter can be used to forcibly end the turn in special cases (e.g., deadlock or error).",
                    "parameters": {
                        "faction": {
                            "type": "string",
                            "required": True,
                            "description": "Your current faction (wei | shu | wu)",
                        },
                        "force": {
                            "type": "bool",
                            "required": False,
                            "description": "Force end turn (only use in special situations, default is False)",
                            "default": False,
                        },
                    },
                    "prerequisites": ["Game running", "Current faction's turn"],
                },
            },
        }

        return {"success": True, "result": True, **action_docs}

    def handle_action_list_full(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Return full documentation for available actions."""
        action_docs = {
            "total_actions": len(self.action_handlers),
            "actions": {
                # Unit control
                "move": {
                    "category": "unit_control",
                    "description": "Move a unit to the target position",
                    "parameters": {
                        "unit_id": {
                            "type": "int",
                            "required": True,
                            "description": "Unit ID",
                        },
                        "target_position": {
                            "type": "object",
                            "required": True,
                            "description": "Target position",
                            "properties": {
                                "col": {"type": "int", "description": "column"},
                                "row": {"type": "int", "description": "row"},
                            },
                        },
                    },
                    "returns": {
                        "success": {
                            "type": "bool",
                            "description": "Whether execution succeeded",
                        },
                        "message": {"type": "string", "description": "Result message"},
                        "resource_consumption": {
                            "type": "object",
                            "description": "Resource consumption details",
                        },
                        "remaining_resources": {
                            "type": "object",
                            "description": "Remaining resources",
                        },
                    },
                    "prerequisites": [
                        "Unit exists",
                        "Sufficient action & movement points",
                        "Target reachable",
                        "Valid unit status",
                    ],
                },
                "attack": {
                    "category": "unit_control",
                    "description": "Attack a target enemy unit",
                    "parameters": {
                        "unit_id": {
                            "type": "int",
                            "required": True,
                            "description": "Attacker unit ID",
                        },
                        "target_id": {
                            "type": "int",
                            "required": True,
                            "description": "Target unit ID",
                        },
                    },
                    "prerequisites": [
                        "Unit exists",
                        "Target in range",
                        "Enemy faction",
                        "Sufficient action points",
                    ],
                },
                "rest": {
                    "category": "unit_control",
                    "description": "Unit rests and recovers",
                    "parameters": {
                        "unit_id": {
                            "type": "int",
                            "required": True,
                            "description": "Unit ID",
                        }
                    },
                    "prerequisites": ["Unit exists"],
                },
                "occupy": {
                    "category": "unit_control",
                    "description": "Occupy a tile; consumes AP but not construction points",
                    "parameters": {
                        "unit_id": {
                            "type": "int",
                            "required": True,
                            "description": "Unit ID",
                        },
                        "position": {
                            "type": "object",
                            "required": True,
                            "description": "Target position",
                            "properties": {
                                "col": {"type": "int", "description": "column"},
                                "row": {"type": "int", "description": "row"},
                            },
                        },
                    },
                    "prerequisites": [
                        "Unit exists",
                        "Tile not already friendly",
                        "Current or adjacent tile",
                        "Sufficient action points",
                    ],
                },
                "fortify": {
                    "category": "unit_control",
                    "description": "Build fortification on friendly tile; increases defense; consumes CP and AP",
                    "parameters": {
                        "unit_id": {
                            "type": "int",
                            "required": True,
                            "description": "Unit ID",
                        },
                        "position": {
                            "type": "object",
                            "required": True,
                            "description": "Position to fortify",
                        },
                    },
                    "prerequisites": [
                        "Unit exists",
                        "Tile friendly",
                        "Below max fortification level",
                        "Terrain allows",
                        "Sufficient AP and CP",
                    ],
                },
                "skill": {
                    "category": "unit_control",
                    "description": "Use a unit skill",
                    "parameters": {
                        "unit_id": {
                            "type": "int",
                            "required": True,
                            "description": "Unit ID",
                        },
                        "skill_name": {
                            "type": "string",
                            "required": True,
                            "description": "Skill name",
                        },
                        "target": {
                            "type": "any",
                            "required": False,
                            "description": "Skill target (optional)",
                        },
                    },
                    "prerequisites": [
                        "Unit exists",
                        "Skill available",
                        "Not on cooldown",
                        "Sufficient action points",
                    ],
                },
                # Observation
                "observation": {
                    "category": "observation",
                    "description": "Get unit observation info",
                    "parameters": {
                        "unit_id": {
                            "type": "int",
                            "required": True,
                            "description": "Unit ID",
                        },
                        "observation_level": {
                            "type": "string",
                            "required": False,
                            "description": "Observation level",
                            "default": "basic",
                            "options": ["basic", "detailed", "tactical"],
                        },
                    },
                    "prerequisites": ["Unit exists"],
                },
                # Faction
                "get_faction_state": {
                    "category": "faction_control",
                    "description": "Get overall faction status including battles and outcomes",
                    "parameters": {
                        "faction": {
                            "type": "string",
                            "required": True,
                            "description": "Faction name (wei/shu/wu)",
                        }
                    },
                    "returns": {
                        "success": {
                            "type": "bool",
                            "description": "Whether execution succeeded",
                        },
                        "state": {
                            "type": "string",
                            "description": "Faction state: active/in_battle/victory/defeat/eliminated/draw",
                        },
                        "status_details": {
                            "type": "object",
                            "description": "Detailed status info",
                        },
                        "faction": {"type": "string", "description": "Faction name"},
                        "total_units": {
                            "type": "int",
                            "description": "Total unit count",
                        },
                        "alive_units": {
                            "type": "int",
                            "description": "Alive unit count",
                        },
                        "units": {
                            "type": "array",
                            "description": "Detailed unit info list",
                        },
                    },
                    "prerequisites": ["Valid faction name"],
                },
                # System
                "get_action_list": {
                    "category": "system",
                    "description": "Get concise docs for all actions",
                    "parameters": {},
                    "prerequisites": ["none"],
                },
                "end_turn": {
                    "category": "system",
                    "description": "End the current faction's turn and pass control to the next faction. After ending the turn, no further actions (such as move, attack, etc.) can be performed by this faction until their next turn; only observation and information queries are allowed. Use this action when you have completed all desired actions for your faction in the current turn. The optional 'force' parameter can be used to forcibly end the turn in special cases (e.g., deadlock or error).",
                    "parameters": {
                        "faction": {
                            "type": "string",
                            "required": True,
                            "description": "Your current faction (wei | shu | wu)",
                        },
                        "force": {
                            "type": "bool",
                            "required": False,
                            "description": "Force end turn (only use in special situations, default is False)",
                            "default": False,
                        },
                    },
                    "prerequisites": ["Game running", "Current faction's turn"],
                },
            },
            "usage_examples": {
                "move_unit": {
                    "action": "move",
                    "params": {"unit_id": 123, "target_position": {"col": 5, "row": 8}},
                },
                "attack_enemy": {
                    "action": "attack",
                    "params": {"unit_id": 123, "target_id": 456},
                },
                "rest_unit": {
                    "action": "rest",
                    "params": {"unit_id": 123},
                },
                "occupy_territory": {
                    "action": "occupy",
                    "params": {"unit_id": 123, "position": {"col": 5, "row": 8}},
                },
                "build_fortification": {
                    "action": "fortify",
                    "params": {"unit_id": 123, "position": {"col": 5, "row": 8}},
                },
                "use_skill": {
                    "action": "skill",
                    "params": {"unit_id": 123, "skill_name": "hide", "target": None},
                },
                "observe_surroundings": {
                    "action": "observation",
                    "params": {"unit_id": 123, "observation_level": "detailed"},
                },
                "get_faction_overview": {
                    "action": "get_faction_state",
                    "params": {"faction": "wei"},
                },
                "finish_turn": {
                    "action": "end_turn",
                    "params": {"faction": "wei", "force": False},
                },
            },
        }

        return {"success": True, "result": True, **action_docs}

    def handle_end_turn(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle end-turn action for the current faction."""
        faction_str = params.get("faction")
        force = params.get("force", False)

        if not faction_str:
            return self._create_error_response("faction parameter required")

        try:
            faction = Faction(faction_str)
        except ValueError:
            return self._create_error_response(f"Invalid faction: {faction_str}")

        # Check game state
        game_state = self.world.get_singleton_component(GameState)
        if not game_state:
            return self._create_error_response("Game not initialized")

        if game_state.game_over:
            return self._create_error_response("Game is already over")

        # Get turn system
        turn_system = self._get_turn_system()
        if not turn_system:
            return self._create_error_response("Turn system not available")

        # Ensure it's the current player's turn
        current_player = self._get_current_player()
        if not current_player or current_player.faction != faction:
            return self._create_error_response(
                f"Not {faction.value}'s turn. Current turn: {current_player.faction.value if current_player else 'unknown'}",
            )

        # Execute end turn
        success = turn_system.agent_end_turn()

        if success:
            # Get new current player
            new_current_player = self._get_current_player()
            next_faction = (
                new_current_player.faction.value if new_current_player else "unknown"
            )

            return {
                "success": True,
                "result": True,
                "details": f"Turn ended for faction {faction.value}",
                "message": f"Turn ended for faction {faction.value}",
                "turn_summary": {
                    "ended_faction": faction.value,
                    "next_faction": next_faction,
                    "turn_number": game_state.turn_number,
                    "forced": force,
                },
                "game_status": {
                    "game_running": not game_state.game_over,
                    "current_turn": game_state.turn_number,
                    "current_player": next_faction,
                },
            }
        else:
            return self._create_error_response(
                f"Failed to end turn for faction {faction.value}"
            )

    # ==================== Helper methods ====================

    def _create_error_response(
        self, message: str, extra_data: Dict = None
    ) -> Dict[str, Any]:
        """Create a structured error response (uniform schema)."""
        response = {
            "success": False,
            "result": False,
            "details": message,
            "message": message,
        }

        if extra_data:
            response.update(extra_data)

        return response

    def _validate_faction_turn_permission(
        self, unit_id: int, action_name: str = "action"
    ) -> Dict[str, Any]:
        """验证指定单位的阵营是否有当前回合的操作权限

        Args:
            unit_id: 单位ID
            action_name: 动作名称，用于错误信息

        Returns:
            Dict: 包含验证结果的字典，如果验证失败会返回错误响应，成功返回None
        """
        # 检查单位是否存在
        unit = self.world.get_component(unit_id, Unit)
        if not unit:
            return self._create_error_response(
                f"Unit {unit_id} not found", {"unit_id": unit_id, "action": action_name}
            )

        # 获取当前轮到行动的阵营
        current_player = self._get_current_player()
        if not current_player:
            return self._create_error_response(
                "Unable to determine current player",
                {"unit_id": unit_id, "action": action_name},
            )

        # 检查是否是该阵营的回合
        if unit.faction != current_player.faction:
            return self._create_error_response(
                f"Not {unit.faction.value}'s turn to act. Current turn: {current_player.faction.value}",
                {
                    "unit_id": unit_id,
                    "unit_faction": unit.faction.value,
                    "current_turn_faction": current_player.faction.value,
                    "action": action_name,
                    "suggestion": f"Wait for {unit.faction.value}'s turn or switch to a {current_player.faction.value} unit",
                },
            )

        # 验证通过，返回None表示无错误
        return None

    def _get_detailed_unit_info(self, unit_id: int) -> Dict[str, Any]:
        """Get detailed unit information with safe fallbacks."""
        try:

            if not isinstance(unit_id, int) or unit_id <= 0:
                return {
                    "unit_id": unit_id,
                    "error": "Invalid unit_id",
                    "unit_type": "unknown",
                    "faction": "unknown",
                    "position": {"col": 0, "row": 0},
                    "unit_status": {
                        "current_count": 0,
                        "max_count": 0,
                        "health_percentage": 0.0,
                        "morale": "unknown",
                        "fatigue": "none",
                    },
                    "capabilities": {
                        "movement": 0,
                        "attack_range": 0,
                        "vision_range": 0,
                        "action_points": 0,
                        "max_action_points": 0,
                        "attack_points": 0,
                        "construction_points": 0,
                        "skill_points": 0,
                    },
                    "available_skills": [],
                }

            unit = self.world.get_component(unit_id, Unit)
            unit_count = self.world.get_component(unit_id, UnitCount)
            position = self.world.get_component(unit_id, HexPosition)
            movement_points = self.world.get_component(unit_id, MovementPoints)
            combat = self.world.get_component(unit_id, Combat)
            vision = self.world.get_component(unit_id, Vision)
            action_points = self.world.get_component(unit_id, ActionPoints)
            attack_points = self.world.get_component(unit_id, AttackPoints)
            construction_points = self.world.get_component(unit_id, ConstructionPoints)
            skill_points = self.world.get_component(unit_id, SkillPoints)
            unit_status = self.world.get_component(unit_id, UnitStatus)
            unit_skills = self.world.get_component(unit_id, UnitSkills)

            if not unit:
                return {
                    "unit_id": unit_id,
                    "error": "Unit not found",
                    "unit_type": "unknown",
                    "faction": "unknown",
                    "position": {"col": 0, "row": 0},
                    "unit_status": {
                        "current_count": 0,
                        "max_count": 0,
                        "health_percentage": 0.0,
                        "morale": "unknown",
                        "fatigue": "none",
                    },
                    "capabilities": {
                        "movement": 0,
                        "attack_range": 0,
                        "vision_range": 0,
                        "action_points": 0,
                        "max_action_points": 0,
                        "attack_points": 0,
                        "construction_points": 0,
                        "skill_points": 0,
                    },
                    "available_skills": [],
                }

            try:
                unit_type_value = unit.unit_type.value if unit.unit_type else "unknown"
            except (AttributeError, ValueError):
                unit_type_value = "unknown"

            try:
                faction_value = unit.faction.value if unit.faction else "unknown"
            except (AttributeError, ValueError):
                faction_value = "unknown"

            position_info = {"col": 0, "row": 0}
            if position:
                try:
                    position_info = {
                        "col": int(position.col) if hasattr(position, "col") else 0,
                        "row": int(position.row) if hasattr(position, "row") else 0,
                    }
                except (AttributeError, ValueError, TypeError):
                    position_info = {"col": 0, "row": 0}

            status_info = {
                "current_count": 0,
                "max_count": 0,
                "health_percentage": 0.0,
                "morale": "normal",
                "fatigue": "none",
            }

            if unit_count:
                try:
                    status_info.update(
                        {
                            "current_count": (
                                int(unit_count.current_count)
                                if hasattr(unit_count, "current_count")
                                else 0
                            ),
                            "max_count": (
                                int(unit_count.max_count)
                                if hasattr(unit_count, "max_count")
                                else 0
                            ),
                            "health_percentage": (
                                float(unit_count.ratio)
                                if hasattr(unit_count, "ratio")
                                else 0.0
                            ),
                        }
                    )
                except (AttributeError, ValueError, TypeError):
                    pass  # keep defaults

            if unit_status:
                try:
                    if (
                        hasattr(unit_status, "current_status")
                        and unit_status.current_status
                    ):
                        if hasattr(unit_status.current_status, "value"):
                            status_info["morale"] = str(
                                unit_status.current_status.value
                            )
                        else:
                            status_info["morale"] = str(unit_status.current_status)
                except (AttributeError, ValueError, TypeError):
                    status_info["morale"] = "normal"

            capabilities_info = {
                "movement": 0,
                "attack_range": 1,
                "vision_range": 2,
                "action_points": 0,
                "max_action_points": 2,
                "attack_points": 0,
                "construction_points": 0,
                "skill_points": 0,
            }

            if movement_points:
                try:
                    capabilities_info["movement"] = (
                        int(movement_points.current_mp)
                        if hasattr(movement_points, "current_mp")
                        else 0
                    )
                except (AttributeError, ValueError, TypeError):
                    pass

            if combat:
                try:
                    capabilities_info["attack_range"] = (
                        int(combat.attack_range)
                        if hasattr(combat, "attack_range")
                        else 1
                    )
                except (AttributeError, ValueError, TypeError):
                    pass

            if vision:
                try:
                    capabilities_info["vision_range"] = (
                        int(vision.range) if hasattr(vision, "range") else 2
                    )
                except (AttributeError, ValueError, TypeError):
                    pass

            if action_points:
                try:
                    capabilities_info.update(
                        {
                            "action_points": (
                                int(action_points.current_ap)
                                if hasattr(action_points, "current_ap")
                                else 0
                            ),
                            "max_action_points": (
                                int(action_points.max_ap)
                                if hasattr(action_points, "max_ap")
                                else 2
                            ),
                        }
                    )
                except (AttributeError, ValueError, TypeError):
                    pass

            if attack_points:
                try:
                    capabilities_info["attack_points"] = (
                        int(attack_points.normal_attacks)
                        if hasattr(attack_points, "normal_attacks")
                        else 0
                    )
                except (AttributeError, ValueError, TypeError):
                    pass

            if construction_points:
                try:
                    capabilities_info["construction_points"] = (
                        int(construction_points.current_cp)
                        if hasattr(construction_points, "current_cp")
                        else 0
                    )
                except (AttributeError, ValueError, TypeError):
                    pass

            if skill_points:
                try:
                    capabilities_info["skill_points"] = (
                        int(skill_points.current_sp)
                        if hasattr(skill_points, "current_sp")
                        else 0
                    )
                except (AttributeError, ValueError, TypeError):
                    pass

            available_skills = []
            if unit_skills:
                try:
                    if (
                        hasattr(unit_skills, "available_skills")
                        and unit_skills.available_skills
                    ):
                        available_skills = [
                            str(skill) for skill in unit_skills.available_skills
                        ]
                except (AttributeError, ValueError, TypeError):
                    available_skills = []

            return {
                "unit_id": unit_id,
                "unit_type": unit_type_value,
                "faction": faction_value,
                "position": position_info,
                "unit_status": status_info,
                "capabilities": capabilities_info,
                "available_skills": available_skills,
            }

        except Exception as e:
            # Return safe defaults on exception
            return {
                "unit_id": unit_id,
                "error": f"Failed to get unit info: {str(e)}",
                "unit_type": "unknown",
                "faction": "unknown",
                "position": {"col": 0, "row": 0},
                "unit_status": {
                    "current_count": 0,
                    "max_count": 0,
                    "health_percentage": 0.0,
                    "morale": "unknown",
                    "fatigue": "none",
                },
                "capabilities": {
                    "movement": 0,
                    "attack_range": 0,
                    "vision_range": 0,
                    "action_points": 0,
                    "max_action_points": 0,
                    "attack_points": 0,
                    "construction_points": 0,
                    "skill_points": 0,
                },
                "available_skills": [],
            }

    def _get_visible_environment(
        self, unit_id: int, observation_level: str
    ) -> List[Dict[str, Any]]:
        """Get visible environment around the unit."""
        vision = self.world.get_component(unit_id, Vision)
        if not vision:
            return []

        unit_position = self.world.get_component(unit_id, HexPosition)
        movement_points = self.world.get_component(unit_id, MovementPoints)
        unit_count = self.world.get_component(unit_id, UnitCount)
        combat = self.world.get_component(unit_id, Combat)
        unit = self.world.get_component(unit_id, Unit)
        current_pos = (unit_position.col, unit_position.row) if unit_position else None

        visible_tiles = []
        for pos in vision.visible_tiles:
            tile_info = {
                "position": {"col": pos[0], "row": pos[1]},
                "terrain": self._get_terrain_at_position(pos).value,
                "units": self._get_units_at_position(pos),
                "fortifications": self._get_current_fortification_level(pos),
                # Territory info
                "territory_control": self._get_territory_control_info(
                    pos, unit.faction if unit else None
                ),
                # Movement accessibility
                "movement_accessibility": self._get_movement_accessibility_info(
                    unit_id, current_pos, pos, movement_points, unit_count
                ),
                # Attack range info
                "attack_range_info": self._get_attack_range_info(
                    current_pos, pos, combat
                ),
            }

            visible_tiles.append(tile_info)

        return visible_tiles

    def _calculate_movement_info(
        self,
        unit_id: int,
        current_pos: Tuple[int, int],
        target_pos: Tuple[int, int],
        movement_points: MovementPoints,
        unit_count: UnitCount,
    ) -> Dict[str, Any]:
        """Compute movement info from current to target tile."""

        if current_pos == target_pos:
            return {
                "reachable": True,
                "is_current_position": True,
                "movement_cost": 0,
                "path_length": 0,
                "terrain_movement_cost": self._get_terrain_movement_cost(target_pos),
                "effective_movement_range": movement_points.get_effective_movement(
                    unit_count
                ),
                "current_movement_points": movement_points.current_mp,
                # "path": [current_pos],
            }

        # Effective movement (consider strength)
        effective_movement = movement_points.get_effective_movement(unit_count)

        # 获取障碍物和路径
        obstacles = self._get_obstacles()
        from ..utils.hex_utils import PathFinding

        try:
            # 尝试寻找路径
            path = PathFinding.find_path(
                current_pos, target_pos, obstacles, effective_movement
            )

            if path and len(path) > 1:
                # 计算路径总消耗
                total_movement_cost = self._calculate_total_movement_cost(path)

                # 检查是否可达
                reachable = total_movement_cost <= movement_points.current_mp

                return {
                    "reachable": reachable,
                    "is_current_position": False,
                    "movement_cost": total_movement_cost,
                    "path_length": len(path) - 1,
                    "terrain_movement_cost": self._get_terrain_movement_cost(
                        target_pos
                    ),
                    "effective_movement_range": effective_movement,
                    "current_movement_points": movement_points.current_mp,
                    # "path": path,
                    "reachable_reason": (
                        "sufficient_movement_points"
                        if reachable
                        else f"need_{total_movement_cost}_have_{movement_points.current_mp}"
                    ),
                }
            else:
                # No valid path
                return {
                    "reachable": False,
                    "is_current_position": False,
                    "movement_cost": -1,
                    "path_length": -1,
                    "terrain_movement_cost": self._get_terrain_movement_cost(
                        target_pos
                    ),
                    "effective_movement_range": effective_movement,
                    "current_movement_points": movement_points.current_mp,
                    # "path": [],
                    "reachable_reason": "no_valid_path",
                }
        except Exception as e:
            # Path calculation error
            return {
                "reachable": False,
                "is_current_position": False,
                "movement_cost": -1,
                "path_length": -1,
                "terrain_movement_cost": self._get_terrain_movement_cost(target_pos),
                "effective_movement_range": effective_movement,
                "current_movement_points": movement_points.current_mp,
                # "path": [],
                "reachable_reason": f"path_calculation_error: {str(e)}",
            }

    def _get_tactical_info(self, unit_id: int) -> Dict[str, Any]:
        """Get tactical info (placeholder)."""
        # 简化实现
        return {"threats": [], "opportunities": [], "movement_options": []}

    def _get_faction_units(self, faction: Faction) -> List[int]:
        """Get all unit IDs belonging to a faction."""
        units = []
        for entity in self.world.query().with_component(Unit).entities():
            unit = self.world.get_component(entity, Unit)
            if unit and unit.faction == faction:
                units.append(entity)
        return units

    def _is_unit_alive(self, unit_id: int) -> bool:
        """Check if unit is alive (count > 0)."""
        unit_count = self.world.get_component(unit_id, UnitCount)
        return unit_count and unit_count.current_count > 0

    def _can_unit_take_action(self, unit_id: int) -> bool:
        """Check if unit can act (alive and has AP)."""
        if not self._is_unit_alive(unit_id):
            return False

        action_points = self.world.get_component(unit_id, ActionPoints)
        return action_points and action_points.current_ap > 0

    def _calculate_territory_control(self, faction: Faction) -> int:
        """Calculate territory control percentage (placeholder)."""
        # 简化实现
        return 30  # fixed value; real calculation TBD

    def _calculate_resource_summary(self, faction_units: List[int]) -> Dict[str, Any]:
        """Calculate resource summary (simplified)."""
        total_manpower = 0
        for unit_id in faction_units:
            unit_count = self.world.get_component(unit_id, UnitCount)
            if unit_count:
                total_manpower += unit_count.current_count

        return {
            "total_manpower": total_manpower,
            "fortification_points": 0,  # simplified
            "controlled_cities": 0,  # simplified
        }

    def _get_strategic_summary(self, faction: Faction) -> Dict[str, Any]:
        """Get strategic summary (simplified)."""
        return {
            "active_battles": 0,
            "territory_threats": [],
            "expansion_opportunities": [],
        }

    # ==================== System getters ====================

    def _get_movement_system(self):
        """Get MovementSystem instance if present."""
        for system in self.world.systems:
            if system.__class__.__name__ == "MovementSystem":
                return system
        return None

    def _get_combat_system(self):
        """Get CombatSystem instance if present."""
        for system in self.world.systems:
            if system.__class__.__name__ == "CombatSystem":
                return system
        return None

    def _get_action_system(self):
        """Get ActionSystem instance if present."""
        for system in self.world.systems:
            if system.__class__.__name__ == "ActionSystem":
                return system
        return None

    def _get_territory_system(self):
        """Get TerritorySystem instance if present."""
        for system in self.world.systems:
            if system.__class__.__name__ == "TerritorySystem":
                return system
        return None

    def _get_turn_system(self):
        """Get TurnSystem instance if present."""
        for system in self.world.systems:
            if system.__class__.__name__ == "TurnSystem":
                return system
        return None

    def _get_current_player(self):
        """Get current player (by faction) from GameState."""
        # turn_manager = self.world.get_singleton_component(TurnManager)
        # if turn_manager:
        #     current_player_entity = turn_manager.get_current_player()
        #     if current_player_entity:
        #         return self.world.get_component(current_player_entity, Player)

        # Fallback: obtain current player via GameState
        game_state = self.world.get_singleton_component(GameState)
        if game_state:
            for entity in self.world.query().with_component(Player).entities():
                player = self.world.get_component(entity, Player)
                if player and player.faction == game_state.current_player:
                    return player
        return None

    # ==================== Game logic helpers ====================

    def _get_obstacles(self) -> Set[Tuple[int, int]]:
        """Get movement obstacles - only units as blockers."""
        obstacles = set()
        # Collect all unit positions as obstacles
        for entity in self.world.query().with_all(HexPosition, Unit).entities():
            pos = self.world.get_component(entity, HexPosition)
            if pos:
                obstacles.add((pos.col, pos.row))
        return obstacles

    def _get_obstacles_excluding_unit(
        self, exclude_unit_id: int
    ) -> Set[Tuple[int, int]]:
        """Get obstacles excluding a unit - other units + impassable terrain."""
        obstacles = set()
        # Collect unit positions as obstacles but exclude the given unit
        for entity in self.world.query().with_all(HexPosition, Unit).entities():
            if entity == exclude_unit_id:
                continue  # skip moving unit itself
            pos = self.world.get_component(entity, HexPosition)
            if pos:
                obstacles.add((pos.col, pos.row))

        # Include impassable terrain (e.g., water) as obstacles, matching MovementSystem
        map_data = self.world.get_singleton_component(MapData)
        if map_data:
            for (q, r), tile_entity in map_data.tiles.items():
                terrain = self.world.get_component(tile_entity, Terrain)
                if terrain and terrain.terrain_type == TerrainType.WATER:
                    obstacles.add((q, r))

        print(
            f"[DEBUG] Obstacles (including water): {len(obstacles)} (excluding unit {exclude_unit_id})"
        )
        return obstacles

    def _get_adjacent_free_positions(
        self, center_pos: Tuple[int, int], obstacles: Set[Tuple[int, int]]
    ) -> List[Tuple[int, int]]:
        """Get unblocked adjacent positions around the given tile."""
        from ..utils.hex_utils import HexMath

        col, row = center_pos

        # Six adjacent axial directions
        adjacent_positions = []
        directions = [(1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1)]

        for dx, dy in directions:
            adj_pos = (col + dx, row + dy)
            if adj_pos not in obstacles:
                adjacent_positions.append(adj_pos)

        return adjacent_positions

    def _calculate_total_movement_cost(self, path: List[Tuple[int, int]]) -> int:
        """Compute total movement cost for a path."""
        total_cost = 0
        for pos in path[1:]:  # skip origin
            terrain_cost = self._get_terrain_movement_cost(pos)
            total_cost += terrain_cost
        return total_cost

    def _get_terrain_movement_cost(self, position: Tuple[int, int]) -> int:
        """Get terrain movement cost (movement points)."""
        from ..prefabs.config import GameConfig

        terrain_type = self._get_terrain_at_position(position)
        terrain_effect = GameConfig.TERRAIN_EFFECTS.get(terrain_type)
        return terrain_effect.movement_cost if terrain_effect else 1

    def _get_path_terrain_breakdown(
        self, path: List[Tuple[int, int]]
    ) -> List[Dict[str, Any]]:
        """Break down terrain and cost for each step along a path."""
        breakdown = []

        for i, pos in enumerate(path):
            if i == 0:  # skip origin
                continue

            terrain_type = self._get_terrain_at_position(pos)
            movement_cost = self._get_terrain_movement_cost(pos)

            breakdown.append(
                {
                    "position": {"col": pos[0], "row": pos[1]},
                    "terrain": terrain_type.value,
                    "movement_cost": movement_cost,
                    "step": i,
                }
            )

        return breakdown

    def _get_terrain_at_position(self, position: Tuple[int, int]) -> TerrainType:
        """Get terrain type at tile position."""
        map_data = self.world.get_singleton_component(MapData)
        if not map_data:
            return TerrainType.PLAIN

        tile_entity = map_data.tiles.get(position)
        if not tile_entity:
            return TerrainType.PLAIN

        terrain = self.world.get_component(tile_entity, Terrain)
        return terrain.terrain_type if terrain else TerrainType.PLAIN

    def _is_position_within_map_bounds(self, col: int, row: int) -> bool:
        """Check whether a position is within map bounds."""
        from ..prefabs.config import GameConfig

        # Center-based coordinate system: for width/height W,H
        # center = W // 2; valid col,row in [-center, center-1]
        center = GameConfig.MAP_WIDTH // 2
        min_coord = -center
        max_coord = center - 1

        return (min_coord <= col <= max_coord) and (min_coord <= row <= max_coord)

    def _get_terrain_attack_bonus(
        self, position: Tuple[int, int], faction: Faction
    ) -> float:
        """Get attack bonus from terrain/territory (fractional)."""
        territory_system = self._get_territory_system()
        if territory_system:
            return (
                territory_system.get_territory_attack_bonus(position, faction) / 10.0
            )  # convert to fraction
        return 0.0

    def _get_max_fortification_level(self, terrain_type: TerrainType) -> int:
        """Get max fortification level allowed by terrain type."""
        level_limits = {
            TerrainType.PLAIN: 1,
            TerrainType.FOREST: 2,
            TerrainType.HILL: 2,
            TerrainType.MOUNTAIN: 2,
            TerrainType.CITY: 3,
            TerrainType.URBAN: 3,
            TerrainType.WATER: 0,
        }
        return level_limits.get(terrain_type, 1)

    def _get_current_fortification_level(self, position: Tuple[int, int]) -> int:
        """Get current fortification level at a tile."""
        map_data = self.world.get_singleton_component(MapData)
        if not map_data:
            return 0

        tile_entity = map_data.tiles.get(position)
        if not tile_entity:
            return 0

        territory_control = self.world.get_component(tile_entity, TerritoryControl)
        if territory_control and territory_control.fortified:
            return territory_control.fortification_level
        return 0

    def _calculate_fortification_defense_bonus(self, level: int) -> float:
        """Calculate defense bonus provided by fortification level."""
        return level * 0.2  # +20% defense per level

    def _get_units_at_position(self, position: Tuple[int, int]) -> List[Dict[str, Any]]:
        """Get all units at a given position."""
        units = []
        for entity in self.world.query().with_all(HexPosition, Unit).entities():
            pos = self.world.get_component(entity, HexPosition)
            unit = self.world.get_component(entity, Unit)

            if pos and unit and (pos.col, pos.row) == position:
                units.append(
                    {
                        "unit_id": entity,
                        "unit_type": unit.unit_type.value,
                        "faction": unit.faction.value,
                    }
                )

        return units

    def _execute_terrain_skill(
        self, unit_id: int, skill_name: str, terrain: TerrainType, target: Any
    ) -> Dict[str, Any]:
        """Execute terrain-dependent skill, returning effect/cooldown."""
        # Skill execution mapping
        skill_effects = {
            "hide": {
                "allowed_terrains": [
                    TerrainType.FOREST,
                    TerrainType.MOUNTAIN,
                    TerrainType.HILL,
                ],
                "effect": "Unit gains concealment",
                "cooldown": 0,
                "success": terrain
                in [TerrainType.FOREST, TerrainType.MOUNTAIN, TerrainType.HILL],
            },
            "rockslide": {
                "allowed_terrains": [TerrainType.MOUNTAIN],
                "effect": "Area damage to enemies on plains",
                "cooldown": 3,
                "success": terrain == TerrainType.MOUNTAIN,
            },
            "arrow_evasion": {
                "allowed_terrains": [TerrainType.HILL],
                "effect": "Reduce archer damage by 90%",
                "cooldown": 0,
                "success": terrain == TerrainType.HILL,
            },
        }

        skill_data = skill_effects.get(skill_name)
        if not skill_data:
            return {"success": False, "error": f"Unknown skill: {skill_name}"}

        if not skill_data["success"]:
            return {
                "success": False,
                "error": f"Skill {skill_name} cannot be used on terrain {terrain.value}",
            }

        return {
            "success": True,
            "effect": skill_data["effect"],
            "cooldown": skill_data["cooldown"],
        }

    def _get_terrain_occupation_bonus(self, terrain_type: TerrainType) -> float:
        """Get occupation bonus for a terrain type."""
        occupation_bonuses = {
            TerrainType.PLAIN: 0.0,
            TerrainType.FOREST: 0.1,  # concealment bonus
            TerrainType.HILL: 0.15,  # vision bonus
            TerrainType.MOUNTAIN: 0.2,  # defense bonus
            TerrainType.CITY: 0.3,  # resource bonus
            TerrainType.URBAN: 0.25,  # population bonus
            TerrainType.WATER: 0.0,  # cannot be occupied
        }
        return occupation_bonuses.get(terrain_type, 0.0)

    def _get_terrain_resource_value(self, terrain_type: TerrainType) -> int:
        """Get resource value for a terrain type (simplified)."""
        resource_values = {
            TerrainType.PLAIN: 2,  # basic agriculture
            TerrainType.FOREST: 1,  # timber
            TerrainType.HILL: 1,  # minerals
            TerrainType.MOUNTAIN: 1,  # rare minerals
            TerrainType.CITY: 5,  # high value
            TerrainType.URBAN: 3,  # medium value
            TerrainType.WATER: 0,  # none
        }
        return resource_values.get(terrain_type, 1)

    def _get_faction_status(self, faction: Faction) -> str:
        """Get faction status: in_battle, victory, defeat, eliminated, active, or draw."""
        # Game over check
        game_state = self.world.get_singleton_component(GameState)
        if game_state and game_state.game_over:
            # Winner check
            if game_state.winner == faction:
                return "victory"
            elif game_state.winner is not None:
                return "defeat"
            else:
                return "draw"

        # Winner component check
        from ..components.game_over import Winner

        winner_component = self.world.get_singleton_component(Winner)
        if winner_component and winner_component.faction is not None:
            if winner_component.faction == faction:
                return "victory"
            else:
                return "defeat"

        # During game, if faction has no living units → eliminated
        alive_units = [
            u for u in self._get_faction_units(faction) if self._is_unit_alive(u)
        ]
        if not alive_units:
            return "eliminated"  # 已被消灭

        # If other factions have living units, inspect recent battles to infer in_battle
        other_factions_exist = False
        for other_faction in Faction:
            if other_faction != faction:
                other_alive_units = [
                    u
                    for u in self._get_faction_units(other_faction)
                    if self._is_unit_alive(u)
                ]
                if other_alive_units:
                    other_factions_exist = True
                    break

        if other_factions_exist:
            # 检查是否有最近的战斗活动
            battle_log = self.world.get_singleton_component(BattleLog)
            if battle_log and hasattr(battle_log, "entries") and battle_log.entries:
                # Recent battles imply in_battle
                recent_battles = battle_log.entries[-3:]
                for entry in recent_battles:
                    if (
                        hasattr(entry, "attacker_faction")
                        and entry.attacker_faction == faction
                    ) or (
                        hasattr(entry, "defender_faction")
                        and entry.defender_faction == faction
                    ):
                        return "in_battle"

            return "active"
        else:
            return "victory"

    def _get_territory_control_info(
        self, position: Tuple[int, int], unit_faction: Faction = None
    ) -> Dict[str, Any]:
        """Get territory control info for a tile."""
        territory_system = self._get_territory_system()
        if not territory_system:
            return {
                "controlled_by": None,
                "is_friendly": False,
                "is_enemy": False,
                "is_neutral": True,
                "can_occupy": False,
                "occupation_bonus": 0.0,
            }

        # Get controlling faction
        current_control = territory_system.get_territory_control(position)

        # Determine relation to unit faction
        is_friendly = (
            current_control == unit_faction
            if current_control and unit_faction
            else False
        )
        is_enemy = (
            current_control != unit_faction
            if current_control and unit_faction
            else False
        )
        is_neutral = current_control is None

        # 判断是否可以占领（未被己方控制的地块）
        can_occupy = not is_friendly if unit_faction else False

        # 获取地形占领加成
        terrain_type = self._get_terrain_at_position(position)
        occupation_bonus = self._get_terrain_occupation_bonus(terrain_type)

        return {
            "controlled_by": current_control.value if current_control else None,
            # "is_friendly": is_friendly,
            # "is_enemy": is_enemy,
            # "is_neutral": is_neutral,
            # "can_occupy": can_occupy,
            # "occupation_bonus": occupation_bonus,
        }

    def _get_movement_accessibility_info(
        self,
        unit_id: int,
        current_pos: Tuple[int, int],
        target_pos: Tuple[int, int],
        movement_points: MovementPoints,
        unit_count: UnitCount,
    ) -> Dict[str, Any]:

        if not current_pos or not movement_points or not unit_count:
            return {
                "reachable": False,
                "reason": "missing_movement_components",
                "movement_cost": -1,
                "remaining_movement": 0,
            }

        if current_pos == target_pos:
            return {
                "reachable": True,
                "reason": "current_position",
                "movement_cost": 0,
                "remaining_movement": movement_points.current_mp,
                "is_current_position": True,
            }

        effective_movement = movement_points.get_effective_movement(unit_count)

        obstacles = self._get_obstacles_excluding_unit(unit_id)
        if target_pos in obstacles:
            return {
                "reachable": False,
                "reason": "position_occupied",
                "movement_cost": -1,
                "remaining_movement": movement_points.current_mp,
                "blocked_by": "other_unit",
            }

        # Try to find a path
        try:
            from ..utils.hex_utils import PathFinding

            path = PathFinding.find_path(
                current_pos, target_pos, obstacles, effective_movement
            )

            if path and len(path) > 1:
                # Calculate total movement cost
                total_movement_cost = self._calculate_total_movement_cost(path)

                # Check if reachable
                reachable = total_movement_cost <= movement_points.current_mp

                return {
                    "reachable": reachable,
                    # "reason": (
                    #     "sufficient_movement" if reachable else "insufficient_movement"
                    # ),
                    # "movement_cost": total_movement_cost,
                    # "remaining_movement": movement_points.current_mp,
                    # "path_length": len(path) - 1,
                    # "effective_movement_range": effective_movement,
                }
            else:
                return {
                    "reachable": False,
                    "reason": "no_valid_path",
                    "movement_cost": -1,
                    "remaining_movement": movement_points.current_mp,
                    "effective_movement_range": effective_movement,
                }
        except Exception as e:
            return {
                "reachable": False,
                "reason": f"path_calculation_error",
                "movement_cost": -1,
                "remaining_movement": movement_points.current_mp,
                "error": str(e),
            }

    def _get_attack_range_info(
        self, current_pos: Tuple[int, int], target_pos: Tuple[int, int], combat: Combat
    ) -> Dict[str, Any]:
        """Get attack-range information between current and target tiles."""
        if not current_pos or not combat:
            return {
                "in_attack_range": False,
                "distance": -1,
                "attack_range": 0,
                "can_attack": False,
            }

        # Compute distance
        from ..utils.hex_utils import HexMath

        distance = HexMath.hex_distance(current_pos, target_pos)
        attack_range = combat.attack_range

        # In range?
        in_range = distance <= attack_range

        # Attack allowed when in range and not attacking self tile
        can_attack = in_range and distance > 0

        # return {
        #     "in_attack_range": in_range,
        #     # "distance": distance,
        #     # "attack_range": attack_range,
        #     # "can_attack": can_attack,
        #     # "range_status": "in_range" if in_range else "out_of_range",
        # }
        return in_range

    def handle_register_agent_info(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Register agent information for a faction (provider/model/base_url/etc)."""
        try:
            # Validate required parameters
            required_params = ["faction", "provider", "model_id", "base_url"]
            for param in required_params:
                if param not in params:
                    return {
                        "success": False,
                        "result": False,
                        "message": f"Missing required parameter: {param}",
                        "details": f"Missing required parameter: {param}",
                    }

            faction = params["faction"]
            provider = params["provider"]
            model_id = params["model_id"]
            base_url = params["base_url"]
            # Optional features
            enable_thinking = params.get("enable_thinking", False)

            # Create AgentInfo
            from ..components.agent_info import AgentInfo, AgentInfoRegistry

            agent_info = AgentInfo(
                provider=provider,
                model_id=model_id,
                base_url=AgentInfoRegistry.sanitize_url(base_url),
                agent_id=params.get("agent_id"),
                version=params.get("version"),
                note=params.get("note"),
                # pass through optional thinking flag
                enable_thinking=enable_thinking,
            )

            # Get or create registry
            registry = self.world.get_singleton_component(AgentInfoRegistry)
            if not registry:
                registry = AgentInfoRegistry()
                self.world.add_singleton_component(registry)

            # Register
            success = registry.register_agent(faction, agent_info)

            # Maintain registered_factions set in GameStats
            try:
                from ..components.state import GameStats

                stats = self.world.get_singleton_component(GameStats)
                if stats is None:
                    stats = GameStats()
                    self.world.add_singleton_component(stats)
                from ..prefabs.config import Faction as _Faction

                reg_faction = _Faction(faction)
                stats.registered_factions.add(reg_faction)
            except Exception as _e:
                print(
                    f"[LLMActionHandlerV3] ⚠️ Failed to update registered_factions after registration: {_e}"
                )

            if success:
                return {
                    "success": True,
                    "result": True,
                    "details": f"Agent info registered for faction: {faction}",
                    "message": f"Agent info registered for faction: {faction}",
                    "registered_info": {
                        "faction": faction,
                        "provider": provider,
                        "model_id": model_id,
                        "base_url_sanitized": agent_info.base_url,
                        # include thinking flag in response
                        "enable_thinking": enable_thinking,
                    },
                }
            else:
                return {
                    "success": False,
                    "result": False, 
                    "message": "Failed to register agent info", 
                    "details": "Failed to register agent info",
                }

        except Exception as e:
            return {
                "success": False,
                "result": False,
                "details": f"Error registering agent info: {str(e)}",
                "message": f"Error registering agent info: {str(e)}",
            }
