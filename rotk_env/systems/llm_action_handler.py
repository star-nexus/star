"""
LLM Action Handler - 为LLM系统提供可执行操作的handle
处理move、battle、defend、scout等各种单位动作
支持观测相关指令和状态查询功能
"""

import ast
import time
from typing import Dict, List, Any, Optional, Tuple, Set
from framework import World
from ..components import (
    Unit,
    Health,
    HexPosition,
    Movement,
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
    """LLM动作处理器 - 提供单位可执行操作的统一接口"""

    def __init__(self, world: World):
        self.world = world
        self.supported_actions = {
            # 单位动作
            "move": self.handle_move_action,
            "attack": self.handle_attack_action,
            "defend": self.handle_defend_action,
            "scout": self.handle_scout_action,
            "retreat": self.handle_retreat_action,
            "fortify": self.handle_fortify_action,
            "patrol": self.handle_patrol_action,
            "end_turn": self.handle_end_turn_action,
            "select_unit": self.handle_select_unit_action,
            "formation": self.handle_formation_action,
            # 观测相关指令
            "unit_observation": self.handle_unit_observation,
            "faction_observation": self.handle_faction_observation,
            "godview_observation": self.handle_godview_observation,
            "limited_observation": self.handle_limited_observation,
            "tactical_observation": self.handle_tactical_observation,
            # 状态查询指令
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
        """执行指定动作"""
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
        """获取支持的动作列表及其详细信息"""
        return {
            # 单位动作
            "move": {
                "function_name": "move",
                "function_desc": "移动单位到指定位置",
                "inputs": {
                    "unit_id": {
                        "param_desc": "要移动的单位ID",
                        "param_type": "int",
                        "required": True,
                    },
                    "target_position": {
                        "param_desc": "目标位置坐标 [col, row]",
                        "param_type": "list[int]",
                        "required": True,
                    },
                },
            },
            "attack": {
                "function_name": "attack",
                "function_desc": "攻击指定目标单位",
                "inputs": {
                    "unit_id": {
                        "param_desc": "攻击方单位ID",
                        "param_type": "int",
                        "required": True,
                    },
                    "target_id": {
                        "param_desc": "目标单位ID",
                        "param_type": "int",
                        "required": True,
                    },
                },
            },
            "defend": {
                "function_name": "defend",
                "function_desc": "设置单位为防御状态",
                "inputs": {
                    "unit_id": {
                        "param_desc": "要设置防御的单位ID",
                        "param_type": "int",
                        "required": True,
                    }
                },
            },
            "scout": {
                "function_name": "scout",
                "function_desc": "侦察指定区域",
                "inputs": {
                    "unit_id": {
                        "param_desc": "执行侦察的单位ID",
                        "param_type": "int",
                        "required": True,
                    },
                    "target_position": {
                        "param_desc": "侦察目标位置 [col, row]",
                        "param_type": "list[int]",
                        "required": True,
                    },
                },
            },
            "retreat": {
                "function_name": "retreat",
                "function_desc": "单位撤退到安全位置",
                "inputs": {
                    "unit_id": {
                        "param_desc": "要撤退的单位ID",
                        "param_type": "int",
                        "required": True,
                    }
                },
            },
            "fortify": {
                "function_name": "fortify",
                "function_desc": "在当前位置构建防御工事",
                "inputs": {
                    "unit_id": {
                        "param_desc": "执行构建的单位ID",
                        "param_type": "int",
                        "required": True,
                    }
                },
            },
            "patrol": {
                "function_name": "patrol",
                "function_desc": "在指定区域执行巡逻任务",
                "inputs": {
                    "unit_id": {
                        "param_desc": "执行巡逻的单位ID",
                        "param_type": "int",
                        "required": True,
                    },
                    "patrol_area": {
                        "param_desc": "巡逻区域的坐标列表",
                        "param_type": "list[list[int]]",
                        "required": True,
                    },
                },
            },
            "end_turn": {
                "function_name": "end_turn",
                "function_desc": "结束当前单位的回合",
                "inputs": {
                    "unit_id": {
                        "param_desc": "要结束回合的单位ID",
                        "param_type": "int",
                        "required": True,
                    }
                },
            },
            "select_unit": {
                "function_name": "select_unit",
                "function_desc": "选择指定单位",
                "inputs": {
                    "unit_id": {
                        "param_desc": "要选择的单位ID",
                        "param_type": "int",
                        "required": True,
                    }
                },
            },
            "formation": {
                "function_name": "formation",
                "function_desc": "设置单位阵型",
                "inputs": {
                    "unit_id": {
                        "param_desc": "要设置阵型的单位ID",
                        "param_type": "int",
                        "required": True,
                    },
                    "formation_type": {
                        "param_desc": "阵型类型 (offensive/defensive/mobile)",
                        "param_type": "str",
                        "required": True,
                    },
                },
            },
            # 观测相关指令
            "unit_observation": {
                "function_name": "unit_observation",
                "function_desc": "获取指定单位的观测信息",
                "inputs": {
                    "unit_id": {
                        "param_desc": "要观测的单位ID",
                        "param_type": "int",
                        "required": True,
                    }
                },
            },
            "faction_observation": {
                "function_name": "faction_observation",
                "function_desc": "获取指定阵营的观测信息",
                "inputs": {
                    "faction": {
                        "param_desc": "阵营名称 (WEI/SHU/WU)",
                        "param_type": "str",
                        "required": True,
                    }
                },
            },
            "godview_observation": {
                "function_name": "godview_observation",
                "function_desc": "获取全局视角的观测信息",
                "inputs": {},
            },
            "limited_observation": {
                "function_name": "limited_observation",
                "function_desc": "获取受限视角的观测信息",
                "inputs": {
                    "faction": {
                        "param_desc": "观测方阵营名称 (WEI/SHU/WU)",
                        "param_type": "str",
                        "required": True,
                    }
                },
            },
            "tactical_observation": {
                "function_name": "tactical_observation",
                "function_desc": "获取战术层面的观测信息",
                "inputs": {
                    "unit_id": {
                        "param_desc": "观测中心的单位ID",
                        "param_type": "int",
                        "required": False,
                    },
                    "radius": {
                        "param_desc": "观测半径",
                        "param_type": "int",
                        "required": False,
                    },
                },
            },
            # 状态查询指令
            "get_unit_list": {
                "function_name": "get_unit_list",
                "function_desc": "获取所有单位的列表",
                "inputs": {
                    "faction": {
                        "param_desc": "筛选指定阵营的单位 (可选)",
                        "param_type": "str",
                        "required": False,
                    },
                    "unit_type": {
                        "param_desc": "筛选指定类型的单位 (可选)",
                        "param_type": "str",
                        "required": False,
                    },
                },
            },
            "get_unit_info": {
                "function_name": "get_unit_info",
                "function_desc": "获取指定单位的详细信息",
                "inputs": {
                    "unit_id": {
                        "param_desc": "要查询的单位ID",
                        "param_type": "int",
                        "required": True,
                    }
                },
            },
            "get_faction_units": {
                "function_name": "get_faction_units",
                "function_desc": "获取指定阵营的所有单位",
                "inputs": {
                    "faction": {
                        "param_desc": "阵营名称 (WEI/SHU/WU)",
                        "param_type": "str",
                        "required": True,
                    }
                },
            },
            "get_game_state": {
                "function_name": "get_game_state",
                "function_desc": "获取当前游戏状态信息",
                "inputs": {},
            },
            "get_map_info": {
                "function_name": "get_map_info",
                "function_desc": "获取地图信息",
                "inputs": {
                    "position": {
                        "param_desc": "查询特定位置的地图信息 [col, row] (可选)",
                        "param_type": "list[int]",
                        "required": False,
                    },
                    "area": {
                        "param_desc": "查询区域范围 [[min_col, min_row], [max_col, max_row]] (可选)",
                        "param_type": "list[list[int]]",
                        "required": False,
                    },
                },
            },
            "get_battle_status": {
                "function_name": "get_battle_status",
                "function_desc": "获取当前战斗状态信息",
                "inputs": {
                    "battle_id": {
                        "param_desc": "特定战斗ID (可选)",
                        "param_type": "int",
                        "required": False,
                    }
                },
            },
            "get_available_actions": {
                "function_name": "get_available_actions",
                "function_desc": "获取指定单位可执行的动作列表",
                "inputs": {
                    "unit_id": {
                        "param_desc": "要查询的单位ID",
                        "param_type": "int",
                        "required": True,
                    }
                },
            },
            "get_unit_capabilities": {
                "function_name": "get_unit_capabilities",
                "function_desc": "获取指定单位的能力信息",
                "inputs": {
                    "unit_id": {
                        "param_desc": "要查询的单位ID",
                        "param_type": "int",
                        "required": True,
                    }
                },
            },
            "get_visibility_info": {
                "function_name": "get_visibility_info",
                "function_desc": "获取视野和可见性信息",
                "inputs": {
                    "faction": {
                        "param_desc": "查询指定阵营的视野信息",
                        "param_type": "str",
                        "required": True,
                    },
                    "position": {
                        "param_desc": "查询特定位置的可见性 [col, row] (可选)",
                        "param_type": "list[int]",
                        "required": False,
                    },
                },
            },
            "get_strategic_summary": {
                "function_name": "get_strategic_summary",
                "function_desc": "获取战略层面的摘要信息",
                "inputs": {
                    "faction": {
                        "param_desc": "查询指定阵营的战略摘要 (可选)",
                        "param_type": "str",
                        "required": False,
                    },
                    "detail_level": {
                        "param_desc": "详细程度 (basic/detailed/full)",
                        "param_type": "str",
                        "required": False,
                    },
                },
            },
        }

    def handle_move_action(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理移动动作"""
        unit_id = params.get("unit_id")
        target_pos = params.get("target_position")  # (col, row)
        unit_id = int(unit_id)
        target_pos = ast.literal_eval(target_pos)
        if not unit_id or not target_pos:
            return {"success": False, "error": "Missing unit_id or target_position"}

        # 验证单位存在
        if not self.world.has_entity(unit_id):
            return {"success": False, "error": f"Unit {unit_id} does not exist"}

        # 获取移动系统
        movement_system = self._get_movement_system()
        if not movement_system:
            return {"success": False, "error": "Movement system not available"}

        # 执行移动
        success = movement_system.move_unit(unit_id, tuple(target_pos))

        if success:
            return {
                "success": True,
                "message": f"Unit {unit_id} moved to {target_pos}",
                "unit_id": unit_id,
                "new_position": target_pos,
            }
        else:
            return {
                "success": False,
                "error": "Movement failed - check path, movement points, or obstacles",
                "unit_id": unit_id,
                "target_position": target_pos,
            }

    def handle_attack_action(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理攻击动作"""
        attacker_id = params.get("attacker_id")
        target_id = params.get("target_id")

        if not attacker_id or not target_id:
            return {"success": False, "error": "Missing attacker_id or target_id"}

        # 验证单位存在
        if not self.world.has_entity(attacker_id) or not self.world.has_entity(
            target_id
        ):
            return {"success": False, "error": "One or both units do not exist"}

        # 获取战斗系统
        combat_system = self._get_combat_system()
        if not combat_system:
            return {"success": False, "error": "Combat system not available"}

        # 执行攻击
        success = combat_system.attack(attacker_id, target_id)

        if success:
            # 获取目标单位当前血量
            target_health = self.world.get_component(target_id, Health)
            return {
                "success": True,
                "message": f"Unit {attacker_id} attacked unit {target_id}",
                "attacker_id": attacker_id,
                "target_id": target_id,
                "target_remaining_health": (
                    target_health.current if target_health else 0
                ),
            }
        else:
            return {
                "success": False,
                "error": "Attack failed - check range, action points, or target validity",
                "attacker_id": attacker_id,
                "target_id": target_id,
            }

    def handle_defend_action(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理防御动作"""
        unit_id = params.get("unit_id")

        if not unit_id:
            return {"success": False, "error": "Missing unit_id"}

        if not self.world.has_entity(unit_id):
            return {"success": False, "error": f"Unit {unit_id} does not exist"}

        # 设置防御状态
        unit_status = self.world.get_component(unit_id, UnitStatus)
        if unit_status:
            unit_status.is_defending = True
            return {
                "success": True,
                "message": f"Unit {unit_id} is now defending",
                "unit_id": unit_id,
                "defense_bonus": 0.5,  # 50% 防御加成
            }

        return {"success": False, "error": "Unable to set defend status"}

    def handle_scout_action(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理侦察动作"""
        unit_id = params.get("unit_id")
        target_area = params.get("target_area")  # (col, row) 或区域范围

        if not unit_id:
            return {"success": False, "error": "Missing unit_id"}

        if not self.world.has_entity(unit_id):
            return {"success": False, "error": f"Unit {unit_id} does not exist"}

        # 获取单位视野信息
        vision = self.world.get_component(unit_id, Vision)
        position = self.world.get_component(unit_id, HexPosition)

        if not vision or not position:
            return {
                "success": False,
                "error": "Unit lacks vision or position component",
            }

        # 执行侦察 - 临时增加视野范围
        original_range = vision.sight_range
        vision.sight_range = min(vision.sight_range + 2, 10)  # 增加2格视野，最大10格

        # TODO: 这里应该更新雾战系统

        return {
            "success": True,
            "message": f"Unit {unit_id} is scouting",
            "unit_id": unit_id,
            "enhanced_vision_range": vision.sight_range,
            "original_vision_range": original_range,
        }

    def handle_retreat_action(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理撤退动作"""
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

        # 计算撤退目标位置
        current_pos = (position.col, position.row)
        retreat_pos = self._calculate_retreat_position(current_pos, retreat_direction)

        # 执行移动（撤退）
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
        """处理驻防/加固动作"""
        unit_id = params.get("unit_id")

        if not unit_id:
            return {"success": False, "error": "Missing unit_id"}

        if not self.world.has_entity(unit_id):
            return {"success": False, "error": f"Unit {unit_id} does not exist"}

        # 设置驻防状态
        unit_status = self.world.get_component(unit_id, UnitStatus)
        if unit_status:
            unit_status.is_fortified = True
            return {
                "success": True,
                "message": f"Unit {unit_id} is now fortified",
                "unit_id": unit_id,
                "fortification_bonus": 0.3,  # 30% 防御加成
            }

        return {"success": False, "error": "Unable to set fortify status"}

    def handle_patrol_action(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理巡逻动作"""
        unit_id = params.get("unit_id")
        patrol_points = params.get("patrol_points", [])  # 巡逻路径点列表

        if not unit_id:
            return {"success": False, "error": "Missing unit_id"}

        if not self.world.has_entity(unit_id):
            return {"success": False, "error": f"Unit {unit_id} does not exist"}

        # TODO: 实现巡逻路径系统
        return {
            "success": True,
            "message": f"Unit {unit_id} started patrolling",
            "unit_id": unit_id,
            "patrol_points": patrol_points,
        }

    def handle_end_turn_action(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理结束回合动作"""
        faction = params.get("faction")

        # 获取回合系统
        turn_system = self._get_turn_system()
        if turn_system:
            # TODO: 实现结束回合逻辑
            return {
                "success": True,
                "message": f"Turn ended for faction {faction}",
                "faction": faction,
            }

        return {"success": False, "error": "Turn system not available"}

    def handle_select_unit_action(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理选择单位动作"""
        unit_id = params.get("unit_id")

        if not unit_id:
            return {"success": False, "error": "Missing unit_id"}

        if not self.world.has_entity(unit_id):
            return {"success": False, "error": f"Unit {unit_id} does not exist"}

        # 清除其他单位的选择状态
        for entity in self.world.query().with_all(Selected).entities():
            self.world.remove_component(entity, Selected)

        # 选择目标单位
        self.world.add_component(unit_id, Selected())

        return {
            "success": True,
            "message": f"Unit {unit_id} selected",
            "unit_id": unit_id,
        }

    def handle_formation_action(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理阵型动作"""
        unit_ids = params.get("unit_ids", [])
        formation_type = params.get(
            "formation_type", "line"
        )  # "line", "column", "wedge", etc.

        if not unit_ids:
            return {"success": False, "error": "Missing unit_ids"}

        # TODO: 实现阵型系统
        return {
            "success": True,
            "message": f"Formation {formation_type} set for {len(unit_ids)} units",
            "unit_ids": unit_ids,
            "formation_type": formation_type,
        }

    # 辅助方法
    def _get_movement_system(self):
        """获取移动系统"""
        for system in self.world.systems:
            if system.__class__.__name__ == "MovementSystem":
                return system
        return None

    def _get_combat_system(self):
        """获取战斗系统"""
        for system in self.world.systems:
            if system.__class__.__name__ == "CombatSystem":
                return system
        return None

    def _get_turn_system(self):
        """获取回合系统"""
        for system in self.world.systems:
            if system.__class__.__name__ == "TurnSystem":
                return system
        return None

    def _calculate_retreat_position(
        self, current_pos: Tuple[int, int], direction: str
    ) -> Tuple[int, int]:
        """计算撤退位置"""
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

        offset = direction_map.get(direction, (0, -1))  # 默认向北撤退
        return (col + offset[0], row + offset[1])

    # =============================================
    # 观测相关指令处理方法
    # =============================================

    def handle_unit_observation(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理单位观测请求"""
        unit_id = params.get("unit_id")

        if not unit_id:
            return {"success": False, "error": "Missing unit_id parameter"}

        if not self.world.has_entity(unit_id):
            return {"success": False, "error": f"Unit {unit_id} does not exist"}

        # 获取观测系统
        obs_system = self._get_observation_system()
        if obs_system:
            observation = obs_system.get_observation("unit", unit_id=unit_id)
            return {"success": True, "observation": observation}

        # 如果没有观测系统，返回基本信息
        return {"success": True, "observation": self._get_basic_unit_info(unit_id)}

    def handle_faction_observation(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理阵营观测请求"""
        faction = params.get("faction")
        include_hidden = params.get("include_hidden", False)

        if not faction:
            return {"success": False, "error": "Missing faction parameter"}

        # 转换字符串到Faction枚举
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
        """处理上帝视角观测请求"""
        obs_system = self._get_observation_system()
        if obs_system:
            observation = obs_system.get_observation("godview")
            return {"success": True, "observation": observation}

        return {"success": True, "observation": self._get_basic_godview_info()}

    def handle_limited_observation(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理受限观测请求"""
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
        """处理战术观测请求"""
        center_position = params.get("center_position")
        radius = params.get("radius", 3)
        faction = params.get("faction")

        if not center_position:
            return {"success": False, "error": "Missing center_position parameter"}

        tactical_info = self._get_tactical_area_info(center_position, radius, faction)
        return {"success": True, "observation": tactical_info}

    # =============================================
    # 状态查询指令处理方法
    # =============================================

    def handle_get_unit_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """获取单位列表"""
        faction_filter = params.get("faction")
        unit_type_filter = params.get("unit_type")
        status_filter = params.get("status")  # "alive", "wounded", "ready"

        unit_list = []
        for entity in self.world.query().with_all(Unit).entities():
            unit = self.world.get_component(entity, Unit)
            position = self.world.get_component(entity, HexPosition)
            health = self.world.get_component(entity, Health)

            if not unit:
                continue

            # 应用过滤条件
            if faction_filter and unit.faction != faction_filter:
                continue
            if unit_type_filter and unit.unit_type != unit_type_filter:
                continue
            if status_filter:
                if status_filter == "alive" and health and health.current <= 0:
                    continue
                elif (
                    status_filter == "wounded"
                    and health
                    and health.current >= health.maximum
                ):
                    continue
                elif status_filter == "ready":
                    movement = self.world.get_component(entity, Movement)
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
            if health:
                unit_info["health_percentage"] = (
                    health.current / health.maximum if health.maximum > 0 else 0
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
        """获取指定单位的详细信息"""
        unit_id = params.get("unit_id")

        if not unit_id:
            return {"success": False, "error": "Missing unit_id parameter"}

        if not self.world.has_entity(unit_id):
            return {"success": False, "error": f"Unit {unit_id} does not exist"}

        unit_info = self._get_detailed_unit_info(unit_id)
        return {"success": True, "unit_info": unit_info}

    def handle_get_faction_units(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """获取指定阵营的所有单位"""
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
        """获取游戏状态信息"""
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
        """获取地图信息"""
        include_terrain = params.get("include_terrain", True)
        include_units = params.get("include_units", True)
        area = params.get(
            "area"
        )  # 可选：指定区域 {"min_col": 0, "max_col": 10, "min_row": 0, "max_row": 10}

        map_info = {
            "terrain": [] if include_terrain else None,
            "unit_positions": [] if include_units else None,
        }

        if include_terrain:
            # 获取地形信息
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
            # 获取单位位置
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
        """获取战斗状态信息"""
        faction = params.get("faction")

        battle_status = {"active_battles": [], "recent_battles": [], "casualties": {}}

        # 检查是否有战斗日志系统
        from ..components import BattleLog

        battle_log = self.world.get_singleton_component(BattleLog)

        if battle_log and hasattr(battle_log, "entries"):
            recent_entries = battle_log.entries[-5:]  # 最近5次战斗
            for entry in recent_entries:
                battle_info = {
                    "turn": entry.turn,
                    "attacker": entry.attacker_name,
                    "defender": entry.defender_name,
                    "damage": entry.damage,
                    "result": entry.result,
                }
                battle_status["recent_battles"].append(battle_info)

        # 统计阵营伤亡情况
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
                health = self.world.get_component(entity, Health)

                if unit and unit.faction == faction:
                    total_units += 1
                    if health:
                        if health.current <= 0:
                            dead_units += 1
                        elif health.current < health.maximum:
                            wounded_units += 1

            battle_status["casualties"] = {
                "total_units": total_units,
                "wounded_units": wounded_units,
                "dead_units": dead_units,
                "healthy_units": total_units - wounded_units - dead_units,
            }

        return {"success": True, "battle_status": battle_status}

    def handle_get_available_actions(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """获取可用动作列表"""
        unit_id = params.get("unit_id")

        if unit_id:
            # 获取指定单位的可用动作
            if not self.world.has_entity(unit_id):
                return {"success": False, "error": f"Unit {unit_id} does not exist"}

            available_actions = self._get_unit_available_actions(unit_id)
            return {
                "success": True,
                "unit_id": unit_id,
                "available_actions": available_actions,
            }
        else:
            # 返回所有支持的动作类型
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
        """获取单位能力信息"""
        unit_id = params.get("unit_id")

        if not unit_id:
            return {"success": False, "error": "Missing unit_id parameter"}

        if not self.world.has_entity(unit_id):
            return {"success": False, "error": f"Unit {unit_id} does not exist"}

        capabilities = self._get_unit_capabilities(unit_id)
        return {"success": True, "unit_id": unit_id, "capabilities": capabilities}

    def handle_get_visibility_info(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """获取视野信息"""
        unit_id = params.get("unit_id")
        faction = params.get("faction")

        if unit_id:
            # 获取指定单位的视野信息
            if not self.world.has_entity(unit_id):
                return {"success": False, "error": f"Unit {unit_id} does not exist"}

            visibility_info = self._get_unit_visibility_info(unit_id)
            return {
                "success": True,
                "unit_id": unit_id,
                "visibility_info": visibility_info,
            }

        elif faction:
            # 获取阵营整体视野信息
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
        """获取战略摘要"""
        faction = params.get("faction")

        if faction and isinstance(faction, str):
            try:
                faction = Faction(faction.upper())
            except ValueError:
                return {"success": False, "error": f"Invalid faction: {faction}"}

        strategic_summary = self._get_strategic_summary(faction)
        return {"success": True, "strategic_summary": strategic_summary}

    # =============================================
    # 辅助方法 - 观测和查询相关
    # =============================================

    def _get_observation_system(self):
        """获取观测系统"""
        for system in self.world.systems:
            if system.__class__.__name__ == "LLMObservationSystem":
                return system
        return None

    def _get_basic_unit_info(self, unit_id: int) -> Dict[str, Any]:
        """获取基本单位信息（无观测系统时的后备方案）"""
        unit = self.world.get_component(unit_id, Unit)
        position = self.world.get_component(unit_id, HexPosition)
        health = self.world.get_component(unit_id, Health)

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
        if health:
            basic_info["health"] = {
                "current": health.current,
                "max": health.maximum,
                "percentage": (
                    health.current / health.maximum if health.maximum > 0 else 0
                ),
            }

        return basic_info

    def _get_basic_faction_info(self, faction: Faction) -> Dict[str, Any]:
        """获取基本阵营信息"""
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
        """获取基本上帝视角信息"""
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
        """获取战术区域信息"""
        center_col, center_row = center_position
        area_units = []
        area_terrain = []

        # 获取区域内的单位
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
        """获取详细单位信息"""
        unit = self.world.get_component(unit_id, Unit)
        position = self.world.get_component(unit_id, HexPosition)
        health = self.world.get_component(unit_id, Health)
        movement = self.world.get_component(unit_id, Movement)
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

        if health:
            detailed_info["health"] = {
                "current": health.current,
                "max": health.maximum,
                "percentage": (
                    health.current / health.maximum if health.maximum > 0 else 0
                ),
            }

        if movement:
            detailed_info["movement"] = {
                "current": movement.current_movement,
                "max": movement.max_movement,
                "has_moved": movement.has_moved,
                "remaining_movement": movement.current_movement,
            }

        if combat:
            detailed_info["combat"] = {
                "attack": combat.attack,
                "defense": combat.defense,
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
        """获取单位可用动作"""
        available_actions = []

        movement = self.world.get_component(unit_id, Movement)
        combat = self.world.get_component(unit_id, Combat)
        health = self.world.get_component(unit_id, Health)

        # 检查生存状态
        if health and health.current <= 0:
            return ["dead"]  # 已死亡单位无法执行动作

        # 移动相关动作
        if movement and movement.current_movement > 0 and not movement.has_moved:
            available_actions.extend(["move", "retreat", "scout", "patrol"])

        # 战斗相关动作
        if combat and not combat.has_attacked:
            available_actions.append("attack")

        # 总是可用的动作
        available_actions.extend(["defend", "fortify", "select_unit"])

        return available_actions

    def _get_unit_capabilities(self, unit_id: int) -> Dict[str, Any]:
        """获取单位能力信息"""
        unit = self.world.get_component(unit_id, Unit)
        movement = self.world.get_component(unit_id, Movement)
        combat = self.world.get_component(unit_id, Combat)
        vision = self.world.get_component(unit_id, Vision)

        capabilities = {
            "can_move": movement is not None,
            "can_attack": combat is not None,
            "has_vision": vision is not None,
        }

        if movement:
            capabilities["movement_range"] = movement.max_movement
        if combat:
            capabilities["attack_range"] = combat.attack_range
            capabilities["attack_power"] = combat.attack
            capabilities["defense_power"] = combat.defense
        if vision:
            capabilities["sight_range"] = vision.sight_range

        return capabilities

    def _get_unit_visibility_info(self, unit_id: int) -> Dict[str, Any]:
        """获取单位视野信息"""
        position = self.world.get_component(unit_id, HexPosition)
        vision = self.world.get_component(unit_id, Vision)

        if not position or not vision:
            return {"error": "Unit lacks position or vision component"}

        # 计算可见区域
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

        # 获取视野内的单位
        visible_units = []
        for entity in self.world.query().with_all(Unit, HexPosition).entities():
            if entity == unit_id:  # 跳过自己
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
        """获取阵营视野信息"""
        all_visible_positions = set()
        faction_units = []

        # 收集阵营所有单位的视野
        for entity in self.world.query().with_all(Unit, HexPosition, Vision).entities():
            unit = self.world.get_component(entity, Unit)
            if unit and unit.faction == faction:
                faction_units.append(entity)
                position = self.world.get_component(entity, HexPosition)
                vision = self.world.get_component(entity, Vision)

                # 计算该单位的可见区域
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

        # 获取视野内的敌方单位
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
        """获取战略摘要"""
        summary = {"global_stats": {}, "faction_stats": {}}

        # 全局统计
        all_units = list(self.world.query().with_all(Unit).entities())
        summary["global_stats"] = {
            "total_units": len(all_units),
            "active_factions": len(
                set(self.world.get_component(e, Unit).faction for e in all_units)
            ),
        }

        # 按阵营统计
        faction_stats = {}
        for entity in all_units:
            unit = self.world.get_component(entity, Unit)
            health = self.world.get_component(entity, Health)
            movement = self.world.get_component(entity, Movement)
            combat = self.world.get_component(entity, Combat)

            faction_name = (
                unit.faction.value
                if hasattr(unit.faction, "value")
                else str(unit.faction)
            )

            if faction_name not in faction_stats:
                faction_stats[faction_name] = {
                    "total_units": 0,
                    "healthy_units": 0,
                    "wounded_units": 0,
                    "dead_units": 0,
                    "ready_to_move": 0,
                    "ready_to_attack": 0,
                    "total_attack_power": 0,
                    "total_defense_power": 0,
                }

            stats = faction_stats[faction_name]
            stats["total_units"] += 1

            if health:
                if health.current <= 0:
                    stats["dead_units"] += 1
                elif health.current < health.maximum:
                    stats["wounded_units"] += 1
                else:
                    stats["healthy_units"] += 1

            if movement and movement.current_movement > 0 and not movement.has_moved:
                stats["ready_to_move"] += 1

            if combat:
                if not combat.has_attacked:
                    stats["ready_to_attack"] += 1
                stats["total_attack_power"] += combat.attack
                stats["total_defense_power"] += combat.defense

        summary["faction_stats"] = faction_stats

        # 如果指定了阵营，返回该阵营的详细信息
        if faction:
            faction_name = faction.value if hasattr(faction, "value") else str(faction)
            summary["target_faction"] = faction_name
            summary["target_faction_details"] = faction_stats.get(faction_name, {})

        return summary
