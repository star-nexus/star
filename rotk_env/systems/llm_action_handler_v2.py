"""
LLM Action Handler V2 - 符合API规范的新版动作处理器
完全按照ROTK_UNIT_ACTION_API_SPECIFICATION.md实现

主要改进:
1. 接入各个系统的基础功能，统一封装成符合接口的格式
2. 详细的错误反馈机制，让LLM知道决策错误的具体原因
3. 标准化的JSON请求/响应格式
4. 完整的前置条件检查和限制验证
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
    ActionPoints,  # 这现在指向新的多层次ActionPoints
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
    """LLM动作处理器V2 - 符合API规范标准"""

    def __init__(self, world: World):
        self.world = world
        self.api_version = "v1.0"

        # 错误代码映射
        self.error_codes = {
            1001: "单位不存在",
            1002: "动作点不足",
            1003: "目标超出范围",
            1004: "无效的目标位置",
            1005: "单位状态不允许该动作",
            1006: "技能冷却中",
            1007: "地形不支持该动作",
            1008: "阵营不匹配",
            1009: "游戏状态不允许",
            1010: "参数格式错误",
        }

        # 支持的动作映射
        self.action_handlers = {
            # 单位控制动作
            "move": self.handle_move_action,
            "attack": self.handle_attack_action,
            "wait": self.handle_wait_action,
            "garrison": self.handle_garrison_action,
            "capture": self.handle_capture_action,
            "fortify": self.handle_fortify_action,
            "skill": self.handle_skill_action,
            # 观测动作
            "unit_observation": self.handle_unit_observation,
            "get_unit_info": self.handle_get_unit_info,
            # 阵营控制动作
            "faction_state": self.handle_faction_state,
            # "faction_unit_action": self.handle_faction_unit_action,
            # "faction_batch_actions": self.handle_faction_batch_actions,
            # System
            "action_list": self.handle_action_list,
        }

    def execute_action(
        self, action_type: str, params: Dict[str, Any] = {}
    ) -> Dict[str, Any]:
        """执行动作的统一入口点"""
        try:
            # 解析动作数据
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

            # 执行具体动作
            print(f"Executing action: {action_type} with params: {params}")
            return self.action_handlers[action_type](params)

        except Exception as e:
            return self._create_error_response(
                1010, f"Action execution failed: {str(e)}"
            )

    # ==================== 单位控制动作 ====================

    def handle_move_action(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理移动动作 - 按多层次资源系统设计，增强错误反馈"""
        print(f"[MOVE_ACTION] 开始处理移动动作，参数: {params}")

        # 详细参数验证与反馈
        unit_id = params.get("unit_id")
        target_position = params.get("target_position")

        print(
            f"[MOVE_ACTION] 解析参数: unit_id={unit_id}, target_position={target_position}"
        )

        if not isinstance(unit_id, int):
            error_msg = (
                f"Invalid unit_id type: expected int, got {type(unit_id).__name__}"
            )
            print(f"[MOVE_ACTION] 参数验证失败: {error_msg}")
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
            print(f"[MOVE_ACTION] 参数验证失败: {error_msg}")
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
            print(f"[MOVE_ACTION] 坐标验证失败: {error_msg}")
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

        # 详细单位存在性检查
        print(f"[MOVE_ACTION] 检查单位 {unit_id} 是否存在...")
        unit = self.world.get_component(unit_id, Unit)
        if not unit:
            error_msg = f"Unit {unit_id} not found in world"
            print(f"[MOVE_ACTION] 单位不存在: {error_msg}")
            # 获取所有存在的单位ID作为参考
            all_units = []
            for entity_id in self.world.entities:
                if self.world.get_component(entity_id, Unit):
                    all_units.append(entity_id)

            return self._create_error_response(
                1001,
                error_msg,
                {
                    "requested_unit_id": unit_id,
                    "available_unit_ids": all_units[:10],  # 限制显示前10个
                    "total_units_in_world": len(all_units),
                    "suggestion": "Use faction_state action to see all units for a faction",
                },
            )

        print(
            f"[MOVE_ACTION] 单位 {unit_id} 存在，类型: {unit.unit_type.value}, 阵营: {unit.faction.value}"
        )

        # 详细组件检查
        print(f"[MOVE_ACTION] 检查单位 {unit_id} 的必需组件...")
        position = self.world.get_component(unit_id, HexPosition)
        movement_points = self.world.get_component(unit_id, MovementPoints)
        unit_count = self.world.get_component(unit_id, UnitCount)
        action_points = self.world.get_component(unit_id, ActionPoints)
        unit_status = self.world.get_component(unit_id, UnitStatus)

        # 详细的组件缺失检查
        missing_components = []
        component_info = {}

        if not position:
            missing_components.append("HexPosition")
        else:
            component_info["position"] = {"col": position.col, "row": position.row}
            print(f"[MOVE_ACTION] 当前位置: ({position.col}, {position.row})")

        if not movement_points:
            missing_components.append("MovementPoints")
        else:
            component_info["movement_points"] = {
                "current_mp": movement_points.current_mp,
                "max_mp": movement_points.max_mp,
                "recovery_rate": getattr(movement_points, "recovery_rate", "unknown"),
            }
            print(
                f"[MOVE_ACTION] 移动力: {movement_points.current_mp}/{movement_points.max_mp}"
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
                f"[MOVE_ACTION] 单位人数: {unit_count.current_count}/{unit_count.max_count}"
            )

        if not action_points:
            missing_components.append("ActionPoints")
        else:
            component_info["action_points"] = {
                "current_ap": action_points.current_ap,
                "max_ap": action_points.max_ap,
            }
            print(
                f"[MOVE_ACTION] 行动点: {action_points.current_ap}/{action_points.max_ap}"
            )

        if missing_components:
            error_msg = f"Unit {unit_id} missing required components: {', '.join(missing_components)}"
            print(f"[MOVE_ACTION] 组件缺失: {error_msg}")
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

        # 详细单位状态检查
        if unit_status:
            print(f"[MOVE_ACTION] 单位状态: {unit_status.current_status}")
            if unit_status.current_status == UnitState.CONFUSION:
                error_msg = f"Unit {unit_id} is confused and cannot move"
                print(f"[MOVE_ACTION] 状态阻止移动: {error_msg}")
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
            print(f"[MOVE_ACTION] 单位状态组件不存在，假设状态正常")

        # === 第一层检查：行动点（决策层级） ===
        print(f"[MOVE_ACTION] 检查行动点需求...")
        required_ap = 1
        current_ap = action_points.current_ap

        if current_ap < required_ap:
            error_msg = f"Insufficient action points to initiate movement decision: need {required_ap}, have {current_ap}"
            print(f"[MOVE_ACTION] 行动点不足: {error_msg}")
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
        print(f"[MOVE_ACTION] 行动点检查通过: {current_ap}/{action_points.max_ap}")

        # === 第二层检查：移动力点数（执行层级） ===
        print(f"[MOVE_ACTION] 检查移动力...")
        current_mp = movement_points.current_mp

        if current_mp <= 0:
            error_msg = f"Unit has no movement points left: {current_mp}"
            print(f"[MOVE_ACTION] 移动力不足: {error_msg}")
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
        print(f"[MOVE_ACTION] 移动力检查通过: {current_mp}/{movement_points.max_mp}")

        # 计算有效移动力（考虑人数损失）
        effective_movement = movement_points.get_effective_movement(unit_count)
        current_pos = (position.col, position.row)
        target_pos = (target_col, target_row)

        print(
            f"[MOVE_ACTION] 有效移动力: {effective_movement} (基础: {current_mp}, 人数影响: {unit_count.current_count}/{unit_count.max_count})"
        )
        print(f"[MOVE_ACTION] 路径规划: 从 {current_pos} 到 {target_pos}")

        # 获取路径并检查可达性
        print(f"[MOVE_ACTION] 获取地图障碍...")
        obstacles = self._get_obstacles_excluding_unit(unit_id)  # 排除移动单位自己
        print(f"[MOVE_ACTION] 地图障碍数量: {len(obstacles) if obstacles else 0}")

        # 检查目标位置是否被占用
        if target_pos in obstacles:
            # 查找占用目标位置的单位
            occupying_unit_id = None
            occupying_unit_info = None
            for entity in self.world.query().with_all(HexPosition, Unit).entities():
                if entity == unit_id:
                    continue  # 跳过移动单位自己
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
            print(f"[MOVE_ACTION] 目标位置被占用: {error_msg}")
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

        print(f"[MOVE_ACTION] 执行路径查找...")
        print(f"[MOVE_ACTION] 起始位置: {current_pos}")
        print(f"[MOVE_ACTION] 目标位置: {target_pos}")
        print(f"[MOVE_ACTION] 有效移动力范围: {effective_movement}")
        print(
            f"[MOVE_ACTION] 障碍物列表: {list(obstacles)[:10]}..."
        )  # 只显示前10个障碍

        path = PathFinding.find_path(
            current_pos, target_pos, obstacles, effective_movement
        )

        print(f"[MOVE_ACTION] 路径查找结果: {path}")

        if not path or len(path) < 2:
            # 尝试获取更多路径查找失败的信息
            from ..utils.hex_utils import HexMath

            hex_distance = HexMath.hex_distance(current_pos, target_pos)

            # 检查是否是距离问题
            distance_issue = hex_distance > effective_movement

            # 检查是否是目标位置问题
            target_blocked = target_pos in obstacles

            # 检查相邻位置的可达性
            adjacent_free_positions = self._get_adjacent_free_positions(
                current_pos, obstacles
            )

            error_msg = f"No valid path to target position {target_pos}"
            print(f"[MOVE_ACTION] 路径查找失败: {error_msg}")
            print(f"[MOVE_ACTION] 六边形距离: {hex_distance}")
            print(f"[MOVE_ACTION] 有效移动力: {effective_movement}")
            print(f"[MOVE_ACTION] 距离超出范围: {distance_issue}")
            print(f"[MOVE_ACTION] 目标被阻挡: {target_blocked}")
            print(f"[MOVE_ACTION] 相邻空位: {adjacent_free_positions}")

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
                    "obstacles_sample": list(obstacles)[:10],  # 前10个障碍样本
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

        print(f"[MOVE_ACTION] 找到路径，长度: {len(path)}, 路径: {path}")

        # 计算路径总移动力消耗（每个地形格子有不同的移动力成本）
        print(f"[MOVE_ACTION] 计算路径移动力消耗...")
        total_movement_cost = self._calculate_total_movement_cost(path)
        print(f"[MOVE_ACTION] 路径总消耗: {total_movement_cost} 移动力")

        # 检查当前移动力是否足够（使用实际剩余的移动力）
        if total_movement_cost > current_mp:
            error_msg = f"Target too far: need {total_movement_cost} movement points, have {current_mp}"
            print(f"[MOVE_ACTION] 移动力不足以到达目标: {error_msg}")
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

        print(f"[MOVE_ACTION] 移动力足够，剩余: {current_mp - total_movement_cost}")

        # 执行移动
        print(f"[MOVE_ACTION] 获取移动系统...")
        movement_system = self._get_movement_system()
        if not movement_system:
            error_msg = "Movement system not available"
            print(f"[MOVE_ACTION] 系统错误: {error_msg}")
            return self._create_error_response(
                1009,
                error_msg,
                {
                    "unit_id": unit_id,
                    "system_error": "MovementSystem not found",
                    "suggestion": "This is a game engine error - contact administrator",
                },
            )

        print(f"[MOVE_ACTION] 执行移动操作...")
        success = movement_system.move_unit(unit_id, target_pos)

        if success:
            print(f"[MOVE_ACTION] 移动成功！")
            # 移动成功后，需要重新获取组件状态（因为MovementSystem已经修改了它们）
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
                    "action_points_used": 1,  # 固定消耗1点行动点启动决策
                    "movement_points_used": total_movement_cost,  # 实际移动力消耗
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
            print(f"[MOVE_ACTION] 移动完成，返回结果: {result}")
            return result
        else:
            error_msg = "Movement system failed to execute move"
            print(f"[MOVE_ACTION] 移动执行失败: {error_msg}")
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
        """处理攻击动作"""
        # 参数验证
        unit_id = params.get("unit_id")
        target_id = params.get("target_id")

        if not isinstance(unit_id, int) or not isinstance(target_id, int):
            return self._create_error_response(
                1010, "unit_id and target_id must be integers"
            )

        # 检查攻击方存在性
        attacker_unit = self.world.get_component(unit_id, Unit)
        if not attacker_unit:
            return self._create_error_response(
                1001, f"Attacker unit {unit_id} not found"
            )

        # 检查目标存在性
        target_unit = self.world.get_component(target_id, Unit)
        if not target_unit:
            return self._create_error_response(
                1001, f"Target unit {target_id} not found"
            )

        # 检查是否敌对阵营
        if attacker_unit.faction == target_unit.faction:
            return self._create_error_response(
                1008, "Cannot attack units of same faction"
            )

        # 检查攻击方组件
        attacker_pos = self.world.get_component(unit_id, HexPosition)
        attacker_combat = self.world.get_component(unit_id, Combat)
        attacker_action_points = self.world.get_component(unit_id, ActionPoints)

        if not all([attacker_pos, attacker_combat, attacker_action_points]):
            return self._create_error_response(
                1001, "Attacker missing required components"
            )

        # 检查目标组件
        target_pos = self.world.get_component(target_id, HexPosition)
        if not target_pos:
            return self._create_error_response(
                1001, "Target missing position component"
            )

        # 检查动作点
        if not attacker_action_points.can_perform_action(ActionType.ATTACK):
            return self._create_error_response(
                1002,
                f"Insufficient action points for attack: need 2, have {attacker_action_points.current_ap}",
            )

        # 检查攻击范围
        attacker_current_pos = (attacker_pos.col, attacker_pos.row)
        target_current_pos = (target_pos.col, target_pos.row)
        distance = HexMath.hex_distance(attacker_current_pos, target_current_pos)

        if distance > attacker_combat.attack_range:
            return self._create_error_response(
                1003,
                f"Target out of range: distance {distance}, range {attacker_combat.attack_range}",
            )

        # 检查是否已攻击过
        if attacker_combat.has_attacked:
            return self._create_error_response(
                1005, "Unit has already attacked this turn"
            )

        # 执行攻击
        combat_system = self._get_combat_system()
        if combat_system:
            # 获取攻击前的状态
            target_count = self.world.get_component(target_id, UnitCount)
            initial_target_count = target_count.current_count if target_count else 0

            success = combat_system.attack(unit_id, target_id)
            if success:
                # 获取攻击后的状态
                final_target_count = target_count.current_count if target_count else 0
                casualties = initial_target_count - final_target_count

                # 获取地形加成信息
                terrain_bonus = self._get_terrain_attack_bonus(
                    attacker_current_pos, attacker_unit.faction
                )

                return {
                    "success": True,
                    "message": f"Unit {unit_id} attacked unit {target_id}",
                    "battle_result": {
                        "attacker_damage_dealt": casualties,
                        "defender_damage_dealt": 0,  # 简化，实际可能有反击
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
        """处理待命动作"""
        unit_id = params.get("unit_id")

        if not isinstance(unit_id, int):
            return self._create_error_response(1010, "unit_id must be integer")

        # 检查单位存在性
        unit = self.world.get_component(unit_id, Unit)
        if not unit:
            return self._create_error_response(1001, f"Unit {unit_id} not found")

        # 执行待命
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
        """处理驻扎动作"""
        unit_id = params.get("unit_id")

        if not isinstance(unit_id, int):
            return self._create_error_response(1010, "unit_id must be integer")

        # 检查单位存在性
        unit = self.world.get_component(unit_id, Unit)
        if not unit:
            return self._create_error_response(1001, f"Unit {unit_id} not found")

        # 检查动作点
        action_points = self.world.get_component(unit_id, ActionPoints)
        if not action_points or not action_points.can_perform_action(
            ActionType.GARRISON
        ):
            return self._create_error_response(
                1002,
                f"Insufficient action points for garrison: need 2, have {action_points.current_ap if action_points else 0}",
            )

        # 执行驻扎
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
        """处理占领动作"""
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

        # 检查单位存在性
        unit = self.world.get_component(unit_id, Unit)
        if not unit:
            return self._create_error_response(1001, f"Unit {unit_id} not found")

        # 检查单位位置是否在目标位置
        unit_pos = self.world.get_component(unit_id, HexPosition)
        if not unit_pos or (unit_pos.col, unit_pos.row) != (col, row):
            return self._create_error_response(
                1004, "Unit must be at target position to capture"
            )

        # 检查动作点
        action_points = self.world.get_component(unit_id, ActionPoints)
        if not action_points or not action_points.can_perform_action(
            ActionType.CAPTURE
        ):
            return self._create_error_response(
                1002,
                f"Insufficient action points for capture: need 2, have {action_points.current_ap if action_points else 0}",
            )

        # 检查是否可以占领
        territory_system = self._get_territory_system()
        if territory_system:
            success = territory_system.start_capture(unit_id, (col, row))
            if success:
                return {
                    "success": True,
                    "message": f"Unit {unit_id} started capturing position {(col, row)}",
                    "capture_status": {
                        "in_progress": True,
                        "estimated_turns": 1,  # 可以根据地形调整
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
        """处理工事建设动作"""
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

        # 检查单位存在性
        unit = self.world.get_component(unit_id, Unit)
        if not unit:
            return self._create_error_response(1001, f"Unit {unit_id} not found")

        # 检查动作点和建造点
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

        # 获取地形类型和工事等级限制
        terrain_type = self._get_terrain_at_position((col, row))
        max_level = self._get_max_fortification_level(terrain_type)

        # 检查当前工事等级
        current_level = self._get_current_fortification_level((col, row))

        if current_level >= max_level:
            return self._create_error_response(
                1007,
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
        """处理技能动作"""
        unit_id = params.get("unit_id")
        skill_name = params.get("skill_name")
        target = params.get("target")

        if not isinstance(unit_id, int):
            return self._create_error_response(1010, "unit_id must be integer")

        if not isinstance(skill_name, str):
            return self._create_error_response(1010, "skill_name must be string")

        # 检查单位存在性
        unit = self.world.get_component(unit_id, Unit)
        if not unit:
            return self._create_error_response(1001, f"Unit {unit_id} not found")

        # 检查技能组件
        unit_skills = self.world.get_component(unit_id, UnitSkills)
        skill_points = self.world.get_component(unit_id, SkillPoints)

        if not unit_skills:
            return self._create_error_response(1005, "Unit has no skills")

        if not skill_points:
            return self._create_error_response(1005, "Unit has no skill points")

        # 检查技能是否可用（UnitSkills控制技能列表和冷却）
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

        # 检查技能点是否足够（SkillPoints控制消耗）
        if not skill_points.can_use_skill(skill_name, 1):
            return self._create_error_response(
                1006,
                f"Insufficient skill points: need 1, have {skill_points.current_sp}",
            )

        # 检查动作点
        action_points = self.world.get_component(unit_id, ActionPoints)
        if not action_points or not action_points.can_perform_action(ActionType.SKILL):
            return self._create_error_response(
                1002,
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

            if skill_result["success"]:
                # 消耗资源：多层次资源系统
                # 1. 消耗行动点（决策层）
                action_points.consume_ap(ActionType.SKILL)

                # 2. 消耗技能点（执行层）
                skill_points.use_skill(skill_name, 1, skill_result.get("cooldown", 0))

                # 3. 设置冷却时间（通过UnitSkills）
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

    # ==================== 观测动作 ====================

    def handle_unit_observation(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理单位观测"""
        unit_id = params.get("unit_id")
        observation_level = params.get("observation_level", "basic")

        if not isinstance(unit_id, int):
            return self._create_error_response(1010, "unit_id must be integer")

        # 检查单位存在性
        unit = self.world.get_component(unit_id, Unit)
        if not unit:
            return self._create_error_response(1001, f"Unit {unit_id} not found")

        # 获取单位信息
        unit_info = self._get_detailed_unit_info(unit_id)

        # 获取可见环境
        visible_environment = self._get_visible_environment(unit_id, observation_level)

        result = {
            "success": True,
            "unit_info": unit_info,
            "visible_environment": visible_environment,
        }

        # 根据观测级别添加额外信息
        if observation_level in ["detailed", "tactical"]:
            result["tactical_info"] = self._get_tactical_info(unit_id)

        return result

    def handle_get_unit_info(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """获取单位详细信息"""
        unit_id = params.get("unit_id")

        if not isinstance(unit_id, int):
            return self._create_error_response(1010, "unit_id must be integer")

        # 检查单位存在性
        unit = self.world.get_component(unit_id, Unit)
        if not unit:
            return self._create_error_response(1001, f"Unit {unit_id} not found")

        unit_info = self._get_detailed_unit_info(unit_id)

        return {"success": True, **unit_info}

    # ==================== 阵营控制动作 ====================

    def handle_faction_state(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """获取阵营状态"""
        faction_str = params.get("faction")

        if not faction_str:
            return self._create_error_response(1010, "faction parameter required")

        try:
            faction = Faction(faction_str)
            print(f"Handling faction state for {faction.value}")
        except ValueError:
            return self._create_error_response(1010, f"Invalid faction: {faction_str}")

        # 获取阵营所有单位
        faction_units = self._get_faction_units(faction)

        # 计算阵营统计
        total_units_count = len(faction_units)
        active_units = [u for u in faction_units if self._is_unit_active(u)]
        active_units_count = len(active_units)

        # 计算领土控制
        # territory_control = self._calculate_territory_control(faction)

        # 计算资源汇总
        # resource_summary = self._calculate_resource_summary(faction_units)

        # 战略分析
        # strategic_summary = self._get_strategic_summary(faction)
        print(f"final {faction.value}")
        return {
            "success": True,
            "faction": faction.value,
            "total_units": total_units_count,
            "active_units": active_units_count,
            "units": [
                self._get_detailed_unit_info(unit_id) for unit_id in active_units[:10]
            ],  # 限制返回数量
            # "territory_control": territory_control,
            # "resource_summary": resource_summary,
            # "units": [
            #     self._get_detailed_unit_info(unit_id) for unit_id in faction_units[:10]
            # ],  # 限制返回数量
            # "strategic_summary": strategic_summary,
        }

    def handle_faction_unit_action(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """执行阵营单位动作"""
        faction_str = params.get("faction")
        unit_id = params.get("unit_id")
        unit_action = params.get("unit_action")
        action_params = params.get("action_params", {})

        # 验证参数
        if not faction_str or not isinstance(unit_id, int) or not unit_action:
            return self._create_error_response(
                1010, "faction, unit_id, unit_action required"
            )

        try:
            faction = Faction(faction_str)
        except ValueError:
            return self._create_error_response(1010, f"Invalid faction: {faction_str}")

        # 验证单位属于该阵营
        unit = self.world.get_component(unit_id, Unit)
        if not unit:
            return self._create_error_response(1001, f"Unit {unit_id} not found")

        if unit.faction != faction:
            return self._create_error_response(
                1008, f"Unit {unit_id} does not belong to faction {faction.value}"
            )

        # 构造动作数据并执行
        action_data = {
            "action": unit_action,
            "params": {"unit_id": unit_id, **action_params},
        }

        return self.execute_action(action_data)

    def handle_faction_batch_actions(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """批量执行阵营动作"""
        faction_str = params.get("faction")
        actions = params.get("actions", [])

        if not faction_str:
            return self._create_error_response(1010, "faction parameter required")

        if not isinstance(actions, list):
            return self._create_error_response(1010, "actions must be array")

        if len(actions) > 10:  # 限制批量操作数量
            return self._create_error_response(1010, "Maximum 10 actions per batch")

        try:
            faction = Faction(faction_str)
        except ValueError:
            return self._create_error_response(1010, f"Invalid faction: {faction_str}")

        # 执行所有动作
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
                # 验证单位属于该阵营
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
                    # 执行动作
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
        """返回所有可用动作的接口文档描述"""
        action_docs = {
            "api_version": self.api_version,
            "total_actions": len(self.action_handlers),
            "actions": {
                # 单位控制动作
                "move": {
                    "category": "unit_control",
                    "description": "移动单位到指定位置",
                    "parameters": {
                        "unit_id": {
                            "type": "int",
                            "required": True,
                            "description": "单位ID",
                        },
                        "target_position": {
                            "type": "object",
                            "required": True,
                            "description": "目标位置",
                            "properties": {
                                "col": {"type": "int", "description": "列坐标"},
                                "row": {"type": "int", "description": "行坐标"},
                            },
                        },
                    },
                    "returns": {
                        "success": {"type": "bool", "description": "执行是否成功"},
                        "message": {"type": "string", "description": "执行结果消息"},
                        "resource_consumption": {
                            "type": "object",
                            "description": "资源消耗详情",
                            "properties": {
                                "action_points_used": {
                                    "type": "int",
                                    "description": "消耗的行动点（决策层级）",
                                },
                                "movement_points_used": {
                                    "type": "int",
                                    "description": "消耗的移动力（执行层级）",
                                },
                            },
                        },
                        "remaining_resources": {
                            "type": "object",
                            "description": "剩余资源",
                            "properties": {
                                "action_points": {
                                    "type": "int",
                                    "description": "剩余行动点",
                                },
                                "movement_points": {
                                    "type": "int",
                                    "description": "剩余移动力",
                                },
                            },
                        },
                        "path_info": {
                            "type": "object",
                            "description": "路径信息",
                            "properties": {
                                "path": {"type": "array", "description": "移动路径"},
                                "path_length": {
                                    "type": "int",
                                    "description": "路径长度",
                                },
                                "terrain_breakdown": {
                                    "type": "array",
                                    "description": "路径地形分析",
                                },
                            },
                        },
                    },
                    "resource_system": {
                        "action_points": "固定消耗1点启动移动决策",
                        "movement_points": "根据路径和地形消耗：平原1，森林2，山地3等",
                        "recovery": "每回合自动恢复，实时模式下5秒恢复",
                    },
                    "prerequisites": [
                        "单位存在",
                        "有1点行动点启动决策",
                        "有足够移动力到达目标",
                        "目标位置可达",
                        "单位状态正常",
                    ],
                },
                "attack": {
                    "category": "unit_control",
                    "description": "攻击指定敌方单位",
                    "parameters": {
                        "unit_id": {
                            "type": "int",
                            "required": True,
                            "description": "攻击方单位ID",
                        },
                        "target_id": {
                            "type": "int",
                            "required": True,
                            "description": "目标单位ID",
                        },
                    },
                    "returns": {
                        "success": {"type": "bool", "description": "攻击是否成功"},
                        "message": {"type": "string", "description": "攻击结果消息"},
                        "battle_result": {"type": "object", "description": "战斗详情"},
                        "remaining_action_points": {
                            "type": "int",
                            "description": "剩余行动点",
                        },
                    },
                    "action_point_cost": "2",
                    "prerequisites": [
                        "单位存在",
                        "目标在攻击范围内",
                        "敌对阵营",
                        "未攻击过",
                        "足够行动点",
                    ],
                },
                "wait": {
                    "category": "unit_control",
                    "description": "单位待命并恢复状态",
                    "parameters": {
                        "unit_id": {
                            "type": "int",
                            "required": True,
                            "description": "单位ID",
                        }
                    },
                    "returns": {
                        "success": {"type": "bool", "description": "执行是否成功"},
                        "message": {"type": "string", "description": "执行结果"},
                        "effects": {"type": "object", "description": "恢复效果"},
                        "remaining_action_points": {
                            "type": "int",
                            "description": "剩余行动点",
                        },
                    },
                    "action_point_cost": "0",
                    "prerequisites": ["单位存在"],
                },
                "garrison": {
                    "category": "unit_control",
                    "description": "单位驻扎并恢复人数",
                    "parameters": {
                        "unit_id": {
                            "type": "int",
                            "required": True,
                            "description": "单位ID",
                        }
                    },
                    "returns": {
                        "success": {"type": "bool", "description": "执行是否成功"},
                        "message": {"type": "string", "description": "执行结果"},
                        "effects": {"type": "object", "description": "驻扎效果"},
                        "current_count": {"type": "int", "description": "当前人数"},
                        "remaining_action_points": {
                            "type": "int",
                            "description": "剩余行动点",
                        },
                    },
                    "action_point_cost": "2",
                    "prerequisites": ["单位存在", "足够行动点"],
                },
                "capture": {
                    "category": "territory_control",
                    "description": "占领指定地块",
                    "parameters": {
                        "unit_id": {
                            "type": "int",
                            "required": True,
                            "description": "单位ID",
                        },
                        "position": {
                            "type": "object",
                            "required": True,
                            "description": "占领位置",
                            "properties": {
                                "col": {"type": "int", "description": "列坐标"},
                                "row": {"type": "int", "description": "行坐标"},
                            },
                        },
                    },
                    "returns": {
                        "success": {"type": "bool", "description": "占领是否成功"},
                        "message": {"type": "string", "description": "占领结果"},
                        "capture_status": {"type": "object", "description": "占领状态"},
                        "remaining_action_points": {
                            "type": "int",
                            "description": "剩余行动点",
                        },
                    },
                    "action_point_cost": "2",
                    "prerequisites": ["单位在目标位置", "位置可占领", "足够行动点"],
                },
                "fortify": {
                    "category": "territory_control",
                    "description": "在指定位置建设工事",
                    "parameters": {
                        "unit_id": {
                            "type": "int",
                            "required": True,
                            "description": "单位ID",
                        },
                        "position": {
                            "type": "object",
                            "required": True,
                            "description": "工事位置",
                            "properties": {
                                "col": {"type": "int", "description": "列坐标"},
                                "row": {"type": "int", "description": "行坐标"},
                            },
                        },
                    },
                    "returns": {
                        "success": {"type": "bool", "description": "建设是否成功"},
                        "message": {"type": "string", "description": "建设结果"},
                        "current_level": {"type": "int", "description": "当前工事等级"},
                        "max_level": {"type": "int", "description": "最大工事等级"},
                        "defense_bonus": {"type": "float", "description": "防御加成"},
                        "terrain_type": {"type": "string", "description": "地形类型"},
                        "remaining_action_points": {
                            "type": "int",
                            "description": "剩余行动点",
                        },
                    },
                    "action_point_cost": "2",
                    "prerequisites": [
                        "单位存在",
                        "工事未达上限",
                        "地形允许",
                        "足够行动点",
                    ],
                },
                "skill": {
                    "category": "unit_control",
                    "description": "使用单位技能",
                    "parameters": {
                        "unit_id": {
                            "type": "int",
                            "required": True,
                            "description": "单位ID",
                        },
                        "skill_name": {
                            "type": "string",
                            "required": True,
                            "description": "技能名称",
                        },
                        "target": {
                            "type": "any",
                            "required": False,
                            "description": "技能目标(可选)",
                        },
                    },
                    "returns": {
                        "success": {"type": "bool", "description": "技能使用是否成功"},
                        "message": {"type": "string", "description": "技能使用结果"},
                        "skill_result": {"type": "object", "description": "技能效果"},
                        "remaining_action_points": {
                            "type": "int",
                            "description": "剩余行动点",
                        },
                    },
                    "action_point_cost": "2",
                    "prerequisites": [
                        "单位存在",
                        "技能可用",
                        "无冷却",
                        "地形符合",
                        "足够行动点",
                    ],
                },
                # 观测动作
                "unit_observation": {
                    "category": "observation",
                    "description": "获取单位观测信息",
                    "parameters": {
                        "unit_id": {
                            "type": "int",
                            "required": True,
                            "description": "单位ID",
                        },
                        "observation_level": {
                            "type": "string",
                            "required": False,
                            "description": "观测级别",
                            "default": "basic",
                            "options": ["basic", "detailed", "tactical"],
                        },
                    },
                    "returns": {
                        "success": {"type": "bool", "description": "观测是否成功"},
                        "unit_info": {"type": "object", "description": "单位详细信息"},
                        "visible_environment": {
                            "type": "array",
                            "description": "可见环境",
                        },
                        "tactical_info": {
                            "type": "object",
                            "description": "战术信息(详细模式)",
                        },
                    },
                    "action_point_cost": "0",
                    "prerequisites": ["单位存在"],
                },
                "get_unit_info": {
                    "category": "observation",
                    "description": "获取单位详细信息",
                    "parameters": {
                        "unit_id": {
                            "type": "int",
                            "required": True,
                            "description": "单位ID",
                        }
                    },
                    "returns": {
                        "success": {"type": "bool", "description": "获取是否成功"},
                        "unit_id": {"type": "int", "description": "单位ID"},
                        "unit_type": {"type": "string", "description": "单位类型"},
                        "faction": {"type": "string", "description": "所属阵营"},
                        "position": {"type": "object", "description": "位置信息"},
                        "status": {"type": "object", "description": "状态信息"},
                        "capabilities": {"type": "object", "description": "能力信息"},
                        "available_skills": {
                            "type": "array",
                            "description": "可用技能列表",
                        },
                    },
                    "action_point_cost": "0",
                    "prerequisites": ["单位存在"],
                },
                # 阵营控制动作
                "faction_state": {
                    "category": "faction_control",
                    "description": "获取阵营整体状态",
                    "parameters": {
                        "faction": {
                            "type": "string",
                            "required": True,
                            "description": "阵营名称(wei/shu/wu)",
                        }
                    },
                    "returns": {
                        "success": {"type": "bool", "description": "获取是否成功"},
                        "faction": {"type": "string", "description": "阵营名称"},
                        "total_units": {"type": "int", "description": "总单位数"},
                        "active_units": {"type": "int", "description": "活跃单位数"},
                        "territory_control": {
                            "type": "int",
                            "description": "领土控制百分比",
                        },
                        "resource_summary": {
                            "type": "object",
                            "description": "资源汇总",
                        },
                        "units": {"type": "array", "description": "单位列表(最多10个)"},
                        "strategic_summary": {
                            "type": "object",
                            "description": "战略摘要",
                        },
                    },
                    "action_point_cost": "0",
                    "prerequisites": ["有效阵营名称"],
                },
                # "faction_unit_action": {
                #     "category": "faction_control",
                #     "description": "以阵营身份执行单位动作",
                #     "parameters": {
                #         "faction": {
                #             "type": "string",
                #             "required": True,
                #             "description": "阵营名称",
                #         },
                #         "unit_id": {
                #             "type": "int",
                #             "required": True,
                #             "description": "单位ID",
                #         },
                #         "unit_action": {
                #             "type": "string",
                #             "required": True,
                #             "description": "单位动作类型",
                #         },
                #         "action_params": {
                #             "type": "object",
                #             "required": False,
                #             "description": "动作参数",
                #         },
                #     },
                #     "returns": {
                #         "type": "object",
                #         "description": "返回对应单位动作的结果",
                #     },
                #     "action_point_cost": "取决于具体动作",
                #     "prerequisites": ["单位属于指定阵营", "单位动作有效"],
                # },
                # "faction_batch_actions": {
                #     "category": "faction_control",
                #     "description": "批量执行阵营动作",
                #     "parameters": {
                #         "faction": {
                #             "type": "string",
                #             "required": True,
                #             "description": "阵营名称",
                #         },
                #         "actions": {
                #             "type": "array",
                #             "required": True,
                #             "description": "动作列表(最多10个)",
                #             "max_items": 10,
                #         },
                #     },
                #     "returns": {
                #         "success": {"type": "bool", "description": "批量执行总体结果"},
                #         "executed_actions": {
                #             "type": "int",
                #             "description": "成功执行的动作数",
                #         },
                #         "failed_actions": {
                #             "type": "int",
                #             "description": "失败的动作数",
                #         },
                #         "results": {
                #             "type": "array",
                #             "description": "每个动作的详细结果",
                #         },
                #     },
                #     "action_point_cost": "取决于具体动作",
                #     "prerequisites": ["有效阵营", "动作列表不超过10个"],
                # },
                # 系统动作
                "action_list": {
                    "category": "system",
                    "description": "获取所有可用动作的接口文档",
                    "parameters": {},
                    "returns": {
                        "api_version": {"type": "string", "description": "API版本"},
                        "total_actions": {"type": "int", "description": "总动作数"},
                        "actions": {
                            "type": "object",
                            "description": "所有动作的详细文档",
                        },
                    },
                    "action_point_cost": "0",
                    "prerequisites": ["无"],
                },
            },
            "error_codes": {
                1001: "单位不存在",
                1002: "动作点不足",
                1003: "目标超出范围",
                1004: "无效的目标位置",
                1005: "单位状态不允许该动作",
                1006: "技能冷却中",
                1007: "地形不支持该动作",
                1008: "阵营不匹配",
                1009: "游戏状态不允许",
                1010: "参数格式错误",
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

    # ==================== 辅助方法 ====================

    def _create_error_response(
        self, error_code: int, message: str, extra_data: Dict = None
    ) -> Dict[str, Any]:
        """创建错误响应"""
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
        """获取单位详细信息"""
        try:
            # 参数验证
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

            # 获取所有组件
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

            # 检查核心组件是否存在
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

            # 安全获取单位类型和阵营
            try:
                unit_type_value = unit.unit_type.value if unit.unit_type else "unknown"
            except (AttributeError, ValueError):
                unit_type_value = "unknown"

            try:
                faction_value = unit.faction.value if unit.faction else "unknown"
            except (AttributeError, ValueError):
                faction_value = "unknown"

            # 安全获取位置信息
            position_info = {"col": 0, "row": 0}
            if position:
                try:
                    position_info = {
                        "col": int(position.col) if hasattr(position, "col") else 0,
                        "row": int(position.row) if hasattr(position, "row") else 0,
                    }
                except (AttributeError, ValueError, TypeError):
                    position_info = {"col": 0, "row": 0}

            # 安全获取状态信息
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
                    pass  # 保持默认值

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

            # 安全获取能力信息
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

            # 新增多层次资源信息
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

            # 安全获取技能信息
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
            # 异常情况下返回安全的默认值
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
        """获取单位可见环境"""
        vision = self.world.get_component(unit_id, Vision)
        if not vision:
            return []

        # 获取单位当前位置和移动组件（为移动模式做准备）
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

            # 如果observation_level为"move"，添加移动相关信息
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
        """计算从当前位置到目标位置的移动信息"""
        # 如果是当前位置，返回特殊信息
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

        # 计算有效移动力（考虑人数损失）
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
                    "path_length": len(path) - 1,  # 不包括起始位置
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
                # 无法找到路径
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
            # 路径计算出错
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
        """获取战术信息"""
        # 简化实现
        return {"threats": [], "opportunities": [], "movement_options": []}

    def _get_faction_units(self, faction: Faction) -> List[int]:
        """获取阵营所有单位"""
        units = []
        for entity in self.world.query().with_component(Unit).entities():
            unit = self.world.get_component(entity, Unit)
            if unit and unit.faction == faction:
                units.append(entity)
        return units

    def _is_unit_active(self, unit_id: int) -> bool:
        """检查单位是否活跃"""
        unit_count = self.world.get_component(unit_id, UnitCount)
        return unit_count and unit_count.current_count > 0

    def _calculate_territory_control(self, faction: Faction) -> int:
        """计算领土控制百分比"""
        # 简化实现
        return 30  # 返回固定值，实际应计算

    def _calculate_resource_summary(self, faction_units: List[int]) -> Dict[str, Any]:
        """计算资源汇总"""
        total_manpower = 0
        for unit_id in faction_units:
            unit_count = self.world.get_component(unit_id, UnitCount)
            if unit_count:
                total_manpower += unit_count.current_count

        return {
            "total_manpower": total_manpower,
            "fortification_points": 0,  # 简化
            "controlled_cities": 0,  # 简化
        }

    def _get_strategic_summary(self, faction: Faction) -> Dict[str, Any]:
        """获取战略摘要"""
        return {
            "active_battles": 0,
            "territory_threats": [],
            "expansion_opportunities": [],
        }

    # ==================== 系统获取方法 ====================

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

    def _get_action_system(self):
        """获取动作系统"""
        for system in self.world.systems:
            if system.__class__.__name__ == "ActionSystem":
                return system
        return None

    def _get_territory_system(self):
        """获取领土系统"""
        for system in self.world.systems:
            if system.__class__.__name__ == "TerritorySystem":
                return system
        return None

    # ==================== 游戏逻辑辅助方法 ====================

    def _get_obstacles(self) -> Set[Tuple[int, int]]:
        """获取移动障碍 - 只考虑单位作为障碍"""
        obstacles = set()
        # 获取所有单位位置作为障碍
        for entity in self.world.query().with_all(HexPosition, Unit).entities():
            pos = self.world.get_component(entity, HexPosition)
            if pos:
                obstacles.add((pos.col, pos.row))
        return obstacles

    def _get_obstacles_excluding_unit(
        self, exclude_unit_id: int
    ) -> Set[Tuple[int, int]]:
        """获取移动障碍，排除指定单位 - 只考虑其他单位作为障碍"""
        obstacles = set()
        # 获取所有单位位置作为障碍，但排除指定单位
        for entity in self.world.query().with_all(HexPosition, Unit).entities():
            if entity == exclude_unit_id:
                continue  # 跳过要移动的单位
            pos = self.world.get_component(entity, HexPosition)
            if pos:
                obstacles.add((pos.col, pos.row))
        print(
            f"[DEBUG] 实际单位障碍数量: {len(obstacles)} (排除单位 {exclude_unit_id})"
        )
        return obstacles

    def _get_adjacent_free_positions(
        self, center_pos: Tuple[int, int], obstacles: Set[Tuple[int, int]]
    ) -> List[Tuple[int, int]]:
        """获取中心位置周围的空闲位置"""
        from ..utils.hex_utils import HexMath

        col, row = center_pos

        # 六边形的6个相邻方向
        adjacent_positions = []
        directions = [(1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1)]

        for dx, dy in directions:
            adj_pos = (col + dx, row + dy)
            if adj_pos not in obstacles:
                adjacent_positions.append(adj_pos)

        return adjacent_positions

    def _calculate_total_movement_cost(self, path: List[Tuple[int, int]]) -> int:
        """计算路径总移动消耗"""
        total_cost = 0
        for pos in path[1:]:  # 跳过起始位置
            terrain_cost = self._get_terrain_movement_cost(pos)
            total_cost += terrain_cost
        return total_cost

    def _get_terrain_movement_cost(self, position: Tuple[int, int]) -> int:
        """获取地形移动消耗（移动力消耗）"""
        terrain_type = self._get_terrain_at_position(position)

        # 地形移动消耗映射
        terrain_costs = {
            TerrainType.PLAIN: 1,
            TerrainType.FOREST: 2,
            TerrainType.HILL: 2,
            TerrainType.MOUNTAIN: 3,
            TerrainType.WATER: 99,  # 不可通行
            TerrainType.CITY: 1,
            TerrainType.URBAN: 1,
        }

        return terrain_costs.get(terrain_type, 1)

    def _get_path_terrain_breakdown(
        self, path: List[Tuple[int, int]]
    ) -> List[Dict[str, Any]]:
        """获取路径中每个位置的地形信息和消耗"""
        breakdown = []

        for i, pos in enumerate(path):
            if i == 0:  # 跳过起始位置
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
        """获取位置的地形类型"""
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
        """获取地形攻击加成"""
        territory_system = self._get_territory_system()
        if territory_system:
            return (
                territory_system.get_territory_attack_bonus(position, faction) / 10.0
            )  # 转换为小数
        return 0.0

    def _get_max_fortification_level(self, terrain_type: TerrainType) -> int:
        """获取地形最大工事等级"""
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
        """获取当前工事等级"""
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
        """计算工事防御加成"""
        return level * 0.2  # 每级+20%防御

    def _get_units_at_position(self, position: Tuple[int, int]) -> List[Dict[str, Any]]:
        """获取位置上的所有单位"""
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
        """执行地形技能"""
        # 技能执行逻辑
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
