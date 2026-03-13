"""
LLM Action Handler - provides executable operation handlers for the LLM system.

Supports unit actions (move/battle/defend/scout, etc.), observation commands, and state/query utilities.
"""

import ast
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
    Terrain,
    Tile,
    BattleLog,
)
from ..prefabs.config import Faction
from ..utils.hex_utils import HexMath


class LLMActionHandler:
    """LLM action handler - a unified interface for unit-executable operations."""

    def __init__(self, world: World):
        self.world = world
        self.supported_actions = {
            # Unit actions
            "move": self.handle_move_action,
            "attack": self.handle_attack_action,
            "defend": self.handle_defend_action,
            "garrison": self.handle_garrison_action,
            "wait": self.handle_wait_action,
            "scout": self.handle_scout_action,
            "retreat": self.handle_retreat_action,
            "fortify": self.handle_fortify_action,
            "patrol": self.handle_patrol_action,
            "end_turn": self.handle_end_turn_action,
            "select_unit": self.handle_select_unit_action,
            "formation": self.handle_formation_action,
            # Observation commands
            "unit_observation": self.handle_unit_observation,
            "faction_observation": self.handle_faction_observation,
            "godview_observation": self.handle_godview_observation,
            "limited_observation": self.handle_limited_observation,
            "tactical_observation": self.handle_tactical_observation,
            # State/query commands
            "get_unit_list": self.handle_get_unit_list,
            "get_unit_info": self.handle_get_unit_info,
            "get_faction_units": self.handle_get_faction_units,
            "get_game_state": self.handle_get_game_state,
            "get_map_info": self.handle_get_map_info,
            "get_battle_status": self.handle_get_battle_status,
            "get_available_actions": self.handle_get_available_actions,
            "get_unit_capabilities": self.handle_get_unit_capabilities,
            "get_visibility_info": self.handle_get_visibility_info,
            "get_strategic_summary": self.handle_get_strategic_summary,
        }

    def execute_action(
        self, action_type: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a specific action."""
        if action_type not in self.supported_actions:
            return {
                "success": False,
                "error": f"Unsupported action type: {action_type}",
                "supported_actions": list(self.supported_actions.keys()),
            }

        try:
            return self.supported_actions[action_type](params)
        except Exception as e:
            return {
                "success": False,
                "error": f"Action execution failed: {str(e)}",
                "action_type": action_type,
                "params": params,
            }

    def get_supported_actions(self) -> Dict[str, Dict[str, Any]]:
        """Get supported actions and their detailed interface metadata."""
        return {
            # Unit actions
            "move": {
                "function_name": "move",
                "function_desc": "Move a unit to a target position",
                "inputs": {
                    "unit_id": {
                        "param_desc": "Unit id to move",
                        "param_type": "int",
                        "required": True,
                    },
                    "target_position": {
                        "param_desc": "Target position coordinates [col, row]",
                        "param_type": "list[int]",
                        "required": True,
                    },
                },
            },
            "attack": {
                "function_name": "attack",
                "function_desc": "Attack a target unit",
                "inputs": {
                    "unit_id": {
                        "param_desc": "Attacker unit id",
                        "param_type": "int",
                        "required": True,
                    },
                    "target_id": {
                        "param_desc": "Target unit id",
                        "param_type": "int",
                        "required": True,
                    },
                },
            },
            "defend": {
                "function_name": "defend",
                "function_desc": "Set a unit to defensive stance",
                "inputs": {
                    "unit_id": {
                        "param_desc": "Unit id to set defending",
                        "param_type": "int",
                        "required": True,
                    }
                },
            },
            "garrison": {
                "function_name": "garrison",
                "function_desc": "Put a unit into garrison to gain defensive bonuses",
                "inputs": {
                    "unit_id": {
                        "param_desc": "Unit id to garrison",
                        "param_type": "int",
                        "required": True,
                    }
                },
            },
            "wait": {
                "function_name": "wait",
                "function_desc": "Wait with a unit and skip this turn",
                "inputs": {
                    "unit_id": {
                        "param_desc": "Unit id to wait",
                        "param_type": "int",
                        "required": True,
                    }
                },
            },
            "scout": {
                "function_name": "scout",
                "function_desc": "Scout a target area",
                "inputs": {
                    "unit_id": {
                        "param_desc": "Unit id that performs scouting",
                        "param_type": "int",
                        "required": True,
                    },
                    "target_position": {
                        "param_desc": "Scout target position [col, row]",
                        "param_type": "list[int]",
                        "required": True,
                    },
                },
            },
            "retreat": {
                "function_name": "retreat",
                "function_desc": "Retreat a unit to a safe position",
                "inputs": {
                    "unit_id": {
                        "param_desc": "Unit id to retreat",
                        "param_type": "int",
                        "required": True,
                    }
                },
            },
            "fortify": {
                "function_name": "fortify",
                "function_desc": "Build fortifications at the current position",
                "inputs": {
                    "unit_id": {
                        "param_desc": "Unit id that builds fortifications",
                        "param_type": "int",
                        "required": True,
                    }
                },
            },
            "patrol": {
                "function_name": "patrol",
                "function_desc": "Patrol within a specified area",
                "inputs": {
                    "unit_id": {
                        "param_desc": "Unit id that performs patrol",
                        "param_type": "int",
                        "required": True,
                    },
                    "patrol_area": {
                        "param_desc": "List of coordinates defining the patrol area",
                        "param_type": "list[list[int]]",
                        "required": True,
                    },
                },
            },
            "end_turn": {
                "function_name": "end_turn",
                "function_desc": "End the current unit's turn",
                "inputs": {
                    "unit_id": {
                        "param_desc": "Unit id whose turn should end",
                        "param_type": "int",
                        "required": True,
                    }
                },
            },
            "select_unit": {
                "function_name": "select_unit",
                "function_desc": "Select a unit",
                "inputs": {
                    "unit_id": {
                        "param_desc": "Unit id to select",
                        "param_type": "int",
                        "required": True,
                    }
                },
            },
            "formation": {
                "function_name": "formation",
                "function_desc": "Set unit formation",
                "inputs": {
                    "unit_id": {
                        "param_desc": "Unit id to set formation for",
                        "param_type": "int",
                        "required": True,
                    },
                    "formation_type": {
                        "param_desc": "Formation type (offensive/defensive/mobile)",
                        "param_type": "str",
                        "required": True,
                    },
                },
            },
            # Observation commands
            "unit_observation": {
                "function_name": "unit_observation",
                "function_desc": "Get observation data for a unit",
                "inputs": {
                    "unit_id": {
                        "param_desc": "Unit id to observe",
                        "param_type": "int",
                        "required": True,
                    }
                },
            },
            "faction_observation": {
                "function_name": "faction_observation",
                "function_desc": "Get observation data for a faction",
                "inputs": {
                    "faction": {
                        "param_desc": "Faction name (WEI/SHU/WU)",
                        "param_type": "str",
                        "required": True,
                    }
                },
            },
            "godview_observation": {
                "function_name": "godview_observation",
                "function_desc": "Get observation data from a global (god) view",
                "inputs": {},
            },
            "limited_observation": {
                "function_name": "limited_observation",
                "function_desc": "Get observation data from a restricted (faction) view",
                "inputs": {
                    "faction": {
                        "param_desc": "Observer faction name (WEI/SHU/WU)",
                        "param_type": "str",
                        "required": True,
                    }
                },
            },
            "tactical_observation": {
                "function_name": "tactical_observation",
                "function_desc": "Get tactical-level observation data",
                "inputs": {
                    "unit_id": {
                        "param_desc": "Center unit id (optional)",
                        "param_type": "int",
                        "required": False,
                    },
                    "radius": {
                        "param_desc": "Observation radius (optional)",
                        "param_type": "int",
                        "required": False,
                    },
                },
            },
            # State/query commands
            "get_unit_list": {
                "function_name": "get_unit_list",
                "function_desc": "List all units",
                "inputs": {
                    "faction": {
                        "param_desc": "Filter units by faction (optional)",
                        "param_type": "str",
                        "required": False,
                    },
                    "unit_type": {
                        "param_desc": "Filter units by unit type (optional)",
                        "param_type": "str",
                        "required": False,
                    },
                },
            },
            "get_unit_info": {
                "function_name": "get_unit_info",
                "function_desc": "Get detailed information for a unit",
                "inputs": {
                    "unit_id": {
                        "param_desc": "Unit id to query",
                        "param_type": "int",
                        "required": True,
                    }
                },
            },
            "get_faction_units": {
                "function_name": "get_faction_units",
                "function_desc": "List all units for a faction",
                "inputs": {
                    "faction": {
                        "param_desc": "Faction name (WEI/SHU/WU)",
                        "param_type": "str",
                        "required": True,
                    }
                },
            },
            "get_game_state": {
                "function_name": "get_game_state",
                "function_desc": "Get current game state",
                "inputs": {},
            },
            "get_map_info": {
                "function_name": "get_map_info",
                "function_desc": "Get map information",
                "inputs": {
                    "position": {
                        "param_desc": "Query map info at a specific position [col, row] (optional)",
                        "param_type": "list[int]",
                        "required": False,
                    },
                    "area": {
                        "param_desc": "Query map info for an area [[min_col, min_row], [max_col, max_row]] (optional)",
                        "param_type": "list[list[int]]",
                        "required": False,
                    },
                },
            },
            "get_battle_status": {
                "function_name": "get_battle_status",
                "function_desc": "Get current battle status",
                "inputs": {
                    "battle_id": {
                        "param_desc": "Specific battle id (optional)",
                        "param_type": "int",
                        "required": False,
                    }
                },
            },
            "get_available_actions": {
                "function_name": "get_available_actions",
                "function_desc": "Get the list of actions available to a unit",
                "inputs": {
                    "unit_id": {
                        "param_desc": "Unit id to query",
                        "param_type": "int",
                        "required": True,
                    }
                },
            },
            "get_unit_capabilities": {
                "function_name": "get_unit_capabilities",
                "function_desc": "Get capabilities for a unit",
                "inputs": {
                    "unit_id": {
                        "param_desc": "Unit id to query",
                        "param_type": "int",
                        "required": True,
                    }
                },
            },
            "get_visibility_info": {
                "function_name": "get_visibility_info",
                "function_desc": "Get vision and visibility information",
                "inputs": {
                    "faction": {
                        "param_desc": "Faction name to query vision for",
                        "param_type": "str",
                        "required": True,
                    },
                    "position": {
                        "param_desc": "Query visibility at a specific position [col, row] (optional)",
                        "param_type": "list[int]",
                        "required": False,
                    },
                },
            },
            "get_strategic_summary": {
                "function_name": "get_strategic_summary",
                "function_desc": "Get a strategic-level summary",
                "inputs": {
                    "faction": {
                        "param_desc": "Faction name to scope the summary to (optional)",
                        "param_type": "str",
                        "required": False,
                    },
                    "detail_level": {
                        "param_desc": "Detail level (basic/detailed/full)",
                        "param_type": "str",
                        "required": False,
                    },
                },
            },
        }

    def handle_move_action(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle the move action."""
        try:
            # Validate and normalize parameter types
            unit_id = params.get("unit_id")
            target_position = params.get("target_position")

            # Required-field / type validation
            if unit_id is None:
                return {
                    "success": False,
                    "error": "Missing required parameter: unit_id",
                    "error_code": "MISSING_PARAM",
                    "action": "move",
                }

            if target_position is None:
                return {
                    "success": False,
                    "error": "Missing required parameter: target_position",
                    "error_code": "MISSING_PARAM",
                    "action": "move",
                }

            # Convert parameter types
            try:
                unit_id = int(unit_id)
            except (ValueError, TypeError):
                return {
                    "success": False,
                    "error": f"Invalid unit_id type: expected int, got {type(unit_id).__name__}",
                    "error_code": "INVALID_TYPE",
                    "action": "move",
                }

            # Handle target_position - support multiple input formats
            if isinstance(target_position, str):
                try:
                    target_position = ast.literal_eval(target_position)
                except (ValueError, SyntaxError):
                    return {
                        "success": False,
                        "error": f"Invalid target_position format: {target_position}",
                        "error_code": "INVALID_FORMAT",
                        "action": "move",
                    }

            if (
                not isinstance(target_position, (list, tuple))
                or len(target_position) != 2
            ):
                return {
                    "success": False,
                    "error": "target_position must be [col, row] or (col, row)",
                    "error_code": "INVALID_FORMAT",
                    "action": "move",
                }

            try:
                target_pos = (int(target_position[0]), int(target_position[1]))
            except (ValueError, TypeError, IndexError):
                return {
                    "success": False,
                    "error": f"Invalid target_position coordinates: {target_position}",
                    "error_code": "INVALID_COORDINATES",
                    "action": "move",
                }

            # Validate that the unit exists
            if not self.world.has_entity(unit_id):
                return {
                    "success": False,
                    "error": f"Unit {unit_id} does not exist",
                    "error_code": "UNIT_NOT_FOUND",
                    "action": "move",
                    "unit_id": unit_id,
                }

            # Get the movement system
            movement_system = self._get_movement_system()
            if not movement_system:
                return {
                    "success": False,
                    "error": "Movement system not available",
                    "error_code": "SYSTEM_UNAVAILABLE",
                    "action": "move",
                }

            # Execute movement - use correct parameter types (entity: int, target_pos: Tuple[int, int])
            success = movement_system.move_unit(unit_id, target_pos)

            if success:
                return {
                    "success": True,
                    "message": f"Unit {unit_id} successfully moved to {target_pos}",
                    "action": "move",
                    "unit_id": unit_id,
                    "new_position": {"col": target_pos[0], "row": target_pos[1]},
                    "target_position": list(target_pos),
                }
            else:
                return {
                    "success": False,
                    "error": "Movement failed - check path, movement points, or obstacles",
                    "error_code": "MOVEMENT_FAILED",
                    "action": "move",
                    "unit_id": unit_id,
                    "target_position": list(target_pos),
                }

        except Exception as e:
            return {
                "success": False,
                "error": f"Unexpected error in move action: {str(e)}",
                "error_code": "INTERNAL_ERROR",
                "action": "move",
                "params": params,
            }

    def handle_attack_action(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle the attack action."""
        try:
            # Validate and normalize parameter types
            unit_id = params.get("unit_id")  # Uses unit_id instead of attacker_id
            target_id = params.get("target_id")

            # Validate required parameters
            if unit_id is None:
                return {
                    "success": False,
                    "error": "Missing required parameter: unit_id",
                    "error_code": "MISSING_PARAM",
                    "action": "attack",
                }

            if target_id is None:
                return {
                    "success": False,
                    "error": "Missing required parameter: target_id",
                    "error_code": "MISSING_PARAM",
                    "action": "attack",
                }

            # Convert parameter types
            try:
                unit_id = int(unit_id)
                target_id = int(target_id)
            except (ValueError, TypeError):
                return {
                    "success": False,
                    "error": f"Invalid parameter types: unit_id and target_id must be integers",
                    "error_code": "INVALID_TYPE",
                    "action": "attack",
                }

            # Validate that entities exist
            if not self.world.has_entity(unit_id):
                return {
                    "success": False,
                    "error": f"Attacker unit {unit_id} does not exist",
                    "error_code": "UNIT_NOT_FOUND",
                    "action": "attack",
                    "unit_id": unit_id,
                }

            if not self.world.has_entity(target_id):
                return {
                    "success": False,
                    "error": f"Target unit {target_id} does not exist",
                    "error_code": "TARGET_NOT_FOUND",
                    "action": "attack",
                    "target_id": target_id,
                }

            # Get the combat system
            combat_system = self._get_combat_system()
            if not combat_system:
                return {
                    "success": False,
                    "error": "Combat system not available",
                    "error_code": "SYSTEM_UNAVAILABLE",
                    "action": "attack",
                }

            # Execute attack - use correct parameter types (attacker_entity: int, target_entity: int)
            success = combat_system.attack(unit_id, target_id)

            if success:
                # Get target unit's remaining headcount
                target_unit_count = self.world.get_component(target_id, UnitCount)
                return {
                    "success": True,
                    "message": f"Unit {unit_id} successfully attacked unit {target_id}",
                    "action": "attack",
                    "attacker_id": unit_id,
                    "target_id": target_id,
                    "target_remaining_count": (
                        target_unit_count.current_count if target_unit_count else 0
                    ),
                }
            else:
                return {
                    "success": False,
                    "error": "Attack failed - check range, action points, or target validity",
                    "error_code": "ATTACK_FAILED",
                    "action": "attack",
                    "attacker_id": unit_id,
                    "target_id": target_id,
                }

        except Exception as e:
            return {
                "success": False,
                "error": f"Unexpected error in attack action: {str(e)}",
                "error_code": "INTERNAL_ERROR",
                "action": "attack",
                "params": params,
            }

    def handle_defend_action(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle the defend action."""
        try:
            # Parameter validation
            unit_id = params.get("unit_id")

            if unit_id is None:
                return {
                    "success": False,
                    "error": "Missing required parameter: unit_id",
                    "error_code": "MISSING_PARAM",
                    "action": "defend",
                }

            # Convert parameter types
            try:
                unit_id = int(unit_id)
            except (ValueError, TypeError):
                return {
                    "success": False,
                    "error": f"Invalid unit_id type: expected int, got {type(unit_id).__name__}",
                    "error_code": "INVALID_TYPE",
                    "action": "defend",
                }

            # Validate that the unit exists
            if not self.world.has_entity(unit_id):
                return {
                    "success": False,
                    "error": f"Unit {unit_id} does not exist",
                    "error_code": "UNIT_NOT_FOUND",
                    "action": "defend",
                    "unit_id": unit_id,
                }

            # Set defending status
            unit_status = self.world.get_component(unit_id, UnitStatus)
            if unit_status:
                unit_status.is_defending = True
                return {
                    "success": True,
                    "message": f"Unit {unit_id} is now defending with bonus",
                    "action": "defend",
                    "unit_id": unit_id,
                    "defense_bonus": 0.5,  # 50% defense bonus
                    "status": "defending",
                }
            else:
                return {
                    "success": False,
                    "error": f"Unit {unit_id} does not have UnitStatus component",
                    "error_code": "COMPONENT_MISSING",
                    "action": "defend",
                    "unit_id": unit_id,
                }

        except Exception as e:
            return {
                "success": False,
                "error": f"Unexpected error in defend action: {str(e)}",
                "error_code": "INTERNAL_ERROR",
                "action": "defend",
                "params": params,
            }

    def handle_garrison_action(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle the garrison action."""
        try:
            # Parameter validation
            unit_id = params.get("unit_id")

            if unit_id is None:
                return {
                    "success": False,
                    "error": "Missing required parameter: unit_id",
                    "error_code": "MISSING_PARAM",
                    "action": "garrison",
                }

            # Convert parameter types
            try:
                unit_id = int(unit_id)
            except (ValueError, TypeError):
                return {
                    "success": False,
                    "error": f"Invalid unit_id type: expected int, got {type(unit_id).__name__}",
                    "error_code": "INVALID_TYPE",
                    "action": "garrison",
                }

            # Validate that the unit exists
            if not self.world.has_entity(unit_id):
                return {
                    "success": False,
                    "error": f"Unit {unit_id} does not exist",
                    "error_code": "UNIT_NOT_FOUND",
                    "action": "garrison",
                    "unit_id": unit_id,
                }

            # Get the action system and execute garrison
            action_system = self._get_action_system()
            if not action_system:
                return {
                    "success": False,
                    "error": "Action system not available",
                    "error_code": "SYSTEM_UNAVAILABLE",
                    "action": "garrison",
                }

            success = action_system.perform_garrison(unit_id)
            if success:
                return {
                    "success": True,
                    "message": f"Unit {unit_id} is now garrisoned with defensive bonuses",
                    "action": "garrison",
                    "unit_id": unit_id,
                    "status": "garrisoned",
                }
            else:
                return {
                    "success": False,
                    "error": "Garrison action failed - check unit status and action points",
                    "error_code": "ACTION_FAILED",
                    "action": "garrison",
                    "unit_id": unit_id,
                }

        except Exception as e:
            return {
                "success": False,
                "error": f"Unexpected error in garrison action: {str(e)}",
                "error_code": "INTERNAL_ERROR",
                "action": "garrison",
                "params": params,
            }

    def handle_wait_action(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle the wait action."""
        try:
            # Parameter validation
            unit_id = params.get("unit_id")

            if unit_id is None:
                return {
                    "success": False,
                    "error": "Missing required parameter: unit_id",
                    "error_code": "MISSING_PARAM",
                    "action": "wait",
                }

            # Convert parameter types
            try:
                unit_id = int(unit_id)
            except (ValueError, TypeError):
                return {
                    "success": False,
                    "error": f"Invalid unit_id type: expected int, got {type(unit_id).__name__}",
                    "error_code": "INVALID_TYPE",
                    "action": "wait",
                }

            # Validate that the unit exists
            if not self.world.has_entity(unit_id):
                return {
                    "success": False,
                    "error": f"Unit {unit_id} does not exist",
                    "error_code": "UNIT_NOT_FOUND",
                    "action": "wait",
                    "unit_id": unit_id,
                }

            # Get the action system and execute wait
            action_system = self._get_action_system()
            if not action_system:
                return {
                    "success": False,
                    "error": "Action system not available",
                    "error_code": "SYSTEM_UNAVAILABLE",
                    "action": "wait",
                }

            success = action_system.perform_wait(unit_id)
            if success:
                return {
                    "success": True,
                    "message": f"Unit {unit_id} is waiting this turn",
                    "action": "wait",
                    "unit_id": unit_id,
                    "status": "waiting",
                }
            else:
                return {
                    "success": False,
                    "error": "Wait action failed - check unit status",
                    "error_code": "ACTION_FAILED",
                    "action": "wait",
                    "unit_id": unit_id,
                }

        except Exception as e:
            return {
                "success": False,
                "error": f"Unexpected error in wait action: {str(e)}",
                "error_code": "INTERNAL_ERROR",
                "action": "wait",
                "params": params,
            }

    def handle_scout_action(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle the scout action."""
        unit_id = params.get("unit_id")
        target_area = params.get("target_area")  # (col, row) or an area range

        if not unit_id:
            return {"success": False, "error": "Missing unit_id"}

        if not self.world.has_entity(unit_id):
            return {"success": False, "error": f"Unit {unit_id} does not exist"}

        # Get unit vision information
        vision = self.world.get_component(unit_id, Vision)
        position = self.world.get_component(unit_id, HexPosition)

        if not vision or not position:
            return {
                "success": False,
                "error": "Unit lacks vision or position component",
            }

        # Execute scouting - temporarily increase sight range
        original_range = vision.sight_range
        vision.sight_range = min(vision.sight_range + 2, 10)  # +2 tiles, capped at 10

        # TODO: Fog-of-war system should be updated here

        return {
            "success": True,
            "message": f"Unit {unit_id} is scouting",
            "unit_id": unit_id,
            "enhanced_vision_range": vision.sight_range,
            "original_vision_range": original_range,
        }

    def handle_retreat_action(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle the retreat action."""
        unit_id = params.get("unit_id")
        retreat_direction = params.get(
            "direction"
        )  # "north", "south", "east", "west", etc.

        if not unit_id:
            return {"success": False, "error": "Missing unit_id"}

        if not self.world.has_entity(unit_id):
            return {"success": False, "error": f"Unit {unit_id} does not exist"}

        position = self.world.get_component(unit_id, HexPosition)
        if not position:
            return {"success": False, "error": "Unit has no position"}

        # Compute retreat target position
        current_pos = (position.col, position.row)
        retreat_pos = self._calculate_retreat_position(current_pos, retreat_direction)

        # Execute movement (retreat)
        movement_system = self._get_movement_system()
        if movement_system:
            success = movement_system.move_unit(unit_id, retreat_pos)
            if success:
                return {
                    "success": True,
                    "message": f"Unit {unit_id} retreated to {retreat_pos}",
                    "unit_id": unit_id,
                    "retreat_position": retreat_pos,
                }

        return {"success": False, "error": "Retreat failed"}

    def handle_fortify_action(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle the fortify action."""
        unit_id = params.get("unit_id")

        if not unit_id:
            return {"success": False, "error": "Missing unit_id"}

        if not self.world.has_entity(unit_id):
            return {"success": False, "error": f"Unit {unit_id} does not exist"}

        # Set fortified status
        unit_status = self.world.get_component(unit_id, UnitStatus)
        if unit_status:
            unit_status.is_fortified = True
            return {
                "success": True,
                "message": f"Unit {unit_id} is now fortified",
                "unit_id": unit_id,
                "fortification_bonus": 0.3,  # 30% defense bonus
            }

        return {"success": False, "error": "Unable to set fortify status"}

    def handle_patrol_action(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle the patrol action."""
        unit_id = params.get("unit_id")
        patrol_points = params.get("patrol_points", [])  # List of patrol path points

        if not unit_id:
            return {"success": False, "error": "Missing unit_id"}

        if not self.world.has_entity(unit_id):
            return {"success": False, "error": f"Unit {unit_id} does not exist"}

        # TODO: Implement patrol path logic
        return {
            "success": True,
            "message": f"Unit {unit_id} started patrolling",
            "unit_id": unit_id,
            "patrol_points": patrol_points,
        }

    def handle_end_turn_action(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle the end-turn action."""
        faction = params.get("faction")

        # Get the turn system
        turn_system = self._get_turn_system()
        if turn_system:
            # TODO: Implement end-turn logic
            return {
                "success": True,
                "message": f"Turn ended for faction {faction}",
                "faction": faction,
            }

        return {"success": False, "error": "Turn system not available"}

    def handle_select_unit_action(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle the select-unit action."""
        unit_id = params.get("unit_id")

        if not unit_id:
            return {"success": False, "error": "Missing unit_id"}

        if not self.world.has_entity(unit_id):
            return {"success": False, "error": f"Unit {unit_id} does not exist"}

        # Clear selection state on other units
        for entity in self.world.query().with_all(Selected).entities():
            self.world.remove_component(entity, Selected)

        # Select the target unit
        self.world.add_component(unit_id, Selected())

        return {
            "success": True,
            "message": f"Unit {unit_id} selected",
            "unit_id": unit_id,
        }

    def handle_formation_action(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle the formation action."""
        unit_ids = params.get("unit_ids", [])
        formation_type = params.get(
            "formation_type", "line"
        )  # "line", "column", "wedge", etc.

        if not unit_ids:
            return {"success": False, "error": "Missing unit_ids"}

        # TODO: Implement formation logic
        return {
            "success": True,
            "message": f"Formation {formation_type} set for {len(unit_ids)} units",
            "unit_ids": unit_ids,
            "formation_type": formation_type,
        }

    # Helper methods
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

    def _get_turn_system(self):
        """Get the turn system."""
        for system in self.world.systems:
            if system.__class__.__name__ == "TurnSystem":
                return system
        return None

    def _get_action_system(self):
        """Get the action system."""
        for system in self.world.systems:
            if system.__class__.__name__ == "ActionSystem":
                return system
        return None

    def _calculate_retreat_position(
        self, current_pos: Tuple[int, int], direction: str
    ) -> Tuple[int, int]:
        """Calculate a retreat position."""
        col, row = current_pos

        direction_map = {
            "north": (0, -1),
            "south": (0, 1),
            "northeast": (1, -1),
            "northwest": (-1, 0),
            "southeast": (1, 0),
            "southwest": (-1, 1),
            "east": (1, 0),
            "west": (-1, 0),
        }

        offset = direction_map.get(direction, (0, -1))  # Default: retreat north
        return (col + offset[0], row + offset[1])

    # =============================================
    # Observation command handlers
    # =============================================

    def handle_unit_observation(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle a unit observation request."""
        unit_id = params.get("unit_id")

        if not unit_id:
            return {"success": False, "error": "Missing unit_id parameter"}

        if not self.world.has_entity(unit_id):
            return {"success": False, "error": f"Unit {unit_id} does not exist"}

        # Get the observation system
        obs_system = self._get_observation_system()
        if obs_system:
            observation = obs_system.get_observation("unit", unit_id=unit_id)
            return {"success": True, "observation": observation}

        # Fallback: if no observation system exists, return basic info
        return {"success": True, "observation": self._get_basic_unit_info(unit_id)}

    def handle_faction_observation(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle a faction observation request."""
        faction = params.get("faction")
        include_hidden = params.get("include_hidden", False)

        if not faction:
            return {"success": False, "error": "Missing faction parameter"}

        # Convert string to the Faction enum
        if isinstance(faction, str):
            try:
                faction = Faction(faction.upper())
            except ValueError:
                return {"success": False, "error": f"Invalid faction: {faction}"}

        obs_system = self._get_observation_system()
        if obs_system:
            observation = obs_system.get_observation(
                "faction", faction=faction, include_hidden=include_hidden
            )
            return {"success": True, "observation": observation}

        return {"success": True, "observation": self._get_basic_faction_info(faction)}

    def handle_godview_observation(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle a god-view observation request."""
        obs_system = self._get_observation_system()
        if obs_system:
            observation = obs_system.get_observation("godview")
            return {"success": True, "observation": observation}

        return {"success": True, "observation": self._get_basic_godview_info()}

    def handle_limited_observation(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle a restricted-view observation request."""
        faction = params.get("faction")

        if not faction:
            return {"success": False, "error": "Missing faction parameter"}

        if isinstance(faction, str):
            try:
                faction = Faction(faction.upper())
            except ValueError:
                return {"success": False, "error": f"Invalid faction: {faction}"}

        obs_system = self._get_observation_system()
        if obs_system:
            observation = obs_system.get_observation("limited", faction=faction)
            return {"success": True, "observation": observation}

        return {"success": True, "observation": self._get_basic_faction_info(faction)}

    def handle_tactical_observation(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle a tactical observation request."""
        center_position = params.get("center_position")
        radius = params.get("radius", 3)
        faction = params.get("faction")

        if not center_position:
            return {"success": False, "error": "Missing center_position parameter"}

        tactical_info = self._get_tactical_area_info(center_position, radius, faction)
        return {"success": True, "observation": tactical_info}

    # =============================================
    # State/query command handlers
    # =============================================

    def handle_get_unit_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """List units."""
        faction_filter = params.get("faction")
        unit_type_filter = params.get("unit_type")
        status_filter = params.get("status")  # "alive", "wounded", "ready"

        unit_list = []
        for entity in self.world.query().with_all(Unit).entities():
            unit = self.world.get_component(entity, Unit)
            position = self.world.get_component(entity, HexPosition)
            unit_count = self.world.get_component(entity, UnitCount)

            if not unit:
                continue

            # Apply filters
            if faction_filter and unit.faction != faction_filter:
                continue
            if unit_type_filter and unit.unit_type != unit_type_filter:
                continue
            if status_filter:
                if (
                    status_filter == "alive"
                    and unit_count
                    and unit_count.current_count <= 0
                ):
                    continue
                elif (
                    status_filter == "wounded"
                    and unit_count
                    and unit_count.current_count < unit_count.max_count
                ):
                    continue
                elif status_filter == "ready":
                    movement = self.world.get_component(entity, MovementPoints)
                    combat = self.world.get_component(entity, Combat)
                    if (movement and movement.has_moved) or (
                        combat and combat.has_attacked
                    ):
                        continue

            unit_info = {
                "id": entity,
                "name": unit.name,
                "faction": (
                    unit.faction.value
                    if hasattr(unit.faction, "value")
                    else str(unit.faction)
                ),
                "type": (
                    unit.unit_type.value
                    if hasattr(unit.unit_type, "value")
                    else str(unit.unit_type)
                ),
            }

            if position:
                unit_info["position"] = {"col": position.col, "row": position.row}
            if unit_count:
                unit_info["unit_count_percentage"] = (
                    unit_count.current_count / unit_count.max_count
                    if unit_count.max_count > 0
                    else 0
                )

            unit_list.append(unit_info)

        return {
            "success": True,
            "units": unit_list,
            "total_count": len(unit_list),
            "filters_applied": {
                "faction": faction_filter,
                "unit_type": unit_type_filter,
                "status": status_filter,
            },
        }

    def handle_get_unit_info(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get detailed information for a unit."""
        unit_id = params.get("unit_id")

        if not unit_id:
            return {"success": False, "error": "Missing unit_id parameter"}

        if not self.world.has_entity(unit_id):
            return {"success": False, "error": f"Unit {unit_id} does not exist"}

        unit_info = self._get_detailed_unit_info(unit_id)
        return {"success": True, "unit_info": unit_info}

    def handle_get_faction_units(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """List all units for a faction."""
        faction = params.get("faction")

        if not faction:
            return {"success": False, "error": "Missing faction parameter"}

        if isinstance(faction, str):
            try:
                faction = Faction(faction.upper())
            except ValueError:
                return {"success": False, "error": f"Invalid faction: {faction}"}

        faction_units = []
        for entity in self.world.query().with_all(Unit).entities():
            unit = self.world.get_component(entity, Unit)
            if unit and unit.faction == faction:
                unit_info = self._get_detailed_unit_info(entity)
                faction_units.append(unit_info)

        return {
            "success": True,
            "faction": faction.value if hasattr(faction, "value") else str(faction),
            "units": faction_units,
            "total_count": len(faction_units),
        }

    def handle_get_game_state(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get game state information."""
        game_state = self.world.get_singleton_component(GameState)

        state_info = {"game_exists": game_state is not None}

        if game_state:
            state_info.update(
                {
                    "current_player": (
                        game_state.current_player.value
                        if hasattr(game_state.current_player, "value")
                        else str(game_state.current_player)
                    ),
                    "game_mode": (
                        game_state.game_mode.value
                        if hasattr(game_state.game_mode, "value")
                        else str(game_state.game_mode)
                    ),
                    "turn_number": getattr(game_state, "turn_number", 1),
                    "phase": getattr(game_state, "phase", "action"),
                    "time_limit": getattr(game_state, "time_limit", None),
                    "victory_condition": getattr(
                        game_state, "victory_condition", "elimination"
                    ),
                }
            )

        return {"success": True, "game_state": state_info}

    def handle_get_map_info(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get map information."""
        include_terrain = params.get("include_terrain", True)
        include_units = params.get("include_units", True)
        area = params.get(
            "area"
        )  # Optional: area bounds {"min_col": 0, "max_col": 10, "min_row": 0, "max_row": 10}

        map_info = {
            "terrain": [] if include_terrain else None,
            "unit_positions": [] if include_units else None,
        }

        if include_terrain:
            # Collect terrain info
            from ..components import Terrain, Tile

            for entity in self.world.query().with_all(Tile, HexPosition).entities():
                position = self.world.get_component(entity, HexPosition)
                tile = self.world.get_component(entity, Tile)
                terrain = self.world.get_component(entity, Terrain)

                if area:
                    if (
                        position.col < area.get("min_col", 0)
                        or position.col > area.get("max_col", 999)
                        or position.row < area.get("min_row", 0)
                        or position.row > area.get("max_row", 999)
                    ):
                        continue

                terrain_info = {
                    "position": {"col": position.col, "row": position.row},
                    "passable": tile.passable if tile else True,
                }

                if terrain:
                    terrain_info.update(
                        {
                            "type": (
                                terrain.terrain_type.value
                                if hasattr(terrain.terrain_type, "value")
                                else str(terrain.terrain_type)
                            ),
                            "movement_cost": terrain.movement_cost,
                            "defense_bonus": terrain.defense_bonus,
                        }
                    )

                map_info["terrain"].append(terrain_info)

        if include_units:
            # Collect unit positions
            for entity in self.world.query().with_all(Unit, HexPosition).entities():
                position = self.world.get_component(entity, HexPosition)
                unit = self.world.get_component(entity, Unit)

                if area:
                    if (
                        position.col < area.get("min_col", 0)
                        or position.col > area.get("max_col", 999)
                        or position.row < area.get("min_row", 0)
                        or position.row > area.get("max_row", 999)
                    ):
                        continue

                unit_pos = {
                    "unit_id": entity,
                    "name": unit.name,
                    "faction": (
                        unit.faction.value
                        if hasattr(unit.faction, "value")
                        else str(unit.faction)
                    ),
                    "position": {"col": position.col, "row": position.row},
                }

                map_info["unit_positions"].append(unit_pos)

        return {"success": True, "map_info": map_info}

    def handle_get_battle_status(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get battle status information."""
        faction = params.get("faction")

        battle_status = {"active_battles": [], "recent_battles": [], "casualties": {}}

        # Check whether a battle log system exists
        from ..components import BattleLog

        battle_log = self.world.get_singleton_component(BattleLog)

        if battle_log and hasattr(battle_log, "entries"):
            recent_entries = battle_log.entries[-5:]  # Last 5 battle entries
            for entry in recent_entries:
                battle_info = {
                    "turn": entry.turn,
                    "attacker": entry.attacker_name,
                    "defender": entry.defender_name,
                    "damage": entry.damage,
                    "result": entry.result,
                }
                battle_status["recent_battles"].append(battle_info)

        # Compute faction casualties (optional)
        if faction:
            if isinstance(faction, str):
                try:
                    faction = Faction(faction.upper())
                except ValueError:
                    pass

            total_units = 0
            wounded_units = 0
            dead_units = 0

            for entity in self.world.query().with_all(Unit).entities():
                unit = self.world.get_component(entity, Unit)
                unit_count = self.world.get_component(entity, UnitCount)

                if unit and unit.faction == faction:
                    total_units += 1
                    if unit_count:
                        if unit_count.current_count <= 0:
                            dead_units += 1
                        elif unit_count.current_count < unit_count.max_count:
                            wounded_units += 1

            battle_status["casualties"] = {
                "total_units": total_units,
                "wounded_units": wounded_units,
                "dead_units": dead_units,
                "full_strength_units": total_units - wounded_units - dead_units,
            }

        return {"success": True, "battle_status": battle_status}

    def handle_get_available_actions(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get available actions."""
        unit_id = params.get("unit_id")

        if unit_id:
            # Get available actions for a specific unit
            if not self.world.has_entity(unit_id):
                return {"success": False, "error": f"Unit {unit_id} does not exist"}

            available_actions = self._get_unit_available_actions(unit_id)
            return {
                "success": True,
                "unit_id": unit_id,
                "available_actions": available_actions,
            }
        else:
            # Return all supported action types
            return {
                "success": True,
                "all_supported_actions": self.get_supported_actions(),
                "action_categories": {
                    "unit_actions": [
                        "move",
                        "attack",
                        "defend",
                        "scout",
                        "retreat",
                        "fortify",
                        "patrol",
                    ],
                    "selection_actions": ["select_unit", "formation"],
                    "game_actions": ["end_turn"],
                    "observation_actions": [
                        "unit_observation",
                        "faction_observation",
                        "godview_observation",
                        "limited_observation",
                        "tactical_observation",
                    ],
                    "query_actions": [
                        "get_unit_list",
                        "get_unit_info",
                        "get_faction_units",
                        "get_game_state",
                        "get_map_info",
                        "get_battle_status",
                        "get_available_actions",
                        "get_unit_capabilities",
                        "get_visibility_info",
                        "get_strategic_summary",
                    ],
                },
            }

    def handle_get_unit_capabilities(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get unit capability information."""
        unit_id = params.get("unit_id")

        if not unit_id:
            return {"success": False, "error": "Missing unit_id parameter"}

        if not self.world.has_entity(unit_id):
            return {"success": False, "error": f"Unit {unit_id} does not exist"}

        capabilities = self._get_unit_capabilities(unit_id)
        return {"success": True, "unit_id": unit_id, "capabilities": capabilities}

    def handle_get_visibility_info(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get vision/visibility information."""
        unit_id = params.get("unit_id")
        faction = params.get("faction")

        if unit_id:
            # Get visibility info for a specific unit
            if not self.world.has_entity(unit_id):
                return {"success": False, "error": f"Unit {unit_id} does not exist"}

            visibility_info = self._get_unit_visibility_info(unit_id)
            return {
                "success": True,
                "unit_id": unit_id,
                "visibility_info": visibility_info,
            }

        elif faction:
            # Get aggregated visibility info for a faction
            if isinstance(faction, str):
                try:
                    faction = Faction(faction.upper())
                except ValueError:
                    return {"success": False, "error": f"Invalid faction: {faction}"}

            faction_visibility = self._get_faction_visibility_info(faction)
            return {
                "success": True,
                "faction": str(faction),
                "visibility_info": faction_visibility,
            }

        else:
            return {"success": False, "error": "Must specify either unit_id or faction"}

    def handle_get_strategic_summary(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get a strategic summary."""
        faction = params.get("faction")

        if faction and isinstance(faction, str):
            try:
                faction = Faction(faction.lower())
            except ValueError:
                return {"success": False, "error": f"Invalid faction: {faction}"}

        strategic_summary = self._get_strategic_summary(faction)
        return {"success": True, "strategic_summary": strategic_summary}

    # =============================================
    # Helper methods - observation & query
    # =============================================

    def _get_observation_system(self):
        """Get the observation system."""
        for system in self.world.systems:
            if system.__class__.__name__ == "LLMObservationSystem":
                return system
        return None

    def _get_basic_unit_info(self, unit_id: int) -> Dict[str, Any]:
        """Get basic unit info (fallback when no observation system is available)."""
        unit = self.world.get_component(unit_id, Unit)
        position = self.world.get_component(unit_id, HexPosition)
        unit_count = self.world.get_component(unit_id, UnitCount)

        if not unit:
            return {"error": "Unit component not found"}

        basic_info = {
            "id": unit_id,
            "name": unit.name,
            "faction": (
                unit.faction.value
                if hasattr(unit.faction, "value")
                else str(unit.faction)
            ),
            "type": (
                unit.unit_type.value
                if hasattr(unit.unit_type, "value")
                else str(unit.unit_type)
            ),
        }

        if position:
            basic_info["position"] = {"col": position.col, "row": position.row}
        if unit_count:
            basic_info["health"] = {
                "current": unit_count.current_count,
                "max": unit_count.max_count,
                "percentage": (
                    unit_count.current_count / unit_count.max_count
                    if unit_count.max_count > 0
                    else 0
                ),
            }

        return basic_info

    def _get_basic_faction_info(self, faction: Faction) -> Dict[str, Any]:
        """Get basic faction info."""
        faction_units = []
        for entity in self.world.query().with_all(Unit).entities():
            unit = self.world.get_component(entity, Unit)
            if unit and unit.faction == faction:
                unit_info = self._get_basic_unit_info(entity)
                faction_units.append(unit_info)

        return {
            "faction": faction.value if hasattr(faction, "value") else str(faction),
            "units": faction_units,
            "unit_count": len(faction_units),
        }

    def _get_basic_godview_info(self) -> Dict[str, Any]:
        """Get basic god-view info."""
        all_units = []
        for entity in self.world.query().with_all(Unit).entities():
            unit_info = self._get_basic_unit_info(entity)
            all_units.append(unit_info)

        return {"all_units": all_units, "total_unit_count": len(all_units)}

    def _get_tactical_area_info(
        self,
        center_position: Tuple[int, int],
        radius: int,
        faction: Optional[Faction] = None,
    ) -> Dict[str, Any]:
        """Get tactical area information."""
        center_col, center_row = center_position
        area_units = []
        area_terrain = []

        # Collect units within the area
        for entity in self.world.query().with_all(Unit, HexPosition).entities():
            position = self.world.get_component(entity, HexPosition)
            unit = self.world.get_component(entity, Unit)

            distance = HexMath.hex_distance(
                (center_col, center_row), (position.col, position.row)
            )
            if distance <= radius:
                unit_info = self._get_basic_unit_info(entity)
                unit_info["distance_from_center"] = distance
                area_units.append(unit_info)

        return {
            "center_position": {"col": center_col, "row": center_row},
            "radius": radius,
            "units_in_area": area_units,
            "unit_count": len(area_units),
        }

    def _get_detailed_unit_info(self, unit_id: int) -> Dict[str, Any]:
        """Get detailed unit information."""
        unit = self.world.get_component(unit_id, Unit)
        position = self.world.get_component(unit_id, HexPosition)
        unit_count = self.world.get_component(unit_id, UnitCount)
        movement = self.world.get_component(unit_id, MovementPoints)
        combat = self.world.get_component(unit_id, Combat)
        vision = self.world.get_component(unit_id, Vision)
        status = self.world.get_component(unit_id, UnitStatus)

        detailed_info = {
            "id": unit_id,
            "name": unit.name if unit else "Unknown",
            "faction": (
                unit.faction.value
                if unit and hasattr(unit.faction, "value")
                else str(unit.faction) if unit else "Unknown"
            ),
            "type": (
                unit.unit_type.value
                if unit and hasattr(unit.unit_type, "value")
                else str(unit.unit_type) if unit else "Unknown"
            ),
        }

        if position:
            detailed_info["position"] = {"col": position.col, "row": position.row}

        if unit_count:
            detailed_info["health"] = {
                "current": unit_count.current_count,
                "max": unit_count.max_count,
                "percentage": (
                    unit_count.current_count / unit_count.max_count
                    if unit_count.max_count > 0
                    else 0
                ),
            }

        if movement:
            detailed_info["movement"] = {
                "current": movement.current_mp,
                "max": movement.max_mp,
                "has_moved": movement.has_moved,
                "remaining_movement": movement.current_mp,
            }

        if combat:
            detailed_info["combat"] = {
                "attack": combat.base_attack,
                "defense": combat.base_defense,
                "range": combat.attack_range,
                "has_attacked": combat.has_attacked,
            }

        if vision:
            detailed_info["vision"] = {"sight_range": vision.sight_range}

        if status:
            detailed_info["status"] = {
                "current_status": status.current_status,
                "is_defending": getattr(status, "is_defending", False),
                "is_fortified": getattr(status, "is_fortified", False),
                "is_moving": getattr(status, "is_moving", False),
                "is_patrolling": getattr(status, "is_patrolling", False),
                "is_scouting": getattr(status, "is_scouting", False),
            }

        return detailed_info

    def _get_unit_available_actions(self, unit_id: int) -> List[str]:
        """Get a unit's available actions."""
        available_actions = []

        movement = self.world.get_component(unit_id, MovementPoints)
        combat = self.world.get_component(unit_id, Combat)
        unit_count = self.world.get_component(unit_id, UnitCount)

        # Check survival status
        if unit_count and unit_count.current_count <= 0:
            return ["dead"]  # Eliminated units cannot act

        # Movement-related actions
        if movement and movement.current_mp > 0 and not movement.has_moved:
            available_actions.extend(["move", "retreat", "scout", "patrol"])

        # Combat-related actions
        if combat and not combat.has_attacked:
            available_actions.append("attack")

        # Always-available actions
        available_actions.extend(["defend", "fortify", "select_unit"])

        return available_actions

    def _get_unit_capabilities(self, unit_id: int) -> Dict[str, Any]:
        """Get unit capabilities."""
        unit = self.world.get_component(unit_id, Unit)
        movement = self.world.get_component(unit_id, MovementPoints)
        combat = self.world.get_component(unit_id, Combat)
        vision = self.world.get_component(unit_id, Vision)

        capabilities = {
            "can_move": movement is not None,
            "can_attack": combat is not None,
            "has_vision": vision is not None,
        }

        if movement:
            capabilities["movement_range"] = movement.current_mp
        if combat:
            capabilities["attack_range"] = combat.attack_range
            capabilities["attack_power"] = combat.base_attack
            capabilities["defense_power"] = combat.base_defense
        if vision:
            capabilities["sight_range"] = vision.sight_range

        return capabilities

    def _get_unit_visibility_info(self, unit_id: int) -> Dict[str, Any]:
        """Get unit visibility information."""
        position = self.world.get_component(unit_id, HexPosition)
        vision = self.world.get_component(unit_id, Vision)

        if not position or not vision:
            return {"error": "Unit lacks position or vision component"}

        # Compute visible area
        visible_positions = set()
        center = (position.col, position.row)

        for col in range(
            position.col - vision.sight_range, position.col + vision.sight_range + 1
        ):
            for row in range(
                position.row - vision.sight_range, position.row + vision.sight_range + 1
            ):
                if HexMath.hex_distance(center, (col, row)) <= vision.sight_range:
                    visible_positions.add((col, row))

        # Collect units within vision
        visible_units = []
        for entity in self.world.query().with_all(Unit, HexPosition).entities():
            if entity == unit_id:  # Skip self
                continue
            other_pos = self.world.get_component(entity, HexPosition)
            if other_pos and (other_pos.col, other_pos.row) in visible_positions:
                other_unit = self.world.get_component(entity, Unit)
                visible_units.append(
                    {
                        "id": entity,
                        "name": other_unit.name if other_unit else "Unknown",
                        "faction": (
                            other_unit.faction.value
                            if other_unit and hasattr(other_unit.faction, "value")
                            else str(other_unit.faction) if other_unit else "Unknown"
                        ),
                        "position": {"col": other_pos.col, "row": other_pos.row},
                    }
                )

        return {
            "sight_range": vision.sight_range,
            "center_position": {"col": position.col, "row": position.row},
            "visible_area_size": len(visible_positions),
            "visible_units": visible_units,
            "visible_unit_count": len(visible_units),
        }

    def _get_faction_visibility_info(self, faction: Faction) -> Dict[str, Any]:
        """Get faction-level visibility information."""
        all_visible_positions = set()
        faction_units = []

        # Aggregate vision of all units in the faction
        for entity in self.world.query().with_all(Unit, HexPosition, Vision).entities():
            unit = self.world.get_component(entity, Unit)
            if unit and unit.faction == faction:
                faction_units.append(entity)
                position = self.world.get_component(entity, HexPosition)
                vision = self.world.get_component(entity, Vision)

                # Compute this unit's visible area
                center = (position.col, position.row)
                for col in range(
                    position.col - vision.sight_range,
                    position.col + vision.sight_range + 1,
                ):
                    for row in range(
                        position.row - vision.sight_range,
                        position.row + vision.sight_range + 1,
                    ):
                        if (
                            HexMath.hex_distance(center, (col, row))
                            <= vision.sight_range
                        ):
                            all_visible_positions.add((col, row))

        # Collect enemy units that are within the visible area
        enemy_units = []
        for entity in self.world.query().with_all(Unit, HexPosition).entities():
            unit = self.world.get_component(entity, Unit)
            position = self.world.get_component(entity, HexPosition)
            if (
                unit
                and unit.faction != faction
                and position
                and (position.col, position.row) in all_visible_positions
            ):
                enemy_units.append(
                    {
                        "id": entity,
                        "name": unit.name,
                        "faction": (
                            unit.faction.value
                            if hasattr(unit.faction, "value")
                            else str(unit.faction)
                        ),
                        "position": {"col": position.col, "row": position.row},
                    }
                )

        return {
            "faction": faction.value if hasattr(faction, "value") else str(faction),
            "observing_units": len(faction_units),
            "total_visible_area": len(all_visible_positions),
            "visible_enemy_units": enemy_units,
            "enemy_unit_count": len(enemy_units),
        }

    def _get_strategic_summary(
        self, faction: Optional[Faction] = None
    ) -> Dict[str, Any]:
        """Get a strategic summary."""
        summary = {"global_stats": {}, "faction_stats": {}}

        # Global stats
        all_units = list(self.world.query().with_all(Unit).entities())
        summary["global_stats"] = {
            "total_units": len(all_units),
            "active_factions": len(
                set(self.world.get_component(e, Unit).faction for e in all_units)
            ),
        }

        # Per-faction stats
        faction_stats = {}
        for entity in all_units:
            unit = self.world.get_component(entity, Unit)
            unit_count = self.world.get_component(entity, UnitCount)
            movement = self.world.get_component(entity, MovementPoints)
            combat = self.world.get_component(entity, Combat)

            faction_name = (
                unit.faction.value
                if hasattr(unit.faction, "value")
                else str(unit.faction)
            )

            if faction_name not in faction_stats:
                faction_stats[faction_name] = {
                    "total_units": 0,
                    "full_strength_units": 0,
                    "wounded_units": 0,
                    "dead_units": 0,
                    "ready_to_move": 0,
                    "ready_to_attack": 0,
                    "total_attack_power": 0,
                    "total_defense_power": 0,
                }

            stats = faction_stats[faction_name]
            stats["total_units"] += 1

            if unit_count:
                if unit_count.current_count <= 0:
                    stats["dead_units"] += 1
                elif unit_count.current_count < unit_count.max_count:
                    stats["wounded_units"] += 1
                else:
                    stats["full_strength_units"] += 1

            if movement and movement.current_mp > 0 and not movement.has_moved:
                stats["ready_to_move"] += 1

            if combat:
                if not combat.has_attacked:
                    stats["ready_to_attack"] += 1
                stats["total_attack_power"] += combat.base_attack
                stats["total_defense_power"] += combat.base_defense

        summary["faction_stats"] = faction_stats

        # If a faction is specified, return details for that faction
        if faction:
            faction_name = faction.value if hasattr(faction, "value") else str(faction)
            summary["target_faction"] = faction_name
            summary["target_faction_details"] = faction_stats.get(faction_name, {})

        return summary
