"""
LLM Action Handler V3 - 精简且高效的动作处理器
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


class LLMActionHandlerV3:
    """LLM动作处理器V3 - 精简且高效的接口设计"""

    def __init__(self, world: World):
        self.world = world

        # 支持的动作映射
        self.action_handlers = {
            # 单位控制动作
            "move": self.handle_move_action,
            "attack": self.handle_attack_action,
            "rest": self.handle_rest_action,
            "occupy": self.handle_occupy_action,
            "fortify": self.handle_fortify_action,
            "skill": self.handle_skill_action,
            # 观测动作
            "observation": self.handle_observation_action,
            # 阵营信息
            "get_faction_state": self.handle_faction_state,
            # System
            "get_action_list": self.handle_action_list,
            "end_turn": self.handle_end_turn,  # 新增 end_turn （回合）
            "register_agent_info": self.handle_register_agent_info,
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
                return self._create_error_response("Missing action field")

            if action_type not in self.action_handlers:
                return self._create_error_response(
                    f"Unsupported action: {action_type}",
                    {"supported_actions": list(self.action_handlers.keys())},
                )

            # 执行具体动作
            print(f"Executing action: {action_type} with params: {params}")
            return self.action_handlers[action_type](params)

        except Exception as e:
            return self._create_error_response(f"Action execution failed: {str(e)}")

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
                error_msg,
                {
                    "received_unit_id": unit_id,
                    "expected_type": "int",
                    "valid_example": {"unit_id": 123},
                },
            )

        if not target_position or not isinstance(target_position, dict):
            error_msg = f"Invalid target_position: expected dict with col/row, got {type(target_position).__name__}"
            print(f"[MOVE_ACTION] 参数验证失败: {error_msg}")
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
            print(f"[MOVE_ACTION] 坐标类型验证失败: {error_msg}")
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

        # 检查目标位置是否在地图边界内
        print(
            f"[MOVE_ACTION] 检查目标位置 ({target_col}, {target_row}) 是否在地图边界内..."
        )
        if not self._is_position_within_map_bounds(target_col, target_row):
            from ..prefabs.config import GameConfig

            center = GameConfig.MAP_WIDTH // 2
            min_coord = -center
            max_coord = center - 1
            error_msg = f"Target position ({target_col}, {target_row}) is outside map boundaries"
            print(f"[MOVE_ACTION] 地图边界检查失败: {error_msg}")
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

        print(f"[MOVE_ACTION] 目标位置在地图边界内: ({target_col}, {target_row})")

        # 详细单位存在性检查
        print(f"[MOVE_ACTION] 检查单位 {unit_id} 是否存在...")
        unit = self.world.get_component(unit_id, Unit)
        if not unit:
            error_msg = f"Unit {unit_id} not found in world"
            print(f"[MOVE_ACTION] 单位不存在: {error_msg}")
            return self._create_error_response(
                error_msg,
                {
                    "requested_unit_id": unit_id,
                    "suggestion": "Use get_faction_state action to see all units for a faction",
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
            error_msg = f"Insufficient movement points this turn: need {total_movement_cost}, have {current_mp}."
            print(f"[MOVE_ACTION] 移动力不足以到达目标: {error_msg}")

            # 计算在当前移动力下，沿路径能够抵达的最远位置
            cumulative_cost = 0
            reachable_positions_along_path = []
            for step_index, pos in enumerate(path[1:]):  # 跳过起点
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

            # 提供若干邻近可达位置作为候选（优先更接近目标）
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

        print(f"[MOVE_ACTION] 移动力足够，剩余: {current_mp - total_movement_cost}")

        # 执行移动
        print(f"[MOVE_ACTION] 获取移动系统...")
        movement_system = self._get_movement_system()
        if not movement_system:
            error_msg = "Movement system not available"
            print(f"[MOVE_ACTION] 系统错误: {error_msg}")
            return self._create_error_response(
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

            # 从 MovementAnimation 组件获取默认速度，或者硬编码一个已知值
            # 这里我们使用在 rotk_env/components/animation.py 中定义的默认值 2.0
            animation_speed = 2.0
            path_length = len(path) - 1 if path else 0
            estimated_duration = (
                path_length / animation_speed if animation_speed > 0 else 0
            )

            result = {
                "success": True,
                "message": f"Unit {unit_id} has started moving from {current_pos} to {target_pos}.",
                "action_status": "in_progress",
                "movement_details": {
                    "start_position": {"col": current_pos[0], "row": current_pos[1]},
                    "target_position": {"col": target_pos[0], "row": target_pos[1]},
                    "path": path,
                    "path_length": path_length,
                    "estimated_duration_seconds": round(estimated_duration, 2),
                },
            }
            print(f"[MOVE_ACTION] 移动完成，返回结果: {result}")
            return result
        else:
            error_msg = "Movement system failed to execute move"
            print(f"[MOVE_ACTION] 移动执行失败: {error_msg}")
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
        """处理攻击动作 - LLM接口层，负责验证和错误反馈"""
        print(f"[ATTACK_ACTION] 开始处理攻击动作，参数: {params}")

        # === 第一层：参数格式验证 ===
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

        print(f"[ATTACK_ACTION] 参数验证通过: 攻击方={unit_id}, 目标={target_id}")

        # === 第二层：实体存在性验证 ===
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
            f"[ATTACK_ACTION] 单位存在性验证通过: {attacker_unit.unit_type.value}({attacker_unit.faction.value}) -> {target_unit.unit_type.value}({target_unit.faction.value})"
        )

        # === 第三层：阵营关系验证 ===
        if attacker_unit.faction == target_unit.faction:
            return self._create_error_response(
                "Cannot attack units of same faction",
                {
                    "attacker_faction": attacker_unit.faction.value,
                    "target_faction": target_unit.faction.value,
                    "suggestion": "Select an enemy unit from a different faction",
                },
            )

        # === 第四层：必需组件验证 ===
        print(f"[ATTACK_ACTION] 检查攻击方组件...")
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

        print(f"[ATTACK_ACTION] 检查目标组件...")
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

        # === 第五层：行动点验证 ===
        print(f"[ATTACK_ACTION] 检查行动点...")
        if not attacker_action_points.can_perform_action(ActionType.ATTACK):
            required_ap = 2  # 攻击需要2点行动点
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

        # === 第六层：单位状态验证 ===
        print(f"[ATTACK_ACTION] 检查单位状态...")

        # 检查攻击方人数（人数≤10%无法主动攻击）
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

        # 注释掉攻击次数限制 - 允许多次攻击（只要有足够的行动点）
        # if attacker_combat.has_attacked:
        #     return self._create_error_response(
        #         f"Unit {unit_id} has already attacked this turn",
        #         {
        #             "unit_id": unit_id,
        #             "suggestion": "Each unit can only attack once per turn",
        #         },
        #     )

        # 检查目标是否还活着
        if target_count.current_count <= 0:
            return self._create_error_response(
                f"Target unit {target_id} is already destroyed",
                {
                    "target_id": target_id,
                    "current_count": target_count.current_count,
                    "suggestion": "Select a living enemy unit",
                },
            )

        # === 第七层：距离和范围验证 ===
        print(f"[ATTACK_ACTION] 检查攻击范围...")
        attacker_current_pos = (attacker_pos.col, attacker_pos.row)
        target_current_pos = (target_pos.col, target_pos.row)
        distance = HexMath.hex_distance(attacker_current_pos, target_current_pos)
        attack_range = attacker_combat.attack_range

        print(f"[ATTACK_ACTION] 距离={distance}, 攻击范围={attack_range}")

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

        # === 第八层：执行攻击 ===
        print(f"[ATTACK_ACTION] 所有验证通过，执行攻击...")
        combat_system = self._get_combat_system()
        if not combat_system:
            return self._create_error_response(
                "Combat system not available",
                {
                    "system_error": "CombatSystem not found",
                    "suggestion": "This is a game engine error - contact administrator",
                },
            )

        # 记录攻击前状态以便对比
        pre_attack_state = {
            "attacker_action_points": attacker_action_points.current_ap,
            "target_count": target_count.current_count,
            "attacker_has_attacked": attacker_combat.has_attacked,
        }

        # 调用战斗系统执行攻击
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

        # === 第九层：格式化返回结果 ===
        print(f"[ATTACK_ACTION] 攻击执行成功，格式化结果...")

        # 获取攻击后状态
        post_attack_state = {
            "attacker_action_points": attacker_action_points.current_ap,
            "target_count": target_count.current_count,
            "attacker_has_attacked": attacker_combat.has_attacked,
        }

        # 计算变化
        action_points_used = (
            pre_attack_state["attacker_action_points"]
            - post_attack_state["attacker_action_points"]
        )
        casualties_inflicted = (
            pre_attack_state["target_count"] - post_attack_state["target_count"]
        )
        target_destroyed = post_attack_state["target_count"] <= 0

        # 获取地形信息
        attacker_terrain = self._get_terrain_at_position(attacker_current_pos)
        target_terrain = self._get_terrain_at_position(target_current_pos)

        result = {
            "success": True,
            "message": f"Unit {unit_id} attacked unit {target_id} successfully",
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
                "battle_result": attack_result,  # 包含详细的战斗结果
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
            f"[ATTACK_ACTION] 攻击完成: 造成{casualties_inflicted}人伤亡，目标{'被摧毁' if target_destroyed else '存活'}"
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

        # 执行待命
        action_system = self._get_action_system()
        if action_system:
            success = action_system.perform_wait(unit_id)
            if success:
                action_points = self.world.get_component(unit_id, ActionPoints)
                unit_status = self.world.get_component(unit_id, UnitStatus)

                return {
                    "success": True,
                    "message": f"Unit {unit_id} is resting and recovering",
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
                "message": f"Unit {unit_id} occupied territory at {target_pos}",
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
                    skill_result.get("error", "Skill execution failed")
                )
        else:
            return self._create_error_response("Unit position not found")

    # ==================== 观测动作 ====================

    def handle_observation_action(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理单位观测"""
        unit_id = params.get("unit_id")
        observation_level = params.get("observation_level", "basic")

        if not isinstance(unit_id, int):
            return self._create_error_response("unit_id must be integer")

        # 检查单位存在性
        unit = self.world.get_component(unit_id, Unit)
        if not unit:
            return self._create_error_response(f"Unit {unit_id} not found")

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

    # ==================== 阵营控制动作 ====================

    def handle_faction_state(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """获取阵营状态"""
        faction_str = params.get("faction")

        if not faction_str:
            return self._create_error_response("faction parameter required")

        try:
            faction = Faction(faction_str)
            print(f"Handling faction state for {faction.value}")
        except ValueError:
            return self._create_error_response(f"Invalid faction: {faction_str}")

        # 获取阵营所有单位
        faction_units = self._get_faction_units(faction)

        # 计算阵营统计
        total_units_count = len(faction_units)
        alive_units = [u for u in faction_units if self._is_unit_alive(u)]
        alive_units_count = len(alive_units)

        # 计算可行动单位（存活且有行动点）
        actionable_units = [u for u in alive_units if self._can_unit_take_action(u)]
        actionable_units_count = len(actionable_units)

        # 获取阵营当前状态
        faction_status = self._get_faction_status(faction)

        print(f"final {faction.value}")
        return {
            "success": True,
            "state": faction_status,  # 阵营整体状态：active/in_battle/victory/defeat/eliminated/draw
            "faction": faction.value,
            "total_units": total_units_count,
            "alive_units": alive_units_count,  # 存活单位数（人数>0）
            "actionable_units": actionable_units_count,  # 可行动单位数（存活且有行动点）
            "units": [
                self._get_detailed_unit_info(unit_id) for unit_id in alive_units[:10]
            ],  # 返回存活单位的详细信息
        }

    def handle_action_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """返回所有可用动作的接口文档描述"""
        action_docs = {
            "actions": {
                "move": {
                    "description": "移动单位到指定位置（可多次移动，直到移动力耗尽）",
                    "parameters": {
                        "unit_id": {
                            "type": "int",
                            "required": True,
                            "description": "移动的单位ID，必须是存活单位",
                        },
                        "target_position": {
                            "type": "object",
                            "required": True,
                            "description": "目标位置，列坐标和行坐标",
                            "properties": {
                                "col": {"type": "int", "description": "列坐标"},
                                "row": {"type": "int", "description": "行坐标"},
                            },
                        },
                    },
                },
                "attack": {
                    "description": "攻击指定敌方单位（可多次攻击，直到行动点耗尽）",
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
                },
                "observation": {
                    "description": "获取单位周围的观测信息",
                    "parameters": {
                        "unit_id": {
                            "type": "int",
                            "required": True,
                            "description": "单位ID，必须是存活",
                        },
                        "observation_level": {
                            "type": "string",
                            "required": False,
                            "description": "观测级别",
                            "default": "basic",
                            "options": ["basic", "detailed", "tactical"],
                        },
                    },
                },
                "get_faction_state": {
                    "description": "获取阵营整体状态信息，包括总单位数量、存活单位数量、单位详细信息列表",
                    "parameters": {
                        "faction": {
                            "type": "string",
                            "required": True,
                            "description": "阵营名称(wei | shu | wu)",
                        }
                    },
                },
                "end_turn": {
                    "description": "结束当前回合，可结束当前阵营的回合，如果当前阵营没有行动点，则结束回合，并结束当前任务",
                    "parameters": {
                        "faction": {
                            "type": "string",
                            "required": True,
                            "description": "自己当前阵营名称(wei | shu | wu)",
                        },
                        "force": {
                            "type": "bool",
                            "required": False,
                            "description": "是否强制结束，如果为True，则无论当前阵营是否有行动点，都结束回合",
                            "default": False,
                        },
                    },
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
                "observe_surroundings": {
                    "action": "observation",
                    "params": {"unit_id": 123, "observation_level": "detailed"},
                },
                "get_faction_overview": {
                    "action": "get_faction_state",
                    "params": {"faction": "wei"},
                },
            },
        }

        return {"success": True, **action_docs}

    def handle_action_list_full(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """返回所有可用动作的接口文档描述"""
        action_docs = {
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
                        },
                        "remaining_resources": {
                            "type": "object",
                            "description": "剩余资源",
                        },
                    },
                    "prerequisites": [
                        "单位存在",
                        "有足够行动点和移动力",
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
                    "prerequisites": [
                        "单位存在",
                        "目标在攻击范围内",
                        "敌对阵营",
                        "足够行动点",
                    ],
                },
                "rest": {
                    "category": "unit_control",
                    "description": "单位休整并恢复状态",
                    "parameters": {
                        "unit_id": {
                            "type": "int",
                            "required": True,
                            "description": "单位ID",
                        }
                    },
                    "prerequisites": ["单位存在"],
                },
                "occupy": {
                    "category": "unit_control",
                    "description": "占领指定区域，不消耗建筑点但消耗行动点",
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
                    "prerequisites": [
                        "单位存在",
                        "目标位置未被己方占领",
                        "目标位置在当前或相邻格",
                        "足够行动点",
                    ],
                },
                "fortify": {
                    "category": "unit_control",
                    "description": "在已占领区域建设工事，增加防御力，消耗建筑点和行动点",
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
                        },
                    },
                    "prerequisites": [
                        "单位存在",
                        "目标已被己方占领",
                        "工事未达上限",
                        "地形允许",
                        "足够行动点和建筑点",
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
                    "prerequisites": [
                        "单位存在",
                        "技能可用",
                        "无冷却",
                        "足够行动点",
                    ],
                },
                # 观测动作
                "observation": {
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
                    "prerequisites": ["单位存在"],
                },
                # 阵营信息
                "get_faction_state": {
                    "category": "faction_control",
                    "description": "获取阵营整体状态，包括战斗状态、胜负情况等",
                    "parameters": {
                        "faction": {
                            "type": "string",
                            "required": True,
                            "description": "阵营名称(wei/shu/wu)",
                        }
                    },
                    "returns": {
                        "success": {"type": "bool", "description": "执行是否成功"},
                        "state": {
                            "type": "string",
                            "description": "阵营状态：active(活跃)/in_battle(战斗中)/victory(胜利)/defeat(失败)/eliminated(被消灭)/draw(平局)",
                        },
                        "status_details": {
                            "type": "object",
                            "description": "详细状态信息",
                        },
                        "faction": {"type": "string", "description": "阵营名称"},
                        "total_units": {"type": "int", "description": "总单位数量"},
                        "alive_units": {"type": "int", "description": "存活单位数量"},
                        "units": {"type": "array", "description": "单位详细信息列表"},
                    },
                    "prerequisites": ["有效阵营名称"],
                },
                # System
                "get_action_list": {
                    "category": "system",
                    "description": "获取所有可用动作的接口文档",
                    "parameters": {},
                    "prerequisites": ["无"],
                },
                "end_turn": {
                    "category": "system",
                    "description": "所有unit无法行动时，或者已完成全部计划时，可以结束当前回合，交由对手执行，己方除了观察不可再进行任何操作",
                    "parameters": {
                        "faction": {
                            "type": "string",
                            "required": True,
                            "description": "自己当前阵营名称(wei | shu | wu)",
                        },
                        "force": {
                            "type": "bool",
                            "required": False,
                            "description": "是否强制结束",
                            "default": False,
                        },
                    },
                    "prerequisites": ["游戏进行中", "当前阵营回合"],
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

        return {"success": True, **action_docs}

    def handle_end_turn(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理结束回合动作"""
        faction_str = params.get("faction")
        force = params.get("force", False)

        if not faction_str:
            return self._create_error_response("faction parameter required")

        try:
            faction = Faction(faction_str)
        except ValueError:
            return self._create_error_response(f"Invalid faction: {faction_str}")

        # 检查游戏状态
        game_state = self.world.get_singleton_component(GameState)
        if not game_state:
            return self._create_error_response("Game not initialized")

        if game_state.game_over:
            return self._create_error_response("Game is already over")

        # 获取回合管理系统
        turn_system = self._get_turn_system()
        if not turn_system:
            return self._create_error_response("Turn system not available")

        # 检查是否是当前玩家的回合
        current_player = self._get_current_player()
        if not current_player or current_player.faction != faction:
            return self._create_error_response(
                f"Not {faction.value}'s turn. Current turn: {current_player.faction.value if current_player else 'unknown'}",
            )

        # 执行结束回合
        success = turn_system.agent_end_turn()

        if success:
            # 获取新的当前玩家
            new_current_player = self._get_current_player()
            next_faction = (
                new_current_player.faction.value if new_current_player else "unknown"
            )

            return {
                "success": True,
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

    # ==================== 辅助方法 ====================

    def _create_error_response(
        self, message: str, extra_data: Dict = None
    ) -> Dict[str, Any]:
        """创建错误响应 - 统一使用消息格式"""
        response = {
            "success": False,
            "message": message,
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

        # 获取单位当前位置和相关组件
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
                # 添加占领信息
                "territory_control": self._get_territory_control_info(
                    pos, unit.faction if unit else None
                ),
                # 添加移动可达性信息
                "movement_accessibility": self._get_movement_accessibility_info(
                    unit_id, current_pos, pos, movement_points, unit_count
                ),
                # 添加攻击范围信息
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
                # "path": [current_pos],
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
                    # "path": path,
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
                    # "path": [],
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
                # "path": [],
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

    def _is_unit_alive(self, unit_id: int) -> bool:
        """检查单位是否存活（人数>0）"""
        unit_count = self.world.get_component(unit_id, UnitCount)
        return unit_count and unit_count.current_count > 0

    def _can_unit_take_action(self, unit_id: int) -> bool:
        """检查单位是否可以执行行动（存活且有行动点）"""
        if not self._is_unit_alive(unit_id):
            return False

        action_points = self.world.get_component(unit_id, ActionPoints)
        return action_points and action_points.current_ap > 0

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

    def _get_turn_system(self):
        """获取回合系统"""
        for system in self.world.systems:
            if system.__class__.__name__ == "TurnSystem":
                return system
        return None

    def _get_current_player(self):
        """获取当前阵营"""
        # turn_manager = self.world.get_singleton_component(TurnManager)
        # if turn_manager:
        #     current_player_entity = turn_manager.get_current_player()
        #     if current_player_entity:
        #         return self.world.get_component(current_player_entity, Player)

        # 备用方法：通过 GameState 获取当前阵营
        game_state = self.world.get_singleton_component(GameState)
        if game_state:
            for entity in self.world.query().with_component(Player).entities():
                player = self.world.get_component(entity, Player)
                if player and player.faction == game_state.current_player:
                    return player
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

        # 将不可通过的地形（如水域）也视为障碍，保持与 MovementSystem 一致
        map_data = self.world.get_singleton_component(MapData)
        if map_data:
            for (q, r), tile_entity in map_data.tiles.items():
                terrain = self.world.get_component(tile_entity, Terrain)
                if terrain and terrain.terrain_type == TerrainType.WATER:
                    obstacles.add((q, r))

        print(
            f"[DEBUG] 实际障碍数量(含水域): {len(obstacles)} (排除单位 {exclude_unit_id})"
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
        from ..prefabs.config import GameConfig

        terrain_type = self._get_terrain_at_position(position)
        terrain_effect = GameConfig.TERRAIN_EFFECTS.get(terrain_type)
        return terrain_effect.movement_cost if terrain_effect else 1

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

    def _is_position_within_map_bounds(self, col: int, row: int) -> bool:
        """检查位置是否在地图边界内"""
        from ..prefabs.config import GameConfig

        # 地图使用以(0,0)为中心的坐标系
        # 对于MAP_WIDTH=20, MAP_HEIGHT=20:
        # center = MAP_WIDTH // 2 = 10
        # 实际坐标范围: col [-10, 9], row [-10, 9]
        center = GameConfig.MAP_WIDTH // 2
        min_coord = -center
        max_coord = center - 1

        return (min_coord <= col <= max_coord) and (min_coord <= row <= max_coord)

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

    def _get_terrain_occupation_bonus(self, terrain_type: TerrainType) -> float:
        """获取地形占领加成"""
        occupation_bonuses = {
            TerrainType.PLAIN: 0.0,
            TerrainType.FOREST: 0.1,  # 10% 隐蔽加成
            TerrainType.HILL: 0.15,  # 15% 视野加成
            TerrainType.MOUNTAIN: 0.2,  # 20% 防御加成
            TerrainType.CITY: 0.3,  # 30% 资源加成
            TerrainType.URBAN: 0.25,  # 25% 人口加成
            TerrainType.WATER: 0.0,  # 不可占领
        }
        return occupation_bonuses.get(terrain_type, 0.0)

    def _get_terrain_resource_value(self, terrain_type: TerrainType) -> int:
        """获取地形资源价值"""
        resource_values = {
            TerrainType.PLAIN: 2,  # 基础农业产出
            TerrainType.FOREST: 1,  # 木材资源
            TerrainType.HILL: 1,  # 矿物资源
            TerrainType.MOUNTAIN: 1,  # 稀有矿物
            TerrainType.CITY: 5,  # 高价值城市
            TerrainType.URBAN: 3,  # 中等城镇
            TerrainType.WATER: 0,  # 无直接资源
        }
        return resource_values.get(terrain_type, 1)

    def _get_faction_status(self, faction: Faction) -> str:
        """获取阵营当前状态：战斗中、胜利、失败或活跃"""
        # 检查游戏是否结束
        game_state = self.world.get_singleton_component(GameState)
        if game_state and game_state.game_over:
            # 游戏已结束，检查获胜者
            if game_state.winner == faction:
                return "victory"  # 胜利
            elif game_state.winner is not None:
                return "defeat"  # 失败（其他阵营获胜）
            else:
                return "draw"  # 平局

        # 检查专门的获胜者组件
        from ..components.game_over import Winner

        winner_component = self.world.get_singleton_component(Winner)
        if winner_component and winner_component.faction is not None:
            if winner_component.faction == faction:
                return "victory"
            else:
                return "defeat"

        # 游戏进行中，检查阵营是否有存活单位
        alive_units = [
            u for u in self._get_faction_units(faction) if self._is_unit_alive(u)
        ]
        if not alive_units:
            return "eliminated"  # 已被消灭

        # 检查是否有其他阵营的存活单位（判断是否在战斗中）
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
                # 如果最近有战斗记录，认为在战斗中
                recent_battles = battle_log.entries[-3:]  # 最近3次战斗
                for entry in recent_battles:
                    if (
                        hasattr(entry, "attacker_faction")
                        and entry.attacker_faction == faction
                    ) or (
                        hasattr(entry, "defender_faction")
                        and entry.defender_faction == faction
                    ):
                        return "in_battle"  # 战斗中

            return "active"  # 活跃状态
        else:
            return "victory"  # 其他阵营都被消灭，本阵营获胜

    def _get_territory_control_info(
        self, position: Tuple[int, int], unit_faction: Faction = None
    ) -> Dict[str, Any]:
        """获取地块占领信息"""
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

        # 获取当前控制阵营
        current_control = territory_system.get_territory_control(position)

        # 判断阵营关系
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
        """获取移动可达性信息"""
        if not current_pos or not movement_points or not unit_count:
            return {
                "reachable": False,
                "reason": "missing_movement_components",
                "movement_cost": -1,
                "remaining_movement": 0,
            }

        # 如果是当前位置
        if current_pos == target_pos:
            return {
                "reachable": True,
                "reason": "current_position",
                "movement_cost": 0,
                "remaining_movement": movement_points.current_mp,
                "is_current_position": True,
            }

        # 计算有效移动力（考虑人数损失）
        effective_movement = movement_points.get_effective_movement(unit_count)

        # 检查目标位置是否被其他单位占据
        obstacles = self._get_obstacles_excluding_unit(unit_id)
        if target_pos in obstacles:
            return {
                "reachable": False,
                "reason": "position_occupied",
                "movement_cost": -1,
                "remaining_movement": movement_points.current_mp,
                "blocked_by": "other_unit",
            }

        # 尝试寻找路径
        try:
            from ..utils.hex_utils import PathFinding

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
        """获取攻击范围信息"""
        if not current_pos or not combat:
            return {
                "in_attack_range": False,
                "distance": -1,
                "attack_range": 0,
                "can_attack": False,
            }

        # 计算距离
        from ..utils.hex_utils import HexMath

        distance = HexMath.hex_distance(current_pos, target_pos)
        attack_range = combat.attack_range

        # 判断是否在攻击范围内
        in_range = distance <= attack_range

        # 判断是否可以攻击（距离合适且不是当前位置）
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
        """处理Agent信息注册"""
        try:
            # 验证必需参数
            required_params = ["faction", "provider", "model_id", "base_url"]
            for param in required_params:
                if param not in params:
                    return {"success": False, "message": f"缺少必需参数: {param}"}

            faction = params["faction"]
            provider = params["provider"]
            model_id = params["model_id"]
            base_url = params["base_url"]

            # 创建Agent信息对象
            from ..components.agent_info import AgentInfo, AgentInfoRegistry

            agent_info = AgentInfo(
                provider=provider,
                model_id=model_id,
                base_url=AgentInfoRegistry.sanitize_url(base_url),
                agent_id=params.get("agent_id"),
                version=params.get("version"),
                note=params.get("note"),
            )

            # 获取或创建注册表
            registry = self.world.get_singleton_component(AgentInfoRegistry)
            if not registry:
                registry = AgentInfoRegistry()
                self.world.add_singleton_component(registry)

            # 注册Agent信息
            success = registry.register_agent(faction, agent_info)

            if success:
                return {
                    "success": True,
                    "message": f"Agent信息注册成功: {faction}阵营",
                    "registered_info": {
                        "faction": faction,
                        "provider": provider,
                        "model_id": model_id,
                        "base_url_sanitized": agent_info.base_url,
                    },
                }
            else:
                return {"success": False, "message": "Agent信息注册失败"}

        except Exception as e:
            return {"success": False, "message": f"注册Agent信息时出错: {str(e)}"}
