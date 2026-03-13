"""
LLM Action Handler V2 - API-spec compliant action handler.

Implemented according to ROTK_UNIT_ACTION_API_SPECIFICATION.md.

Key improvements:
1. Integrates core capabilities from individual systems and exposes them via a standardized interface.
2. Provides detailed error feedback so the LLM can understand why a decision failed.
3. Standardized JSON request/response schema.
4. Complete precondition checks and constraint validation.
"""

import asyncio
import json
import time
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
    GameState,
    Selected,
    UnitStatus,
    UnitSkills,
    ActionPoints,  # Points to the new multi-layer ActionPoints
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


class LLMActionHandlerV2:
    """LLM action handler V2 - compliant with the API specification."""

    def __init__(self, world: World):
        self.world = world
        self.api_version = "v1.0"

        # Error code mapping
        self.error_codes = {
            1001: "Unit not found",
            1002: "Insufficient action points",
            1003: "Target out of range",
            1004: "Invalid target position",
            1005: "Unit state does not allow this action",
            1006: "Skill is on cooldown",
            1007: "Terrain does not support this action",
            1008: "Faction mismatch",
            1009: "Action not allowed in the current game state",
            1010: "Invalid parameter format",
        }

        # Supported action mapping
        self.action_handlers = {
            # Unit control actions
            "move": self.handle_move_action,
            "attack": self.handle_attack_action,
            "wait": self.handle_wait_action,
            "garrison": self.handle_garrison_action,
            "capture": self.handle_capture_action,
            "fortify": self.handle_fortify_action,
            "skill": self.handle_skill_action,
            # Observation actions
            "unit_observation": self.handle_unit_observation,
            "get_unit_info": self.handle_get_unit_info,
            # Faction-level actions
            "faction_state": self.handle_faction_state,
            # "faction_unit_action": self.handle_faction_unit_action,
            # "faction_batch_actions": self.handle_faction_batch_actions,
            # System
            "action_list": self.handle_action_list,
        }

    def execute_action(
        self, action_type: str, params: Dict[str, Any] = {}
    ) -> Dict[str, Any]:
        """Unified entry point for executing actions."""
        try:
            # Parse action data
            # action_type = action_data.get("action")
            # params = action_data.get("params", {})

            if not action_type:
                return self._create_error_response(1010, "Missing action field")

            if action_type not in self.action_handlers:
                return self._create_error_response(
                    1010,
                    f"Unsupported action: {action_type}",
                    {"supported_actions": list(self.action_handlers.keys())},
                )

            # Execute the action
            print(f"Executing action: {action_type} with params: {params}")
            return self.action_handlers[action_type](params)

        except Exception as e:
            return self._create_error_response(
                1010, f"Action execution failed: {str(e)}"
            )

    # ==================== Unit control actions ====================

    def handle_move_action(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle the move action - designed for the multi-layer resource system with enhanced error feedback."""
        print(f"[MOVE_ACTION] Start processing move action, params: {params}")

        # Detailed parameter validation and feedback
        unit_id = params.get("unit_id")
        target_position = params.get("target_position")

        print(
            f"[MOVE_ACTION] Parsed params: unit_id={unit_id}, target_position={target_position}"
        )

        if not isinstance(unit_id, int):
            error_msg = (
                f"Invalid unit_id type: expected int, got {type(unit_id).__name__}"
            )
            print(f"[MOVE_ACTION] Parameter validation failed: {error_msg}")
            return self._create_error_response(
                1010,
                error_msg,
                {
                    "received_unit_id": unit_id,
                    "expected_type": "int",
                    "actual_type": type(unit_id).__name__,
                    "valid_example": {"unit_id": 123},
                },
            )

        if not target_position or not isinstance(target_position, dict):
            error_msg = f"Invalid target_position: expected dict with col/row, got {type(target_position).__name__}"
            print(f"[MOVE_ACTION] Parameter validation failed: {error_msg}")
            return self._create_error_response(
                1010,
                error_msg,
                {
                    "received_target_position": target_position,
                    "expected_format": {"col": "int", "row": "int"},
                    "valid_example": {"target_position": {"col": 5, "row": 8}},
                },
            )

        target_col = target_position.get("col")
        target_row = target_position.get("row")

        if not isinstance(target_col, int) or not isinstance(target_row, int):
            error_msg = f"Invalid target_position coordinates: col={target_col} ({type(target_col).__name__}), row={target_row} ({type(target_row).__name__})"
            print(f"[MOVE_ACTION] Coordinate validation failed: {error_msg}")
            return self._create_error_response(
                1010,
                error_msg,
                {
                    "received_col": target_col,
                    "received_row": target_row,
                    "col_type": type(target_col).__name__,
                    "row_type": type(target_row).__name__,
                    "expected_types": {"col": "int", "row": "int"},
                    "valid_example": {"col": 5, "row": 8},
                },
            )

        # Detailed unit existence check
        print(f"[MOVE_ACTION] Checking whether unit {unit_id} exists...")
        unit = self.world.get_component(unit_id, Unit)
        if not unit:
            error_msg = f"Unit {unit_id} not found in world"
            print(f"[MOVE_ACTION] Unit not found: {error_msg}")
            # Collect existing unit ids for reference
            all_units = []
            for entity_id in self.world.entities:
                if self.world.get_component(entity_id, Unit):
                    all_units.append(entity_id)

            return self._create_error_response(
                1001,
                error_msg,
                {
                    "requested_unit_id": unit_id,
                        "available_unit_ids": all_units[:10],  # Show at most the first 10
                    "total_units_in_world": len(all_units),
                    "suggestion": "Use faction_state action to see all units for a faction",
                },
            )

        print(
            f"[MOVE_ACTION] Unit {unit_id} exists. Type: {unit.unit_type.value}, faction: {unit.faction.value}"
        )

        # Detailed component checks
        print(f"[MOVE_ACTION] Checking required components for unit {unit_id}...")
        position = self.world.get_component(unit_id, HexPosition)
        movement_points = self.world.get_component(unit_id, MovementPoints)
        unit_count = self.world.get_component(unit_id, UnitCount)
        action_points = self.world.get_component(unit_id, ActionPoints)
        unit_status = self.world.get_component(unit_id, UnitStatus)

        # Detailed missing-component checks
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
                f"[MOVE_ACTION] Unit headcount: {unit_count.current_count}/{unit_count.max_count}"
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
                1001,
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

        # Detailed unit-state checks
        if unit_status:
            print(f"[MOVE_ACTION] Unit status: {unit_status.current_status}")
            if unit_status.current_status == UnitState.CONFUSION:
                error_msg = f"Unit {unit_id} is confused and cannot move"
                print(f"[MOVE_ACTION] Move blocked by status: {error_msg}")
                return self._create_error_response(
                    1005,
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
            print("[MOVE_ACTION] UnitStatus component missing; assuming normal status")

        # === Layer 1: action points (decision layer) ===
        print("[MOVE_ACTION] Checking action point requirement...")
        required_ap = 1
        current_ap = action_points.current_ap

        if current_ap < required_ap:
            error_msg = f"Insufficient action points to initiate movement decision: need {required_ap}, have {current_ap}"
            print(f"[MOVE_ACTION] Insufficient action points: {error_msg}")
            return self._create_error_response(
                1002,
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
        print(f"[MOVE_ACTION] Action point check passed: {current_ap}/{action_points.max_ap}")

        # === Layer 2: movement points (execution layer) ===
        print("[MOVE_ACTION] Checking movement points...")
        current_mp = movement_points.current_mp

        if current_mp <= 0:
            error_msg = f"Unit has no movement points left: {current_mp}"
            print(f"[MOVE_ACTION] Insufficient movement points: {error_msg}")
            return self._create_error_response(
                1002,
                error_msg,
                {
                    "unit_id": unit_id,
                    "current_movement_points": current_mp,
                    "max_movement_points": movement_points.max_mp,
                    "movement_point_info": component_info.get("movement_points", {}),
                    "suggestion": "Wait for movement points to recover",
                },
            )
        print(f"[MOVE_ACTION] Movement point check passed: {current_mp}/{movement_points.max_mp}")

        # Compute effective movement (account for headcount loss)
        effective_movement = movement_points.get_effective_movement(unit_count)
        current_pos = (position.col, position.row)
        target_pos = (target_col, target_row)

        print(
            f"[MOVE_ACTION] Effective movement: {effective_movement} (base: {current_mp}, headcount: {unit_count.current_count}/{unit_count.max_count})"
        )
        print(f"[MOVE_ACTION] Path planning: from {current_pos} to {target_pos}")

        # Get obstacles and check reachability
        print("[MOVE_ACTION] Collecting map obstacles...")
        obstacles = self._get_obstacles_excluding_unit(unit_id)  # Exclude the moving unit itself
        print(f"[MOVE_ACTION] Obstacle count: {len(obstacles) if obstacles else 0}")

        # Check whether the target position is occupied
        if target_pos in obstacles:
            # Find the unit occupying the target
            occupying_unit_id = None
            occupying_unit_info = None
            for entity in self.world.query().with_all(HexPosition, Unit).entities():
                if entity == unit_id:
                    continue  # Skip the moving unit itself
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
                1004,
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

        print("[MOVE_ACTION] Running pathfinding...")
        print(f"[MOVE_ACTION] Start position: {current_pos}")
        print(f"[MOVE_ACTION] Target position: {target_pos}")
        print(f"[MOVE_ACTION] Effective movement budget: {effective_movement}")
        print(
            f"[MOVE_ACTION] Obstacles sample: {list(obstacles)[:10]}..."
        )  # Show only the first 10

        path = PathFinding.find_path(
            current_pos, target_pos, obstacles, effective_movement
        )

        print(f"[MOVE_ACTION] Pathfinding result: {path}")

        if not path or len(path) < 2:
            # Collect more info when pathfinding fails
            from ..utils.hex_utils import HexMath

            hex_distance = HexMath.hex_distance(current_pos, target_pos)

            # Check whether distance exceeds range
            distance_issue = hex_distance > effective_movement

            # Check whether the target is blocked
            target_blocked = target_pos in obstacles

            # Check reachability of adjacent free positions
            adjacent_free_positions = self._get_adjacent_free_positions(
                current_pos, obstacles
            )

            error_msg = f"No valid path to target position {target_pos}"
            print(f"[MOVE_ACTION] Pathfinding failed: {error_msg}")
            print(f"[MOVE_ACTION] Hex distance: {hex_distance}")
            print(f"[MOVE_ACTION] Effective movement: {effective_movement}")
            print(f"[MOVE_ACTION] Distance exceeds range: {distance_issue}")
            print(f"[MOVE_ACTION] Target blocked: {target_blocked}")
            print(f"[MOVE_ACTION] Adjacent free positions: {adjacent_free_positions}")

            return self._create_error_response(
                1004,
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
                    "obstacles_sample": list(obstacles)[:10],  # First 10 obstacles as a sample
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

        print(f"[MOVE_ACTION] Path found. Length: {len(path)}, path: {path}")

        # Compute total movement cost (terrain tiles may have different costs)
        print("[MOVE_ACTION] Computing total path movement cost...")
        total_movement_cost = self._calculate_total_movement_cost(path)
        print(f"[MOVE_ACTION] Total cost: {total_movement_cost} movement points")

        # Check remaining movement points (use actual remaining points)
        if total_movement_cost > current_mp:
            error_msg = f"Target too far: need {total_movement_cost} movement points, have {current_mp}"
            print(f"[MOVE_ACTION] Not enough movement points to reach target: {error_msg}")
            return self._create_error_response(
                1003,
                error_msg,
                {
                    "unit_id": unit_id,
                    "required_movement_points": total_movement_cost,
                    "current_movement_points": current_mp,
                    "deficit": total_movement_cost - current_mp,
                    "path": path,
                    "path_length": len(path) - 1,
                    "effective_movement": effective_movement,
                    "terrain_costs": self._get_path_terrain_breakdown(path),
                    "suggestion": f"Try a closer target or wait for {total_movement_cost - current_mp} more movement points",
                },
            )

        print(f"[MOVE_ACTION] Movement points sufficient. Remaining: {current_mp - total_movement_cost}")

        # Execute movement
        print("[MOVE_ACTION] Getting movement system...")
        movement_system = self._get_movement_system()
        if not movement_system:
            error_msg = "Movement system not available"
            print(f"[MOVE_ACTION] System error: {error_msg}")
            return self._create_error_response(
                1009,
                error_msg,
                {
                    "unit_id": unit_id,
                    "system_error": "MovementSystem not found",
                    "suggestion": "This is a game engine error - contact administrator",
                },
            )

        print("[MOVE_ACTION] Executing movement...")
        success = movement_system.move_unit(unit_id, target_pos)

        if success:
            print("[MOVE_ACTION] Movement succeeded.")
            # Refresh component state after movement (MovementSystem may have modified them)
            updated_action_points = self.world.get_component(unit_id, ActionPoints)
            updated_movement_points = self.world.get_component(unit_id, MovementPoints)

            result = {
                "success": True,
                "message": f"Unit {unit_id} moved successfully from {current_pos} to {target_pos}",
                "movement_details": {
                    "start_position": current_pos,
                    "end_position": target_pos,
                    "path": path,
                    "path_length": len(path) - 1,
                    "terrain_breakdown": self._get_path_terrain_breakdown(path),
                },
                "resource_consumption": {
                    "action_points_used": 1,  # Fixed: consume 1 AP to initiate the decision
                    "movement_points_used": total_movement_cost,  # Actual movement point cost
                },
                "remaining_resources": {
                    "action_points": (
                        updated_action_points.current_ap if updated_action_points else 0
                    ),
                    "movement_points": (
                        updated_movement_points.current_mp
                        if updated_movement_points
                        else 0
                    ),
                },
                "unit_status_after_move": {
                    "unit_id": unit_id,
                    "position": target_pos,
                    "can_move_further": (
                        updated_movement_points.current_mp
                        if updated_movement_points
                        else 0
                    )
                    > 0,
                    "can_take_more_actions": (
                        updated_action_points.current_ap if updated_action_points else 0
                    )
                    > 0,
                },
            }
            print(f"[MOVE_ACTION] Move completed. Returning result: {result}")
            return result
        else:
            error_msg = "Movement system failed to execute move"
            print(f"[MOVE_ACTION] Move execution failed: {error_msg}")
            return self._create_error_response(
                1009,
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
        """Handle the attack action."""
        # Parameter validation
        unit_id = params.get("unit_id")
        target_id = params.get("target_id")

        if not isinstance(unit_id, int) or not isinstance(target_id, int):
            return self._create_error_response(
                1010, "unit_id and target_id must be integers"
            )

        # Check attacker existence
        attacker_unit = self.world.get_component(unit_id, Unit)
        if not attacker_unit:
            return self._create_error_response(
                1001, f"Attacker unit {unit_id} not found"
            )

        # Check target existence
        target_unit = self.world.get_component(target_id, Unit)
        if not target_unit:
            return self._create_error_response(
                1001, f"Target unit {target_id} not found"
            )

        # Check whether factions are hostile
        if attacker_unit.faction == target_unit.faction:
            return self._create_error_response(
                1008, "Cannot attack units of same faction"
            )

        # Check attacker components
        attacker_pos = self.world.get_component(unit_id, HexPosition)
        attacker_combat = self.world.get_component(unit_id, Combat)
        attacker_action_points = self.world.get_component(unit_id, ActionPoints)

        if not all([attacker_pos, attacker_combat, attacker_action_points]):
            return self._create_error_response(
                1001, "Attacker missing required components"
            )

        # Check target components
        target_pos = self.world.get_component(target_id, HexPosition)
        if not target_pos:
            return self._create_error_response(
                1001, "Target missing position component"
            )

        # Check action points
        if not attacker_action_points.can_perform_action(ActionType.ATTACK):
            return self._create_error_response(
                1002,
                f"Insufficient action points for attack: need 2, have {attacker_action_points.current_ap}",
            )

        # Check attack range
        attacker_current_pos = (attacker_pos.col, attacker_pos.row)
        target_current_pos = (target_pos.col, target_pos.row)
        distance = HexMath.hex_distance(attacker_current_pos, target_current_pos)

        if distance > attacker_combat.attack_range:
            return self._create_error_response(
                1003,
                f"Target out of range: distance {distance}, range {attacker_combat.attack_range}",
            )

        # Check whether the unit has already attacked
        if attacker_combat.has_attacked:
            return self._create_error_response(
                1005, "Unit has already attacked this turn"
            )

        # Execute attack
        combat_system = self._get_combat_system()
        if combat_system:
            # Capture pre-attack state
            target_count = self.world.get_component(target_id, UnitCount)
            initial_target_count = target_count.current_count if target_count else 0

            success = combat_system.attack(unit_id, target_id)
            if success:
                # Capture post-attack state
                final_target_count = target_count.current_count if target_count else 0
                casualties = initial_target_count - final_target_count

                # Terrain modifier information
                terrain_bonus = self._get_terrain_attack_bonus(
                    attacker_current_pos, attacker_unit.faction
                )

                return {
                    "success": True,
                    "message": f"Unit {unit_id} attacked unit {target_id}",
                    "battle_result": {
                        "attacker_damage_dealt": casualties,
                        "defender_damage_dealt": 0,  # Simplified: counterattacks may exist in full rules
                        "attacker_casualties": 0,
                        "defender_casualties": casualties,
                        "terrain_bonus": terrain_bonus,
                    },
                    "remaining_action_points": attacker_action_points.current_ap - 2,
                }
            else:
                return self._create_error_response(
                    1009, "Combat system failed to execute attack"
                )
        else:
            return self._create_error_response(1009, "Combat system not available")

    def handle_wait_action(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle the wait action."""
        unit_id = params.get("unit_id")

        if not isinstance(unit_id, int):
            return self._create_error_response(1010, "unit_id must be integer")

        # Validate that the unit exists
        unit = self.world.get_component(unit_id, Unit)
        if not unit:
            return self._create_error_response(1001, f"Unit {unit_id} not found")

        # Execute wait
        action_system = self._get_action_system()
        if action_system:
            success = action_system.perform_wait(unit_id)
            if success:
                action_points = self.world.get_component(unit_id, ActionPoints)
                unit_status = self.world.get_component(unit_id, UnitStatus)

                return {
                    "success": True,
                    "message": f"Unit {unit_id} is waiting and recovering",
                    "effects": {
                        "morale_recovery": True,
                        "fatigue_removed": unit_status.current_status
                        != UnitState.FATIGUE,
                        "turn_ended": True,
                    },
                    "remaining_action_points": (
                        action_points.current_ap if action_points else 0
                    ),
                }
            else:
                return self._create_error_response(
                    1009, "Action system failed to execute wait"
                )
        else:
            return self._create_error_response(1009, "Action system not available")

    def handle_garrison_action(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle the garrison action."""
        unit_id = params.get("unit_id")

        if not isinstance(unit_id, int):
            return self._create_error_response(1010, "unit_id must be integer")

        # Validate that the unit exists
        unit = self.world.get_component(unit_id, Unit)
        if not unit:
            return self._create_error_response(1001, f"Unit {unit_id} not found")

        # Check action points
        action_points = self.world.get_component(unit_id, ActionPoints)
        if not action_points or not action_points.can_perform_action(
            ActionType.GARRISON
        ):
            return self._create_error_response(
                1002,
                f"Insufficient action points for garrison: need 2, have {action_points.current_ap if action_points else 0}",
            )

        # Execute garrison
        action_system = self._get_action_system()
        if action_system:
            success = action_system.perform_garrison(unit_id)
            if success:
                unit_count = self.world.get_component(unit_id, UnitCount)
                return {
                    "success": True,
                    "message": f"Unit {unit_id} is garrisoned",
                    "effects": {
                        "manpower_recovery": True,
                        "defense_bonus": 2,
                        "status_normalized": True,
                    },
                    "current_count": unit_count.current_count if unit_count else 0,
                    "remaining_action_points": action_points.current_ap - 2,
                }
            else:
                return self._create_error_response(
                    1009, "Action system failed to execute garrison"
                )
        else:
            return self._create_error_response(1009, "Action system not available")

    def handle_capture_action(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle the capture action."""
        unit_id = params.get("unit_id")
        position = params.get("position")

        if not isinstance(unit_id, int):
            return self._create_error_response(1010, "unit_id must be integer")

        if not position or not isinstance(position, dict):
            return self._create_error_response(
                1010, "position must be object with col/row"
            )

        col = position.get("col")
        row = position.get("row")

        if not isinstance(col, int) or not isinstance(row, int):
            return self._create_error_response(
                1010, "position col/row must be integers"
            )

        # Validate that the unit exists
        unit = self.world.get_component(unit_id, Unit)
        if not unit:
            return self._create_error_response(1001, f"Unit {unit_id} not found")

        # Validate that the unit is at the target position
        unit_pos = self.world.get_component(unit_id, HexPosition)
        if not unit_pos or (unit_pos.col, unit_pos.row) != (col, row):
            return self._create_error_response(
                1004, "Unit must be at target position to capture"
            )

        # Check action points
        action_points = self.world.get_component(unit_id, ActionPoints)
        if not action_points or not action_points.can_perform_action(
            ActionType.CAPTURE
        ):
            return self._create_error_response(
                1002,
                f"Insufficient action points for capture: need 2, have {action_points.current_ap if action_points else 0}",
            )

        # Check whether the tile can be captured
        territory_system = self._get_territory_system()
        if territory_system:
            success = territory_system.start_capture(unit_id, (col, row))
            if success:
                return {
                    "success": True,
                    "message": f"Unit {unit_id} started capturing position {(col, row)}",
                    "capture_status": {
                        "in_progress": True,
                        "estimated_turns": 1,  # May be adjusted based on terrain
                        "can_be_interrupted": True,
                    },
                    "remaining_action_points": action_points.current_ap - 2,
                }
            else:
                return self._create_error_response(
                    1007, "Position cannot be captured (already controlled or invalid)"
                )
        else:
            return self._create_error_response(1009, "Territory system not available")

    def handle_fortify_action(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle the fortify (build fortification) action."""
        unit_id = params.get("unit_id")
        position = params.get("position")

        if not isinstance(unit_id, int):
            return self._create_error_response(1010, "unit_id must be integer")

        if not position or not isinstance(position, dict):
            return self._create_error_response(
                1010, "position must be object with col/row"
            )

        col = position.get("col")
        row = position.get("row")

        if not isinstance(col, int) or not isinstance(row, int):
            return self._create_error_response(
                1010, "position col/row must be integers"
            )

        # Validate that the unit exists
        unit = self.world.get_component(unit_id, Unit)
        if not unit:
            return self._create_error_response(1001, f"Unit {unit_id} not found")

        # Check action points and construction points
        action_points = self.world.get_component(unit_id, ActionPoints)
        construction_points = self.world.get_component(unit_id, ConstructionPoints)

        if not action_points or not action_points.can_perform_action(
            ActionType.FORTIFY
        ):
            return self._create_error_response(
                1002,
                f"Insufficient action points for fortify: need 2, have {action_points.current_ap if action_points else 0}",
            )

        if not construction_points or not construction_points.can_build(1):
            return self._create_error_response(
                1002,
                f"Insufficient construction points for fortify: need 1, have {construction_points.current_cp if construction_points else 0}",
            )

        # Get terrain type and fortification level cap
        terrain_type = self._get_terrain_at_position((col, row))
        max_level = self._get_max_fortification_level(terrain_type)

        # Check current fortification level
        current_level = self._get_current_fortification_level((col, row))

        if current_level >= max_level:
            return self._create_error_response(
                1007,
                f"Fortification already at max level for terrain {terrain_type.value}: {current_level}/{max_level}",
            )

        # Execute fortification build
        territory_system = self._get_territory_system()
        if territory_system:
            success = territory_system.build_fortification(unit_id, (col, row))
            if success:
                new_level = current_level + 1
                defense_bonus = self._calculate_fortification_defense_bonus(new_level)

                return {
                    "success": True,
                    "message": f"Unit {unit_id} built fortification at {(col, row)}",
                    "current_level": new_level,
                    "max_level": max_level,
                    "defense_bonus": defense_bonus,
                    "terrain_type": terrain_type.value,
                    "remaining_action_points": action_points.current_ap - 2,
                }
            else:
                return self._create_error_response(
                    1007, "Cannot build fortification at this position"
                )
        else:
            return self._create_error_response(1009, "Territory system not available")

    def handle_skill_action(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle the skill action."""
        unit_id = params.get("unit_id")
        skill_name = params.get("skill_name")
        target = params.get("target")

        if not isinstance(unit_id, int):
            return self._create_error_response(1010, "unit_id must be integer")

        if not isinstance(skill_name, str):
            return self._create_error_response(1010, "skill_name must be string")

        # Validate that the unit exists
        unit = self.world.get_component(unit_id, Unit)
        if not unit:
            return self._create_error_response(1001, f"Unit {unit_id} not found")

        # Check skill-related components
        unit_skills = self.world.get_component(unit_id, UnitSkills)
        skill_points = self.world.get_component(unit_id, SkillPoints)

        if not unit_skills:
            return self._create_error_response(1005, "Unit has no skills")

        if not skill_points:
            return self._create_error_response(1005, "Unit has no skill points")

        # Check whether the skill is available (UnitSkills controls list & cooldown)
        if not unit_skills.can_use_skill(skill_name):
            if skill_name not in unit_skills.available_skills:
                return self._create_error_response(
                    1005, f"Skill {skill_name} not available"
                )
            else:
                cooldown = unit_skills.skill_cooldowns.get(skill_name, 0)
                return self._create_error_response(
                    1006, f"Skill {skill_name} on cooldown: {cooldown} turns"
                )

        # Check skill points (SkillPoints controls cost)
        if not skill_points.can_use_skill(skill_name, 1):
            return self._create_error_response(
                1006,
                f"Insufficient skill points: need 1, have {skill_points.current_sp}",
            )

        # Check action points
        action_points = self.world.get_component(unit_id, ActionPoints)
        if not action_points or not action_points.can_perform_action(ActionType.SKILL):
            return self._create_error_response(
                1002,
                f"Insufficient action points for skill: need 2, have {action_points.current_ap if action_points else 0}",
            )

        # Check terrain and skill requirements
        unit_pos = self.world.get_component(unit_id, HexPosition)
        if unit_pos:
            current_terrain = self._get_terrain_at_position(
                (unit_pos.col, unit_pos.row)
            )
            skill_result = self._execute_terrain_skill(
                unit_id, skill_name, current_terrain, target
            )

            if skill_result["success"]:
                # Consume resources: multi-layer resource system
                # 1) Action points (decision layer)
                action_points.consume_ap(ActionType.SKILL)

                # 2) Skill points (execution layer)
                skill_points.use_skill(skill_name, 1, skill_result.get("cooldown", 0))

                # 3) Set cooldown (via UnitSkills)
                unit_skills.use_skill(skill_name, skill_result.get("cooldown", 0))

                return {
                    "success": True,
                    "message": f"Unit {unit_id} used skill {skill_name}",
                    "skill_result": skill_result,
                    "remaining_action_points": action_points.current_ap,
                    "remaining_skill_points": skill_points.current_sp,
                }
            else:
                return self._create_error_response(
                    1007, skill_result.get("error", "Skill execution failed")
                )
        else:
            return self._create_error_response(1001, "Unit position not found")

    # ==================== Observation actions ====================

    def handle_unit_observation(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle unit observation."""
        unit_id = params.get("unit_id")
        observation_level = params.get("observation_level", "basic")

        if not isinstance(unit_id, int):
            return self._create_error_response(1010, "unit_id must be integer")

        # Validate that the unit exists
        unit = self.world.get_component(unit_id, Unit)
        if not unit:
            return self._create_error_response(1001, f"Unit {unit_id} not found")

        # Get unit information
        unit_info = self._get_detailed_unit_info(unit_id)

        # Get visible environment
        visible_environment = self._get_visible_environment(unit_id, observation_level)

        result = {
            "success": True,
            "unit_info": unit_info,
            "visible_environment": visible_environment,
        }

        # Add extra information based on observation level
        if observation_level in ["detailed", "tactical"]:
            result["tactical_info"] = self._get_tactical_info(unit_id)

        return result

    def handle_get_unit_info(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get detailed unit information."""
        unit_id = params.get("unit_id")

        if not isinstance(unit_id, int):
            return self._create_error_response(1010, "unit_id must be integer")

        # Validate that the unit exists
        unit = self.world.get_component(unit_id, Unit)
        if not unit:
            return self._create_error_response(1001, f"Unit {unit_id} not found")

        unit_info = self._get_detailed_unit_info(unit_id)

        return {"success": True, **unit_info}

    # ==================== Faction-level actions ====================

    def handle_faction_state(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get faction state."""
        faction_str = params.get("faction")

        if not faction_str:
            return self._create_error_response(1010, "faction parameter required")

        try:
            faction = Faction(faction_str)
            print(f"Handling faction state for {faction.value}")
        except ValueError:
            return self._create_error_response(1010, f"Invalid faction: {faction_str}")

        # Get all units for the faction
        faction_units = self._get_faction_units(faction)

        # Compute faction statistics
        total_units_count = len(faction_units)
        active_units = [u for u in faction_units if self._is_unit_active(u)]
        active_units_count = len(active_units)

        # Territory control (TODO)
        # territory_control = self._calculate_territory_control(faction)

        # Resource summary (TODO)
        # resource_summary = self._calculate_resource_summary(faction_units)

        # Strategic analysis (TODO)
        # strategic_summary = self._get_strategic_summary(faction)
        print(f"final {faction.value}")
        return {
            "success": True,
            "faction": faction.value,
            "total_units": total_units_count,
            "active_units": active_units_count,
            "units": [
                self._get_detailed_unit_info(unit_id) for unit_id in active_units[:10]
            ],  # Limit returned units
            # "territory_control": territory_control,
            # "resource_summary": resource_summary,
            # "units": [
            #     self._get_detailed_unit_info(unit_id) for unit_id in faction_units[:10]
            # ],  # Limit returned count
            # "strategic_summary": strategic_summary,
        }

    def handle_faction_unit_action(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a unit action scoped to a faction."""
        faction_str = params.get("faction")
        unit_id = params.get("unit_id")
        unit_action = params.get("unit_action")
        action_params = params.get("action_params", {})

        # Validate parameters
        if not faction_str or not isinstance(unit_id, int) or not unit_action:
            return self._create_error_response(
                1010, "faction, unit_id, unit_action required"
            )

        try:
            faction = Faction(faction_str)
        except ValueError:
            return self._create_error_response(1010, f"Invalid faction: {faction_str}")

        # Validate the unit belongs to this faction
        unit = self.world.get_component(unit_id, Unit)
        if not unit:
            return self._create_error_response(1001, f"Unit {unit_id} not found")

        if unit.faction != faction:
            return self._create_error_response(
                1008, f"Unit {unit_id} does not belong to faction {faction.value}"
            )

        # Construct action payload and execute
        action_data = {
            "action": unit_action,
            "params": {"unit_id": unit_id, **action_params},
        }

        return self.execute_action(action_data)

    def handle_faction_batch_actions(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a batch of faction-scoped actions."""
        faction_str = params.get("faction")
        actions = params.get("actions", [])

        if not faction_str:
            return self._create_error_response(1010, "faction parameter required")

        if not isinstance(actions, list):
            return self._create_error_response(1010, "actions must be array")

        if len(actions) > 10:  # Limit batch size
            return self._create_error_response(1010, "Maximum 10 actions per batch")

        try:
            faction = Faction(faction_str)
        except ValueError:
            return self._create_error_response(1010, f"Invalid faction: {faction_str}")

        # Execute all actions
        results = []
        executed_actions = 0
        failed_actions = 0

        for action in actions:
            unit_id = action.get("unit_id")
            action_type = action.get("action")
            action_params = action.get("params", {})

            if not isinstance(unit_id, int) or not action_type:
                result = {
                    "unit_id": unit_id,
                    "action": action_type,
                    "success": False,
                    "message": "Invalid action format",
                    "result_data": None,
                }
                failed_actions += 1
            else:
                # Validate the unit belongs to this faction
                unit = self.world.get_component(unit_id, Unit)
                if not unit or unit.faction != faction:
                    result = {
                        "unit_id": unit_id,
                        "action": action_type,
                        "success": False,
                        "message": f"Unit {unit_id} not found or wrong faction",
                        "result_data": None,
                    }
                    failed_actions += 1
                else:
                    # Execute action
                    action_data = {
                        "action": action_type,
                        "params": {"unit_id": unit_id, **action_params},
                    }

                    action_result = self.execute_action(action_data)

                    result = {
                        "unit_id": unit_id,
                        "action": action_type,
                        "success": action_result.get("success", False),
                        "message": action_result.get("message", ""),
                        "result_data": action_result,
                    }

                    if result["success"]:
                        executed_actions += 1
                    else:
                        failed_actions += 1

            results.append(result)

        return {
            "success": True,
            "executed_actions": executed_actions,
            "failed_actions": failed_actions,
            "results": results,
        }

    def handle_action_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Return interface documentation for all available actions."""
        action_docs = {
            "api_version": self.api_version,
            "total_actions": len(self.action_handlers),
            "actions": {
                # Unit control actions
                "move": {
                    "category": "unit_control",
                    "description": "Move a unit to a target position",
                    "parameters": {
                        "unit_id": {
                            "type": "int",
                            "required": True,
                            "description": "Unit id",
                        },
                        "target_position": {
                            "type": "object",
                            "required": True,
                            "description": "Target position",
                            "properties": {
                                "col": {"type": "int", "description": "Column coordinate"},
                                "row": {"type": "int", "description": "Row coordinate"},
                            },
                        },
                    },
                    "returns": {
                        "success": {"type": "bool", "description": "Whether execution succeeded"},
                        "message": {"type": "string", "description": "Result message"},
                        "resource_consumption": {
                            "type": "object",
                            "description": "Resource consumption details",
                            "properties": {
                                "action_points_used": {
                                    "type": "int",
                                    "description": "Action points consumed (decision layer)",
                                },
                                "movement_points_used": {
                                    "type": "int",
                                    "description": "Movement points consumed (execution layer)",
                                },
                            },
                        },
                        "remaining_resources": {
                            "type": "object",
                            "description": "Remaining resources",
                            "properties": {
                                "action_points": {
                                    "type": "int",
                                    "description": "Remaining action points",
                                },
                                "movement_points": {
                                    "type": "int",
                                    "description": "Remaining movement points",
                                },
                            },
                        },
                        "path_info": {
                            "type": "object",
                            "description": "Path information",
                            "properties": {
                                "path": {"type": "array", "description": "Movement path"},
                                "path_length": {
                                    "type": "int",
                                    "description": "Path length",
                                },
                                "terrain_breakdown": {
                                    "type": "array",
                                    "description": "Per-tile terrain cost breakdown",
                                },
                            },
                        },
                    },
                    "resource_system": {
                        "action_points": "Fixed: consume 1 AP to initiate the movement decision",
                        "movement_points": "Depends on path & terrain costs: plain=1, forest=2, mountain=3, etc.",
                        "recovery": "Automatically recovers each turn; in real-time mode recovers every 5 seconds",
                    },
                    "prerequisites": [
                        "Unit exists",
                        "At least 1 AP to initiate decision",
                        "Sufficient movement points to reach the target",
                        "Target position is reachable",
                        "Unit status allows movement",
                    ],
                },
                "attack": {
                    "category": "unit_control",
                    "description": "Attack an enemy unit",
                    "parameters": {
                        "unit_id": {
                            "type": "int",
                            "required": True,
                            "description": "Attacker unit id",
                        },
                        "target_id": {
                            "type": "int",
                            "required": True,
                            "description": "Target unit id",
                        },
                    },
                    "returns": {
                        "success": {"type": "bool", "description": "Whether the attack succeeded"},
                        "message": {"type": "string", "description": "Attack result message"},
                        "battle_result": {"type": "object", "description": "Battle details"},
                        "remaining_action_points": {
                            "type": "int",
                            "description": "Remaining action points",
                        },
                    },
                    "action_point_cost": "2",
                    "prerequisites": [
                        "Unit exists",
                        "Target is within attack range",
                        "Target is hostile",
                        "Has not attacked this turn",
                        "Sufficient action points",
                    ],
                },
                "wait": {
                    "category": "unit_control",
                    "description": "Wait to recover/normalize unit state",
                    "parameters": {
                        "unit_id": {
                            "type": "int",
                            "required": True,
                            "description": "Unit id",
                        }
                    },
                    "returns": {
                        "success": {"type": "bool", "description": "Whether execution succeeded"},
                        "message": {"type": "string", "description": "Result message"},
                        "effects": {"type": "object", "description": "Recovery effects"},
                        "remaining_action_points": {
                            "type": "int",
                            "description": "Remaining action points",
                        },
                    },
                    "action_point_cost": "0",
                    "prerequisites": ["Unit exists"],
                },
                "garrison": {
                    "category": "unit_control",
                    "description": "Garrison to recover headcount and gain defensive benefits",
                    "parameters": {
                        "unit_id": {
                            "type": "int",
                            "required": True,
                            "description": "Unit id",
                        }
                    },
                    "returns": {
                        "success": {"type": "bool", "description": "Whether execution succeeded"},
                        "message": {"type": "string", "description": "Result message"},
                        "effects": {"type": "object", "description": "Garrison effects"},
                        "current_count": {"type": "int", "description": "Current headcount"},
                        "remaining_action_points": {
                            "type": "int",
                            "description": "Remaining action points",
                        },
                    },
                    "action_point_cost": "2",
                    "prerequisites": ["Unit exists", "Sufficient action points"],
                },
                "capture": {
                    "category": "territory_control",
                    "description": "Capture a target tile",
                    "parameters": {
                        "unit_id": {
                            "type": "int",
                            "required": True,
                            "description": "Unit id",
                        },
                        "position": {
                            "type": "object",
                            "required": True,
                            "description": "Capture position",
                            "properties": {
                                "col": {"type": "int", "description": "Column coordinate"},
                                "row": {"type": "int", "description": "Row coordinate"},
                            },
                        },
                    },
                    "returns": {
                        "success": {"type": "bool", "description": "Whether capture started/succeeded"},
                        "message": {"type": "string", "description": "Capture result message"},
                        "capture_status": {"type": "object", "description": "Capture status"},
                        "remaining_action_points": {
                            "type": "int",
                            "description": "Remaining action points",
                        },
                    },
                    "action_point_cost": "2",
                    "prerequisites": ["Unit is on the target position", "Tile is capturable", "Sufficient action points"],
                },
                "fortify": {
                    "category": "territory_control",
                    "description": "Build fortifications at a target position",
                    "parameters": {
                        "unit_id": {
                            "type": "int",
                            "required": True,
                            "description": "Unit id",
                        },
                        "position": {
                            "type": "object",
                            "required": True,
                            "description": "Fortification position",
                            "properties": {
                                "col": {"type": "int", "description": "Column coordinate"},
                                "row": {"type": "int", "description": "Row coordinate"},
                            },
                        },
                    },
                    "returns": {
                        "success": {"type": "bool", "description": "Whether the build succeeded"},
                        "message": {"type": "string", "description": "Build result message"},
                        "current_level": {"type": "int", "description": "Current fortification level"},
                        "max_level": {"type": "int", "description": "Maximum fortification level"},
                        "defense_bonus": {"type": "float", "description": "Defense bonus"},
                        "terrain_type": {"type": "string", "description": "Terrain type"},
                        "remaining_action_points": {
                            "type": "int",
                            "description": "Remaining action points",
                        },
                    },
                    "action_point_cost": "2",
                    "prerequisites": [
                        "Unit exists",
                        "Fortification not at cap",
                        "Terrain allows fortification",
                        "Sufficient action points",
                    ],
                },
                "skill": {
                    "category": "unit_control",
                    "description": "Use a unit skill",
                    "parameters": {
                        "unit_id": {
                            "type": "int",
                            "required": True,
                            "description": "Unit id",
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
                    "returns": {
                        "success": {"type": "bool", "description": "Whether the skill execution succeeded"},
                        "message": {"type": "string", "description": "Skill result message"},
                        "skill_result": {"type": "object", "description": "Skill effects"},
                        "remaining_action_points": {
                            "type": "int",
                            "description": "Remaining action points",
                        },
                    },
                    "action_point_cost": "2",
                    "prerequisites": [
                        "Unit exists",
                        "Skill is available",
                        "Not on cooldown",
                        "Terrain requirements met",
                        "Sufficient action points",
                    ],
                },
                # Observation actions
                "unit_observation": {
                    "category": "observation",
                    "description": "Get observation information for a unit",
                    "parameters": {
                        "unit_id": {
                            "type": "int",
                            "required": True,
                            "description": "Unit id",
                        },
                        "observation_level": {
                            "type": "string",
                            "required": False,
                            "description": "Observation level",
                            "default": "basic",
                            "options": ["basic", "detailed", "tactical"],
                        },
                    },
                    "returns": {
                        "success": {"type": "bool", "description": "Whether observation succeeded"},
                        "unit_info": {"type": "object", "description": "Detailed unit info"},
                        "visible_environment": {
                            "type": "array",
                            "description": "Visible environment",
                        },
                        "tactical_info": {
                            "type": "object",
                            "description": "Tactical info (detailed/tactical modes)",
                        },
                    },
                    "action_point_cost": "0",
                    "prerequisites": ["Unit exists"],
                },
                "get_unit_info": {
                    "category": "observation",
                    "description": "Get detailed unit information",
                    "parameters": {
                        "unit_id": {
                            "type": "int",
                            "required": True,
                            "description": "Unit id",
                        }
                    },
                    "returns": {
                        "success": {"type": "bool", "description": "Whether retrieval succeeded"},
                        "unit_id": {"type": "int", "description": "Unit id"},
                        "unit_type": {"type": "string", "description": "Unit type"},
                        "faction": {"type": "string", "description": "Faction"},
                        "position": {"type": "object", "description": "Position info"},
                        "status": {"type": "object", "description": "Status info"},
                        "capabilities": {"type": "object", "description": "Capability info"},
                        "available_skills": {
                            "type": "array",
                            "description": "List of available skills",
                        },
                    },
                    "action_point_cost": "0",
                    "prerequisites": ["Unit exists"],
                },
                # Faction-level actions
                "faction_state": {
                    "category": "faction_control",
                    "description": "Get overall faction state",
                    "parameters": {
                        "faction": {
                            "type": "string",
                            "required": True,
                            "description": "Faction name (wei/shu/wu)",
                        }
                    },
                    "returns": {
                        "success": {"type": "bool", "description": "Whether retrieval succeeded"},
                        "faction": {"type": "string", "description": "Faction name"},
                        "total_units": {"type": "int", "description": "Total units"},
                        "active_units": {"type": "int", "description": "Active units"},
                        "territory_control": {
                            "type": "int",
                            "description": "Territory control percentage",
                        },
                        "resource_summary": {
                            "type": "object",
                            "description": "Resource summary",
                        },
                        "units": {"type": "array", "description": "Unit list (up to 10)"},
                        "strategic_summary": {
                            "type": "object",
                            "description": "Strategic summary",
                        },
                    },
                    "action_point_cost": "0",
                    "prerequisites": ["Valid faction name"],
                },
                # System actions
                "action_list": {
                    "category": "system",
                    "description": "Get interface documentation for all available actions",
                    "parameters": {},
                    "returns": {
                        "api_version": {"type": "string", "description": "API version"},
                        "total_actions": {"type": "int", "description": "Total number of actions"},
                        "actions": {
                            "type": "object",
                            "description": "Detailed docs for all actions",
                        },
                    },
                    "action_point_cost": "0",
                    "prerequisites": ["None"],
                },
            },
            "error_codes": {
                1001: "Unit not found",
                1002: "Insufficient action points",
                1003: "Target out of range",
                1004: "Invalid target position",
                1005: "Unit state does not allow this action",
                1006: "Skill is on cooldown",
                1007: "Terrain does not support this action",
                1008: "Faction mismatch",
                1009: "Action not allowed in the current game state",
                1010: "Invalid parameter format",
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
                "get_faction_overview": {
                    "action": "faction_state",
                    "params": {"faction": "wei"},
                },
            },
        }

        return {"success": True, **action_docs}

    # ==================== Helper methods ====================

    def _create_error_response(
        self, error_code: int, message: str, extra_data: Dict = None
    ) -> Dict[str, Any]:
        """Create a standardized error response."""
        response = {
            "success": False,
            "error_code": error_code,
            "error": self.error_codes.get(error_code, "Unknown error"),
            "message": message,
            "api_version": self.api_version,
        }

        if extra_data:
            response.update(extra_data)

        return response

    def _get_detailed_unit_info(self, unit_id: int) -> Dict[str, Any]:
        """Get detailed unit information."""
        try:
            # Parameter validation
            if not isinstance(unit_id, int) or unit_id <= 0:
                return {
                    "unit_id": unit_id,
                    "error": "Invalid unit_id",
                    "unit_type": "unknown",
                    "faction": "unknown",
                    "position": {"col": 0, "row": 0},
                    "status": {
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

            # Get all relevant components
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

            # Validate that core components exist
            if not unit:
                return {
                    "unit_id": unit_id,
                    "error": "Unit not found",
                    "unit_type": "unknown",
                    "faction": "unknown",
                    "position": {"col": 0, "row": 0},
                    "status": {
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

            # Safely extract unit type and faction
            try:
                unit_type_value = unit.unit_type.value if unit.unit_type else "unknown"
            except (AttributeError, ValueError):
                unit_type_value = "unknown"

            try:
                faction_value = unit.faction.value if unit.faction else "unknown"
            except (AttributeError, ValueError):
                faction_value = "unknown"

            # Safely extract position info
            position_info = {"col": 0, "row": 0}
            if position:
                try:
                    position_info = {
                        "col": int(position.col) if hasattr(position, "col") else 0,
                        "row": int(position.row) if hasattr(position, "row") else 0,
                    }
                except (AttributeError, ValueError, TypeError):
                    position_info = {"col": 0, "row": 0}

            # Safely extract status info
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
                    pass  # Keep defaults

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

            # Safely extract capability info
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

            # Multi-layer resource info
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

            # Safely extract skill info
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
                "status": status_info,
                "capabilities": capabilities_info,
                "available_skills": available_skills,
            }

        except Exception as e:
            # Fallback: return safe defaults on errors
            return {
                "unit_id": unit_id,
                "error": f"Failed to get unit info: {str(e)}",
                "unit_type": "unknown",
                "faction": "unknown",
                "position": {"col": 0, "row": 0},
                "status": {
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
        """Get the environment visible to the unit."""
        vision = self.world.get_component(unit_id, Vision)
        if not vision:
            return []

        # Get unit position and movement components (for movement-related info)
        unit_position = self.world.get_component(unit_id, HexPosition)
        movement_points = self.world.get_component(unit_id, MovementPoints)
        unit_count = self.world.get_component(unit_id, UnitCount)
        current_pos = (unit_position.col, unit_position.row) if unit_position else None

        visible_tiles = []
        for pos in vision.visible_tiles:
            tile_info = {
                "position": {"col": pos[0], "row": pos[1]},
                "terrain": self._get_terrain_at_position(pos).value,
                "units": self._get_units_at_position(pos),
                "fortifications": self._get_current_fortification_level(pos),
            }

            # Add movement-related info (e.g., for "move"/tactical style observation)
            # if current_pos and movement_points and unit_count:
            move_info = self._calculate_movement_info(
                unit_id, current_pos, pos, movement_points, unit_count
            )
            tile_info["movement_info"] = move_info

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
        """Compute movement info from current position to a target position."""
        # If this is the current position, return a special marker
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
                "path": [current_pos],
            }

        # Compute effective movement (account for headcount loss)
        effective_movement = movement_points.get_effective_movement(unit_count)

        # Get obstacles and compute a path
        obstacles = self._get_obstacles()
        from ..utils.hex_utils import PathFinding

        try:
            # Attempt to find a path
            path = PathFinding.find_path(
                current_pos, target_pos, obstacles, effective_movement
            )

            if path and len(path) > 1:
                # Compute total path cost
                total_movement_cost = self._calculate_total_movement_cost(path)

                # Check reachability
                reachable = total_movement_cost <= movement_points.current_mp

                return {
                    "reachable": reachable,
                    "is_current_position": False,
                    "movement_cost": total_movement_cost,
                    "path_length": len(path) - 1,  # Excludes the starting position
                    "terrain_movement_cost": self._get_terrain_movement_cost(
                        target_pos
                    ),
                    "effective_movement_range": effective_movement,
                    "current_movement_points": movement_points.current_mp,
                    "path": path,
                    "reachable_reason": (
                        "sufficient_movement_points"
                        if reachable
                        else f"need_{total_movement_cost}_have_{movement_points.current_mp}"
                    ),
                }
            else:
                # No path found
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
                    "path": [],
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
                "path": [],
                "reachable_reason": f"path_calculation_error: {str(e)}",
            }

    def _get_tactical_info(self, unit_id: int) -> Dict[str, Any]:
        """Get tactical information."""
        # Simplified placeholder implementation
        return {"threats": [], "opportunities": [], "movement_options": []}

    def _get_faction_units(self, faction: Faction) -> List[int]:
        """Get all unit ids for a faction."""
        units = []
        for entity in self.world.query().with_component(Unit).entities():
            unit = self.world.get_component(entity, Unit)
            if unit and unit.faction == faction:
                units.append(entity)
        return units

    def _is_unit_active(self, unit_id: int) -> bool:
        """Check whether a unit is active (alive)."""
        unit_count = self.world.get_component(unit_id, UnitCount)
        return unit_count and unit_count.current_count > 0

    def _calculate_territory_control(self, faction: Faction) -> int:
        """Calculate territory control percentage."""
        # Simplified placeholder implementation
        return 30  # Fixed placeholder value; should be computed

    def _calculate_resource_summary(self, faction_units: List[int]) -> Dict[str, Any]:
        """Calculate a resource summary."""
        total_manpower = 0
        for unit_id in faction_units:
            unit_count = self.world.get_component(unit_id, UnitCount)
            if unit_count:
                total_manpower += unit_count.current_count

        return {
            "total_manpower": total_manpower,
            "fortification_points": 0,  # Simplified placeholder
            "controlled_cities": 0,  # Simplified placeholder
        }

    def _get_strategic_summary(self, faction: Faction) -> Dict[str, Any]:
        """Get a strategic summary."""
        return {
            "active_battles": 0,
            "territory_threats": [],
            "expansion_opportunities": [],
        }

    # ==================== System accessors ====================

    def _get_movement_system(self):
        """Get the movement system."""
        for system in self.world.systems:
            if system.__class__.__name__ == "MovementSystem":
                return system
        return None

    def _get_combat_system(self):
        """Get the combat system."""
        for system in self.world.systems:
            if system.__class__.__name__ == "CombatSystem":
                return system
        return None

    def _get_action_system(self):
        """Get the action system."""
        for system in self.world.systems:
            if system.__class__.__name__ == "ActionSystem":
                return system
        return None

    def _get_territory_system(self):
        """Get the territory system."""
        for system in self.world.systems:
            if system.__class__.__name__ == "TerritorySystem":
                return system
        return None

    # ==================== Game-logic helpers ====================

    def _get_obstacles(self) -> Set[Tuple[int, int]]:
        """Get movement obstacles (units only)."""
        obstacles = set()
        # Use all unit positions as obstacles
        for entity in self.world.query().with_all(HexPosition, Unit).entities():
            pos = self.world.get_component(entity, HexPosition)
            if pos:
                obstacles.add((pos.col, pos.row))
        return obstacles

    def _get_obstacles_excluding_unit(
        self, exclude_unit_id: int
    ) -> Set[Tuple[int, int]]:
        """Get movement obstacles excluding a given unit (other units only)."""
        obstacles = set()
        # Use all unit positions as obstacles, excluding the specified unit
        for entity in self.world.query().with_all(HexPosition, Unit).entities():
            if entity == exclude_unit_id:
                continue  # Skip the unit being moved
            pos = self.world.get_component(entity, HexPosition)
            if pos:
                obstacles.add((pos.col, pos.row))
        print(f"[DEBUG] Unit obstacles: {len(obstacles)} (excluding unit {exclude_unit_id})")
        return obstacles

    def _get_adjacent_free_positions(
        self, center_pos: Tuple[int, int], obstacles: Set[Tuple[int, int]]
    ) -> List[Tuple[int, int]]:
        """Get free adjacent positions around a center tile."""
        from ..utils.hex_utils import HexMath

        col, row = center_pos

        # 6 adjacent directions in a hex grid
        adjacent_positions = []
        directions = [(1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1)]

        for dx, dy in directions:
            adj_pos = (col + dx, row + dy)
            if adj_pos not in obstacles:
                adjacent_positions.append(adj_pos)

        return adjacent_positions

    def _calculate_total_movement_cost(self, path: List[Tuple[int, int]]) -> int:
        """Calculate total movement cost for a path."""
        total_cost = 0
        for pos in path[1:]:  # Skip the start position
            terrain_cost = self._get_terrain_movement_cost(pos)
            total_cost += terrain_cost
        return total_cost

    def _get_terrain_movement_cost(self, position: Tuple[int, int]) -> int:
        """Get terrain movement cost (movement point cost)."""
        terrain_type = self._get_terrain_at_position(position)

        # Terrain movement cost mapping
        terrain_costs = {
            TerrainType.PLAIN: 1,
            TerrainType.FOREST: 2,
            TerrainType.HILL: 2,
            TerrainType.MOUNTAIN: 3,
            TerrainType.WATER: 99,  # Impassable
            TerrainType.CITY: 1,
            TerrainType.URBAN: 1,
        }

        return terrain_costs.get(terrain_type, 1)

    def _get_path_terrain_breakdown(
        self, path: List[Tuple[int, int]]
    ) -> List[Dict[str, Any]]:
        """Get terrain type and movement cost for each position on a path."""
        breakdown = []

        for i, pos in enumerate(path):
            if i == 0:  # Skip the start position
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
        """Get the terrain type at a given position."""
        map_data = self.world.get_singleton_component(MapData)
        if not map_data:
            return TerrainType.PLAIN

        tile_entity = map_data.tiles.get(position)
        if not tile_entity:
            return TerrainType.PLAIN

        terrain = self.world.get_component(tile_entity, Terrain)
        return terrain.terrain_type if terrain else TerrainType.PLAIN

    def _get_terrain_attack_bonus(
        self, position: Tuple[int, int], faction: Faction
    ) -> float:
        """Get terrain attack bonus."""
        territory_system = self._get_territory_system()
        if territory_system:
            return (
                territory_system.get_territory_attack_bonus(position, faction) / 10.0
            )  # Convert to decimal
        return 0.0

    def _get_max_fortification_level(self, terrain_type: TerrainType) -> int:
        """Get the maximum fortification level for a terrain type."""
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
        """Get the current fortification level at a position."""
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
        """Calculate fortification defense bonus."""
        return level * 0.2  # +20% defense per level

    def _get_units_at_position(self, position: Tuple[int, int]) -> List[Dict[str, Any]]:
        """Get all units at a position."""
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
        """Execute a terrain-dependent skill."""
        # Skill execution logic
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
