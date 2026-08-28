"""
LLM Action Handler - Minimal, robust, and efficient action gateway
- Validates inputs and game state consistently
- Provides rich, structured error feedback for LLMs
- Bridges unit/system actions (move, attack, occupy, fortify, skills)
- Observation, faction state queries, and turn control

Designed for clarity and reliability when driven by language models.
"""

import base64
import io
from typing import Dict, List, Any, Optional, Tuple, Set

import pygame
from framework import World
from framework.engine.renders import RenderEngine
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
    ConstructionPoints,
    SkillPoints,
    Terrain,
    Tile,
    BattleLog,
    MapData,
    TerritoryControl,
    FogOfWar,
    GameModeComponent,
    GameStats,
    TeamCoordination,
    MovementAnimation,
)
from ..prefabs.config import (
    Faction,
    UnitType,
    ActionType,
    TerrainType,
    UnitState,
    GameConfig,
)
from ..prefabs.action_catalog import allowed_game_actions
from ..utils.hex_utils import HexMath
from .llm_observation_system import LLMObservationSystem, ObservationLevel


class LLMActionHandler:
    """LLM Action Handler - clean and efficient interface design."""

    def __init__(self, world: World, observation_system: Optional[LLMObservationSystem] = None):
        self.world = world
        self.observation_system = observation_system or LLMObservationSystem(world)

        # Implemented game-level verbs. Match subset is also enforced here
        # so execute_action is not a second door around ActionExecutor.
        self.action_handlers = {
            "move": self.handle_move_action,
            "attack": self.handle_attack_action,
            "rest": self.handle_rest_action,
            "occupy": self.handle_occupy_action,
            "fortify": self.handle_fortify_action,
            "skill": self.handle_skill_action,
            "observation": self.handle_observation_action,
            "limited_observation": self.handle_limited_observation,
            "unit_observation": self.handle_unit_observation,
            "faction_observation": self.handle_faction_observation,
            "godview_observation": self.handle_godview_observation,
            "get_faction_state": self.handle_faction_state,
            "get_faction_state_vlm": self.handle_faction_state_vlm,
            "end_turn": self.handle_end_turn,
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
                    {"error_code": 2010},
                )

            if action_type not in allowed_game_actions(self.world):
                return self._create_error_response(
                    "Operation not supported in current game mode",
                    {"error_code": 2003},
                )

            # dispatch
            print(f"[LLM ACTION HANDLER] Executing action: {action_type} with params: {params}")
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

        # Validate target coordinate types
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
        # print(
        #     f"[MOVE_ACTION] Checking target within map bounds: ({target_col}, {target_row})"
        # )
        if not self._is_position_within_map_bounds(target_col, target_row):
            error_msg = f"Target position ({target_col}, {target_row}) is outside map boundaries"
            print(f"[MOVE_ACTION] Map boundary check failed: {error_msg}")
            map_data = self.world.get_singleton_component(MapData)
            return self._create_error_response(
                error_msg,
                {
                    "target_position": {"col": target_col, "row": target_row},
                    "on_board": False,
                    "tile_count": len(map_data.tiles) if map_data else 0,
                },
            )

        # print(f"[MOVE_ACTION] Target within bounds: ({target_col}, {target_row})")

        # Unit existence check
        # print(f"[MOVE_ACTION] Checking if unit {unit_id} exists...")
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

        # print(
        #     f"[MOVE_ACTION] Unit {unit_id} exists, type: {unit.unit_type.value}, faction: {unit.faction.value}"
        # )

        # === Faction turn permission validation ===
        # print(f"[MOVE_ACTION] Checking faction turn permission for unit {unit_id}...")
        permission_error = self._validate_faction_turn_permission(unit_id, "move")
        if permission_error:
            print(
                f"[MOVE_ACTION] Faction permission denied: {permission_error['message']}"
            )
            return permission_error
        # print(f"[MOVE_ACTION] Faction permission granted for {unit.faction.value}")

        missing = []
        if not self.world.get_component(unit_id, HexPosition):
            missing.append("HexPosition")
        if not self.world.get_component(unit_id, MovementPoints):
            missing.append("MovementPoints")
        if not self.world.get_component(unit_id, UnitCount):
            missing.append("UnitCount")
        if missing:
            error_msg = (
                f"Unit {unit_id} missing required components: {', '.join(missing)}"
            )
            print(f"[MOVE_ACTION] Missing components: {error_msg}")
            return self._create_error_response(
                error_msg,
                {
                    "unit_id": unit_id,
                    "missing_components": missing,
                    "required_components": [
                        "HexPosition",
                        "MovementPoints",
                        "UnitCount",
                    ],
                    "suggestion": "This unit may not be properly initialized",
                },
            )

        movement_system = self._get_movement_system()
        if not movement_system:
            return self._create_error_response(
                "Movement system not available",
                {
                    "unit_id": unit_id,
                    "system_error": "MovementSystem not found",
                    "suggestion": "This is a game engine error - contact administrator",
                },
            )

        target_pos = (target_col, target_row)
        planned = movement_system.move_unit(unit_id, target_pos)
        return self._translate_move_result(unit_id, planned)

    def _translate_move_result(
        self, unit_id: int, planned: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Turn MovementSystem's one plan into the LLM error/success payload."""
        if not planned.get("success"):
            extra = {
                k: v
                for k, v in planned.items()
                if k not in ("success", "message")
            }
            print(f"[MOVE_ACTION] Move failed: {planned.get('message')}")
            return self._create_error_response(
                planned.get("message", "Move failed"), extra
            )

        path = planned.get("path") or []
        current_pos = planned["from"]
        target_pos = planned["to"]
        movement_points = self.world.get_component(unit_id, MovementPoints)
        animation_speed = 2.0
        path_length = max(0, len(path) - 1)
        estimated_duration = (
            path_length / animation_speed if animation_speed > 0 else 0
        )
        remaining = (
            f"{movement_points.current_mp}/{movement_points.max_mp}"
            if movement_points
            else None
        )
        return {
            "success": True,
            "result": True,
            "message": f"Unit {unit_id} has moved from {current_pos} to {target_pos}.",
            "details": f"Unit {unit_id} has moved from {current_pos} to {target_pos}.",
            "action_status": "in_progress",
            "movement_descriptions": {
                "start_position": {"col": current_pos[0], "row": current_pos[1]},
                "target_position": {"col": target_pos[0], "row": target_pos[1]},
                "path": path,
                "path_length": path_length,
            },
            "estimated_duration_seconds": round(estimated_duration, 2),
            "remaining_movement_points": remaining,
        }

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

        # print(f"[ATTACK_ACTION] Params ok: attacker={unit_id}, target={target_id}")

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

        # print(
        #     f"[ATTACK_ACTION] Units exist: {attacker_unit.unit_type.value}({attacker_unit.faction.value}) -> {target_unit.unit_type.value}({target_unit.faction.value})"
        # )

        # === Layer 3: faction turn permission validation ===
        # print(f"[ATTACK_ACTION] Checking faction turn permission for unit {unit_id}...")
        permission_error = self._validate_faction_turn_permission(unit_id, "attack")
        if permission_error:
            print(
                f"[ATTACK_ACTION] Faction permission denied: {permission_error['message']}"
            )
            return permission_error
        # print(
        #     f"[ATTACK_ACTION] Faction permission granted for {attacker_unit.faction.value}"
        # )

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
        # print(f"[ATTACK_ACTION] Checking attacker components...")
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

        # print(f"[ATTACK_ACTION] Checking target components...")
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
        # print(f"[ATTACK_ACTION] Checking action points...")
        if not attacker_action_points.can_perform_action(ActionType.ATTACK):
            required_ap = 1  # requires 1 AP to attack
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
        # print(f"[ATTACK_ACTION] Checking attack range...")
        attacker_current_pos = (attacker_pos.col, attacker_pos.row)
        target_current_pos = (target_pos.col, target_pos.row)
        distance = HexMath.hex_distance(attacker_current_pos, target_current_pos)
        attack_range = attacker_combat.attack_range

        # print(f"[ATTACK_ACTION] Distance={distance}, Attack range={attack_range}")

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
        # print(f"[ATTACK_ACTION] All validations passed, executing attack...")
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
        }

        # Invoke CombatSystem
        attack_result = combat_system.execute_attack(unit_id, target_id)

        if not attack_result.get("success", False):
            return self._create_error_response(
                attack_result.get("message", "Attack execution failed"),
                attack_result.get(
                    "details",
                    {
                        "unit_id": unit_id,
                        "target_id": target_id,
                        "suggestion": "Attack validation passed but execution failed - possible game state conflict",
                    },
                ),
            )

        battle_result = attack_result.get("battle_result", {})

        # === Layer 9: format result ===
        # print(f"[ATTACK_ACTION] Attack executed successfully.")

        # Post-attack snapshot
        post_attack_state = {
            "attacker_action_points": attacker_action_points.current_ap,
            "target_count": target_count.current_count,
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
                "battle_result": battle_result,
                "casualties_inflicted": casualties_inflicted,
                "target_destroyed": target_destroyed,
                "distance": distance,
            },
            "resource_consumption": {
                "action_points_used": action_points_used,
            },
            "remaining_resources": {
                "action_points": post_attack_state["attacker_action_points"],
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
        """Handle the rest (wait) action."""
        unit_id = params.get("unit_id")

        if not isinstance(unit_id, int):
            return self._create_error_response("unit_id must be integer")

        # Validate that the unit exists
        unit = self.world.get_component(unit_id, Unit)
        if not unit:
            return self._create_error_response(f"Unit {unit_id} not found")

        # Faction turn permission validation
        permission_error = self._validate_faction_turn_permission(unit_id, "rest")
        if permission_error:
            return permission_error

        # Rest: increment wait streak. Two waits while confused clears it.
        # Does not consume action points (same as the old ActionSystem wait).
        unit_status = self.world.get_component(unit_id, UnitStatus)
        if not unit_status:
            return self._create_error_response(f"Unit {unit_id} has no status")

        unit_status.wait_turns += 1
        if (
            unit_status.wait_turns >= 2
            and unit_status.current_status == UnitState.CONFUSION
        ):
            unit_status.current_status = UnitState.NORMAL
            unit_status.status_duration = 0

        action_points = self.world.get_component(unit_id, ActionPoints)
        return {
            "success": True,
            "result": True,
            "message": f"Unit {unit_id} is resting and recovering",
            "details": f"Unit {unit_id} is resting and recovering",
            "remaining_action_points": (
                action_points.current_ap if action_points else 0
            ),
        }

    def handle_occupy_action(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle the occupy action - does not consume construction points, but consumes action points."""
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

        # Validate that the unit exists
        unit = self.world.get_component(unit_id, Unit)
        if not unit:
            return self._create_error_response(f"Unit {unit_id} not found")

        # Faction turn permission validation
        permission_error = self._validate_faction_turn_permission(unit_id, "occupy")
        if permission_error:
            return permission_error

        # Check unit position and action points
        unit_pos = self.world.get_component(unit_id, HexPosition)
        action_points = self.world.get_component(unit_id, ActionPoints)

        if not unit_pos:
            return self._create_error_response("Unit missing position component")

        if not action_points or not action_points.can_perform_action(ActionType.OCCUPY):
            return self._create_error_response(
                f"Insufficient action points for occupy: need 1, have {action_points.current_ap if action_points else 0}",
            )

        # Ensure target is current or adjacent position
        current_pos = (unit_pos.col, unit_pos.row)
        target_pos = (col, row)

        from ..utils.hex_utils import HexMath

        distance = HexMath.hex_distance(current_pos, target_pos)

        if distance > 1:
            return self._create_error_response(
                f"Cannot occupy position {target_pos}: too far from unit position {current_pos}. Can only occupy current or adjacent positions.",
            )

        # Check whether the target is already occupied/controlled
        territory_system = self._get_territory_system()
        if not territory_system:
            return self._create_error_response("Territory system not available")

        # Check whether it is already controlled by the unit's faction
        current_control = territory_system.get_territory_control(target_pos)
        if current_control and current_control == unit.faction:
            return self._create_error_response(
                f"Position {target_pos} already controlled by faction {unit.faction.value}",
            )

        # Execute occupy
        success = territory_system.occupy_territory(unit_id, target_pos)

        if success:
            # Consume action points
            action_points.consume_ap(ActionType.OCCUPY)

            # Terrain info (optional)
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
                #     "construction_points_used": 0,  # Occupy does not consume construction points
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
        """Handle the fortify (build fortification) action."""
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

        # Validate that the unit exists
        unit = self.world.get_component(unit_id, Unit)
        if not unit:
            return self._create_error_response(f"Unit {unit_id} not found")

        # Faction turn permission validation
        permission_error = self._validate_faction_turn_permission(unit_id, "fortify")
        if permission_error:
            return permission_error

        # Check action points and construction points
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

        # Get terrain type and fortification level cap
        terrain_type = self._get_terrain_at_position((col, row))
        max_level = self._get_max_fortification_level(terrain_type)

        # Check current fortification level
        current_level = self._get_current_fortification_level((col, row))

        if current_level >= max_level:
            return self._create_error_response(
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
        """Handle the skill action."""
        unit_id = params.get("unit_id")
        skill_name = params.get("skill_name")
        target = params.get("target")

        if not isinstance(unit_id, int):
            return self._create_error_response("unit_id must be integer")

        if not isinstance(skill_name, str):
            return self._create_error_response("skill_name must be string")

        # Validate that the unit exists
        unit = self.world.get_component(unit_id, Unit)
        if not unit:
            return self._create_error_response(f"Unit {unit_id} not found")

        # Faction turn permission validation
        permission_error = self._validate_faction_turn_permission(unit_id, "skill")
        if permission_error:
            return permission_error

        # Check skill-related components
        unit_skills = self.world.get_component(unit_id, UnitSkills)
        skill_points = self.world.get_component(unit_id, SkillPoints)

        if not unit_skills:
            return self._create_error_response("Unit has no skills")

        if not skill_points:
            return self._create_error_response("Unit has no skill points")

        # Check skill availability (UnitSkills controls list & cooldown)
        if not unit_skills.can_use_skill(skill_name):
            if skill_name not in unit_skills.available_skills:
                return self._create_error_response(f"Skill {skill_name} not available")
            else:
                cooldown = unit_skills.skill_cooldowns.get(skill_name, 0)
                return self._create_error_response(
                    f"Skill {skill_name} on cooldown: {cooldown} turns"
                )

        # Check skill points (SkillPoints controls cost)
        if not skill_points.can_use_skill(skill_name, 1):
            return self._create_error_response(
                f"Insufficient skill points: need 1, have {skill_points.current_sp}",
            )

        # Check action points
        action_points = self.world.get_component(unit_id, ActionPoints)
        if not action_points or not action_points.can_perform_action(ActionType.SKILL):
            return self._create_error_response(
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

            if skill_result.get("result", False):
                # Consume resources: multi-layer resource system
                # 1) Action points (decision layer)
                action_points.consume_ap(ActionType.SKILL)

                # 2) Skill points (execution layer)
                skill_points.use_skill(skill_name, 1, skill_result.get("cooldown", 0))

                # 3) Cooldown (via UnitSkills)
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

        # Validate that the unit exists
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

    def _named_observation(self, level, params: Dict[str, Any]) -> Dict[str, Any]:
        """Board query via the shared observation system (revision cache)."""
        faction = params.get("faction")
        unit_id = params.get("unit_id")
        include_hidden = params.get("include_hidden", False)

        if faction and isinstance(faction, str):
            try:
                faction = Faction(faction.lower())
            except ValueError:
                return self._create_error_response(f"Invalid faction: {faction}")

        if level == ObservationLevel.UNIT:
            if not isinstance(unit_id, int):
                return self._create_error_response("unit_id must be integer")
            return self.observation_system.get_observation(
                ObservationLevel.UNIT, unit_id=unit_id
            )

        if level == ObservationLevel.FACTION:
            if not faction:
                return self._create_error_response("faction parameter required")
            return self.observation_system.get_observation(
                ObservationLevel.FACTION, faction=faction, include_hidden=include_hidden
            )

        if level == ObservationLevel.LIMITED:
            if not faction:
                return self._create_error_response("faction parameter required")
            return self.observation_system.get_observation(
                ObservationLevel.LIMITED, faction=faction
            )

        if level == ObservationLevel.GODVIEW:
            return self.observation_system.get_observation(ObservationLevel.GODVIEW)

        return self._create_error_response(f"Unknown observation level: {level}")

    def handle_limited_observation(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return self._named_observation(ObservationLevel.LIMITED, params)

    def handle_unit_observation(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return self._named_observation(ObservationLevel.UNIT, params)

    def handle_faction_observation(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return self._named_observation(ObservationLevel.FACTION, params)

    def handle_godview_observation(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return self._named_observation(ObservationLevel.GODVIEW, params)

    # ==================== Faction control ====================

    def handle_faction_state(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Intelligence in the current shared vision for the observer faction.

        ``units`` is the observer's full army (command panel), each with
        ``reachable`` (legal ``move`` targets now) and ``attackable``
        (legal ``attack`` target ids now). Masks are own-units only.
        ``visible_enemy_units`` is every living enemy in the current vision:
        union of that faction's unit vision while fog is on; the whole map
        when fog is off (key 1). Human, BOT, and agents share this switch.
        ``visible_terrain`` is the same tile set: type and movement cost.
        ``params.faction`` must be the observer. Cross-faction queries
        are rejected (2005); they are not an intelligence channel.
        Formation centers live on the join-time map briefing, not here.
        """
        faction_str = params.get("faction")

        if not faction_str:
            return self._create_error_response("faction parameter required")

        try:
            requested = Faction(faction_str)
        except ValueError:
            return self._create_error_response(f"Invalid faction: {faction_str}")

        agent_id = params.get("agent_id")
        observer = self._observer_faction(agent_id, requested)
        if observer != requested:
            return self._create_error_response(
                (
                    f"Agent is registered to {observer.value}; "
                    f"get_faction_state only reports that faction's screen. "
                    f"Visible enemies are in visible_enemy_units."
                ),
                {
                    "error_code": 2005,
                    "registered_faction": observer.value,
                    "requested_faction": requested.value,
                },
            )

        print(f"Handling faction state for {observer.value}")

        faction_units = self._get_faction_units(observer)
        total_units_count = len(faction_units)
        alive_units = [u for u in faction_units if self._is_unit_alive(u)]
        alive_units_count = len(alive_units)
        actionable_units = [u for u in alive_units if self._can_unit_take_action(u)]
        actionable_units_count = len(actionable_units)

        faction_status = self._get_faction_status(observer)
        units = []
        for unit_id in alive_units:
            info = self._get_detailed_unit_info(unit_id)
            info.update(self._unit_command_fields(unit_id, agent_id, observer))
            units.append(info)

        fog_lifted = self._is_fog_lifted()
        visible_enemies = self._visible_enemy_units(observer, fog_lifted)
        visible_terrain = self._visible_terrain(observer, fog_lifted)
        enemy_ids = [e["unit_id"] for e in visible_enemies]
        for info in units:
            unit_id = info.get("unit_id")
            if not isinstance(unit_id, int):
                info["reachable"] = []
                info["attackable"] = []
                continue
            info["reachable"] = self._unit_reachable(unit_id)
            info["attackable"] = self._unit_attackable(unit_id, enemy_ids)

        print(
            f"[FACTION_STATE] Completed for {observer.value} "
            f"fog={'disabled' if fog_lifted else 'active'} "
            f"own={alive_units_count} visible_enemies={len(visible_enemies)}"
        )
        return {
            "success": True,
            "result": True,
            "state": faction_status,
            "faction": observer.value,
            "fog": "disabled" if fog_lifted else "active",
            "total_units": total_units_count,
            "alive_units": alive_units_count,
            "actionable_units": actionable_units_count,
            "units": units,
            "visible_enemy_units": visible_enemies,
            "visible_terrain": visible_terrain,
        }

    def _observer_faction(
        self, agent_id: Optional[str], requested: Faction
    ) -> Faction:
        """Registered agent identity wins; BOT / no agent_id uses the request."""
        if not agent_id:
            return requested
        stats = self.world.get_singleton_component(GameStats)
        if stats and getattr(stats, "agent_id_to_faction", None):
            mapped = stats.agent_id_to_faction.get(agent_id)
            if mapped is not None:
                return mapped
        return requested

    def _is_fog_lifted(self) -> bool:
        """True when FogOfWar.enabled is False (or the component is missing)."""
        fog = self.world.get_singleton_component(FogOfWar)
        return fog is None or not fog.enabled

    def _visible_enemy_units(
        self, observer: Faction, fog_lifted: bool
    ) -> List[Dict[str, Any]]:
        visible_tiles: Optional[Set[Tuple[int, int]]] = None
        if not fog_lifted:
            fog = self.world.get_singleton_component(FogOfWar)
            visible_tiles = set(fog.faction_vision.get(observer, set())) if fog else set()

        enemies: List[Dict[str, Any]] = []
        for entity in self.world.query().with_all(Unit, HexPosition).entities():
            unit = self.world.get_component(entity, Unit)
            if not unit or unit.faction == observer:
                continue
            if not self._is_unit_alive(entity):
                continue
            position = self.world.get_component(entity, HexPosition)
            if position is None:
                continue
            if visible_tiles is not None and (position.col, position.row) not in visible_tiles:
                continue
            enemies.append(self._visible_enemy_unit_info(entity, unit, position))
        return enemies

    def _visible_terrain(
        self, observer: Faction, fog_lifted: bool
    ) -> List[Dict[str, Any]]:
        """Terrain on currently visible hexes (all tiles when fog is off)."""
        map_data = self.world.get_singleton_component(MapData)
        if not map_data:
            return []

        if fog_lifted:
            hexes = set(map_data.tiles)
        else:
            fog = self.world.get_singleton_component(FogOfWar)
            vision = set(fog.faction_vision.get(observer, set())) if fog else set()
            hexes = vision.intersection(map_data.tiles)

        tiles: List[Dict[str, Any]] = []
        for col, row in sorted(hexes):
            tile_entity = map_data.tiles.get((col, row))
            if not tile_entity:
                continue
            terrain = self.world.get_component(tile_entity, Terrain)
            if not terrain:
                continue
            from ..components.terrain import effect_for

            terrain_type = (
                terrain.terrain_type.value
                if hasattr(terrain.terrain_type, "value")
                else str(terrain.terrain_type)
            )
            effect = effect_for(terrain.terrain_type)
            tiles.append(
                {
                    "col": int(col),
                    "row": int(row),
                    "type": terrain_type,
                    "movement_cost": int(effect.movement_cost),
                    "passable": effect.movement_cost < 999,
                }
            )
        return tiles

    def _unit_reachable(self, unit_id: int) -> List[Dict[str, int]]:
        """Positions where ``move(unit_id, target)`` succeeds on this snapshot."""
        position = self.world.get_component(unit_id, HexPosition)
        movement_points = self.world.get_component(unit_id, MovementPoints)
        unit_count = self.world.get_component(unit_id, UnitCount)
        if not position or not movement_points or not unit_count:
            return []

        anim = self.world.get_component(unit_id, MovementAnimation)
        if anim is not None and anim.is_moving:
            return []

        unit_status = self.world.get_component(unit_id, UnitStatus)
        if unit_status is not None:
            status = unit_status.current_status
            confused = (
                status == UnitState.CONFUSION
                or status == UnitState.CONFUSION.value
            )
            if confused:
                return []

        if movement_points.current_mp <= 0:
            return []

        budget = min(
            int(movement_points.get_effective_movement(unit_count)),
            int(movement_points.current_mp),
        )
        start = (int(position.col), int(position.row))
        from ..utils.map_query import reachable_hexes

        hexes = reachable_hexes(
            self.world, start, budget, exclude_entity=unit_id
        )
        hexes.discard(start)
        return [{"col": col, "row": row} for col, row in sorted(hexes)]

    def _unit_attackable(
        self, unit_id: int, visible_enemy_ids: List[int]
    ) -> List[int]:
        """``target_id``s where ``attack(unit_id, target)`` succeeds now."""
        combat = self._attack_oracle()
        attackable = [
            target_id
            for target_id in visible_enemy_ids
            if combat.can_attack(unit_id, target_id)
        ]
        attackable.sort()
        return attackable

    def _attack_oracle(self):
        """CombatSystem already on the world, or a world-bound oracle."""
        existing = self._get_combat_system()
        if existing is not None:
            return existing
        from .combat_system import CombatSystem

        oracle = CombatSystem()
        oracle.world = self.world
        return oracle

    def _visible_enemy_unit_info(
        self, unit_id: int, unit: Unit, position: HexPosition
    ) -> Dict[str, Any]:
        """What a human would read off a visible enemy sprite: id, type, tile, count."""
        unit_count = self.world.get_component(unit_id, UnitCount)
        unit_type = (
            unit.unit_type.value
            if unit.unit_type and hasattr(unit.unit_type, "value")
            else str(unit.unit_type)
        )
        faction_value = (
            unit.faction.value
            if unit.faction and hasattr(unit.faction, "value")
            else str(unit.faction)
        )
        current_count = (
            int(unit_count.current_count)
            if unit_count and hasattr(unit_count, "current_count")
            else 0
        )
        return {
            "unit_id": unit_id,
            "unit_type": unit_type,
            "faction": faction_value,
            "position": {"col": int(position.col), "row": int(position.row)},
            "unit_status": {"current_count": current_count},
        }

    def _unit_command_fields(
        self,
        unit_id: int,
        agent_id: Optional[str],
        queried_faction: Faction,
    ) -> Dict[str, Any]:
        """``owner`` is who claimed; ``commandable`` is who may order.

        Own-faction unclaimed units remain commandable. The query is always
        the observer's faction; this helper does not serve enemy census.
        """
        coord = self.world.get_singleton_component(TeamCoordination)
        owner = coord.owner_of(unit_id) if coord is not None else None
        if not agent_id:
            return {"owner": owner, "commandable": True}

        stats = self.world.get_singleton_component(GameStats)
        mapped = None
        if stats and getattr(stats, "agent_id_to_faction", None):
            mapped = stats.agent_id_to_faction.get(agent_id)
        same_faction = mapped is None or mapped == queried_faction
        authorized = True if coord is None else coord.is_authorized(agent_id, unit_id)
        return {
            "owner": owner,
            "commandable": bool(same_faction and authorized),
        }

    def _capture_frame_base64(self) -> Tuple[Optional[str], Optional[str]]:
        """
        Capture the current rendered frame from the display and return as base64 PNG.
        For VLM: the agent can decode and pass to a vision model.

        Returns:
            (base64_str, None) on success; (None, error_message) on failure.
        """
        try:
            re = RenderEngine()
            screen = re.screen
        except Exception as e:
            return None, f"RenderEngine/screen not available: {e}"

        try:
            surf = screen.copy()
        except Exception as e:
            return None, f"Screen copy failed: {e}"

        try:
            buf = io.BytesIO()
            pygame.image.save(surf, buf)
            b64 = base64.b64encode(buf.getvalue()).decode("ascii")
            return b64, None
        except Exception as e:
            return None, f"Encode frame to base64 failed: {e}"

    def handle_faction_state_vlm(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Same JSON as ``get_faction_state``, plus a full-board PNG."""
        payload = self.handle_faction_state(params)
        if not payload.get("success"):
            return payload

        frame_b64, frame_err = self._capture_frame_base64()
        payload["frame_base64"] = frame_b64
        payload["frame_format"] = "png" if frame_b64 else None
        if frame_err is not None:
            payload["frame_error"] = frame_err

        print(
            f"[FACTION_STATE_VLM] Completed for {payload.get('faction')}, "
            f"frame={'ok' if frame_b64 else 'failed'}"
        )
        return payload

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
        """Validate whether the unit's faction has permission to act this turn.

        Args:
            unit_id: Unit id
            action_name: Action name (used for error messages)

        Returns:
            Dict: Error response dict on failure; None on success.
        """
        # Validate that the unit exists
        unit = self.world.get_component(unit_id, Unit)
        if not unit:
            return self._create_error_response(
                f"Unit {unit_id} not found", {"unit_id": unit_id, "action": action_name}
            )

        # Check game mode
        game_mode = self.world.get_singleton_component(GameModeComponent)
        is_realtime = game_mode and game_mode.is_real_time()

        # In real-time mode all factions can act concurrently, so skip turn checks
        if is_realtime:
            return None

        # Get the currently active faction (turn-based mode only)
        current_player = self._get_current_player()
        if not current_player:
            return self._create_error_response(
                "Unable to determine current player",
                {"unit_id": unit_id, "action": action_name},
            )

        # Check whether it's this faction's turn
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

        # Validation passed: None means no error
        return None

    def _get_detailed_unit_info(self, unit_id: int) -> Dict[str, Any]:
        """Get detailed unit information with safe fallbacks."""
        try:

            if not isinstance(unit_id, int) or unit_id < 0:
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
                        "properties": {
                            "attack_range": 1,
                            "attack_power": 10,
                            "vision_range": 2,
                        },
                        "unit_resources": {
                            "action_points": 0,
                            "max_action_points": 2,
                            "movement_points": 0,
                            "max_movement_points": 3,
                        },
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
                        "properties": {
                            "attack_range": 1,
                            "attack_power": 10,
                            "vision_range": 2,
                        },
                        "unit_resources": {
                            "action_points": 0,
                            "max_action_points": 2,
                            "movement_points": 0,
                            "max_movement_points": 3,
                        },
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
                                float(unit_count.ratio * 100)
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
                "properties": {
                    "attack_range": 1,
                    "attack_power": 10,  # Default attack power
                    "vision_range": 2,
                },
                "unit_resources": {
                    "remaining_action_points": 0,
                    # "max_action_points": 2,
                    "remaining_movement_points": 0,
                    # "max_movement_points": 3,
                },
            }

            if movement_points:
                try:
                    capabilities_info["unit_resources"]["remaining_movement_points"] = (
                        int(movement_points.current_mp)
                        if hasattr(movement_points, "current_mp")
                        else 0
                    )
                except (AttributeError, ValueError, TypeError):
                    pass

            if combat:
                try:
                    capabilities_info["properties"]["attack_range"] = (
                        int(combat.attack_range)
                        if hasattr(combat, "attack_range")
                        else 1
                    )
                    capabilities_info["properties"]["attack_power"] = (
                        int(combat.base_attack)
                        if hasattr(combat, "base_attack")
                        else 10
                    )
                    # Add defense info after attack info
                    capabilities_info["properties"]["defense"] = (
                        int(combat.base_defense)
                        if hasattr(combat, "base_defense")
                        else 5
                    )
                except (AttributeError, ValueError, TypeError):
                    pass

            if vision:
                try:
                    capabilities_info["properties"]["vision_range"] = (
                        int(vision.range) if hasattr(vision, "range") else 2
                    )
                except (AttributeError, ValueError, TypeError):
                    pass

            if action_points:
                try:
                    capabilities_info["unit_resources"].update(
                        {
                            "remaining_action_points": (
                                int(action_points.current_ap)
                                if hasattr(action_points, "current_ap")
                                else 0
                            ),
                            # "max_action_points": (
                            #     int(action_points.max_ap) # not used
                            #     if hasattr(action_points, "max_ap")
                            #     else 2
                            # ),
                        }
                    )
                except (AttributeError, ValueError, TypeError):
                    pass

            if construction_points:

                pass

            if skill_points:
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
                    "properties": {
                        "attack_range": 1,
                        "attack_power": 10,
                        "vision_range": 2,
                    },
                    "unit_resources": {
                        "remaining_action_points": 0,
                        # "max_action_points": 2,
                        "remaining_movement_points": 0,
                        # "max_movement_points": 3,
                    },
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
                    current_pos, pos, combat, unit_id=unit_id
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

        # Get obstacles and compute a path
        from ..utils.map_query import plan_hex_path

        try:
            path = plan_hex_path(
                self.world,
                current_pos,
                target_pos,
                exclude_entity=unit_id,
                max_cost=effective_movement,
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
        # Simplified placeholder implementation
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
        # Simplified placeholder implementation
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

    def _get_obstacles_excluding_unit(
        self, exclude_unit_id: int
    ) -> Set[Tuple[int, int]]:
        """Other units + impassable terrain, matching MovementSystem."""
        from ..utils.map_query import movement_obstacles

        return movement_obstacles(self.world, exclude_unit_id)

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
        from ..components.terrain import movement_cost_at

        return movement_cost_at(self.world, position)

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
        """True when the hex exists on the generated map."""
        map_data = self.world.get_singleton_component(MapData)
        if map_data is None:
            return True
        return (col, row) in map_data.tiles

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
            return "eliminated"  # Eliminated

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
            # Check for recent battle activity
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

        # Determine whether the tile can be occupied (not controlled by own faction)
        can_occupy = not is_friendly if unit_faction else False

        # Terrain occupation bonus
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
                "remaining_movement_points": 0,
            }

        if current_pos == target_pos:
            return {
                "reachable": True,
                "reason": "current_position",
                "movement_cost": 0,
                "remaining_movement_points": movement_points.current_mp,
                "is_current_position": True,
            }

        effective_movement = movement_points.get_effective_movement(unit_count)

        obstacles = self._get_obstacles_excluding_unit(unit_id)
        if target_pos in obstacles:
            return {
                "reachable": False,
                "reason": "position_occupied",
                "movement_cost": -1,
                "remaining_movement_points": movement_points.current_mp,
                "blocked_by": "other_unit",
            }

        # Try to find a path
        try:
            from ..utils.map_query import plan_hex_path

            path = plan_hex_path(
                self.world,
                current_pos,
                target_pos,
                exclude_entity=unit_id,
                max_cost=effective_movement,
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
                    "remaining_movement_points": movement_points.current_mp,
                    "effective_movement_range": effective_movement,
                }
        except Exception as e:
            return {
                "reachable": False,
                "reason": f"path_calculation_error",
                "movement_cost": -1,
                "remaining_movement_points": movement_points.current_mp,
                "error": str(e),
            }

    def _get_attack_range_info(
        self,
        current_pos: Tuple[int, int],
        target_pos: Tuple[int, int],
        combat: Combat,
        unit_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Attack-range information between current and target tiles.

        `in_attack_range` is geometric (Combat.in_attack_range).
        `can_attack` is unit readiness AND in range, via CombatSystem.
        """
        if not current_pos or not combat:
            return {
                "in_attack_range": False,
                "distance": -1,
                "attack_range": 0,
                "can_attack": False,
            }

        distance = HexMath.hex_distance(current_pos, target_pos)
        in_range = combat.in_attack_range(distance)

        if unit_id is not None:
            combat_system = self._get_combat_system()
            unit_ready = (
                combat_system.can_attack(unit_id)
                if combat_system
                else True
            )
        else:
            unit_ready = True

        return {
            "in_attack_range": in_range,
            "distance": distance,
            "attack_range": combat.attack_range,
            "can_attack": bool(unit_ready and in_range),
        }
