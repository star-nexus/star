"""
Mock LLM AI 系统 - 使用普通AI逻辑但通过LLM Action Handler V3的API执行动作
不调用真正的大模型，而是用规则逻辑生成动作命令
"""

import random
import time
from typing import Set, List, Tuple, Optional, Dict, Any
from framework import System, World
from ..components import (
    Player,
    AIControlled,
    Unit,
    HexPosition,
    MovementPoints,
    Combat,
    UnitCount,
    UnitStatus,
    GameState,
    MapData,
    Terrain,
    GameModeComponent,
    ActionPoints,
)
from ..prefabs.config import GameConfig, TerrainType, ActionType, Faction
from ..utils.hex_utils import HexMath, PathFinding
from .llm_action_handler_v3 import LLMActionHandlerV3


class MockLLMAISystem(System):
    """Mock LLM AI系统 - 使用LLM Action Handler V3 API的AI决策系统"""

    def __init__(self):
        super().__init__(required_components={Player, AIControlled})
        self.decision_timer = 0.0
        self.decision_interval = 2.0  # AI决策间隔（秒）
        self.unit_last_action = {}  # 记录每个单位的最后行动时间
        self.llm_handler = None  # LLM Action Handler实例
        self.ai_memory = {}  # AI记忆，记录之前的决策和结果
        self.failed_actions = {}  # 记录失败的动作，避免重复尝试

    def initialize(self, world: World) -> None:
        """初始化Mock LLM AI系统"""
        self.world = world
        # 创建LLM Action Handler实例
        self.llm_handler = LLMActionHandlerV3(world)
        print("Mock LLM AI System initialized with LLM Action Handler V3")

    def subscribe_events(self):
        pass

    def update(self, delta_time: float) -> None:
        """更新Mock LLM AI系统"""
        game_state = self.world.get_singleton_component(GameState)
        game_mode = self.world.get_singleton_component(GameModeComponent)

        if not game_state or game_state.game_over or game_state.paused:
            return

        # 检查游戏模式
        is_realtime = game_mode and game_mode.is_real_time()

        self.decision_timer += delta_time

        if self.decision_timer >= self.decision_interval:
            if is_realtime:
                # 实时模式：所有AI玩家同时行动
                self._make_realtime_ai_decisions()
            else:
                # 回合制模式：只有当前玩家行动
                current_player = self._get_current_player()
                if current_player:
                    ai_controlled = self.world.get_component(
                        current_player, AIControlled
                    )
                    if ai_controlled:
                        self._execute_ai_turn(current_player, is_realtime=False)

            self.decision_timer = 0.0

    def _make_realtime_ai_decisions(self):
        """实时模式AI决策逻辑"""
        # 获取所有AI玩家
        ai_players = []
        for entity in self.world.query().with_all(Player, AIControlled).entities():
            ai_players.append(entity)

        # 为每个AI玩家执行决策
        for player_entity in ai_players:
            self._execute_ai_turn(player_entity, is_realtime=True)

    def _get_current_player(self) -> Optional[int]:
        """获取当前玩家实体"""
        game_state = self.world.get_singleton_component(GameState)
        if not game_state or not game_state.current_player:
            return None

        for entity in self.world.query().with_component(Player).entities():
            player = self.world.get_component(entity, Player)
            if player and player.faction == game_state.current_player:
                return entity
        return None

    def _execute_ai_turn(self, player_entity: int, is_realtime: bool = False):
        """执行AI回合 - 通过LLM Action Handler V3"""
        player = self.world.get_component(player_entity, Player)
        if not player:
            return

        print(
            f"\n=== Mock LLM AI Turn: {player.faction.value} ({'实时' if is_realtime else '回合制'}) ==="
        )

        # 清理过期的失败记录（超过30秒的记录）
        self._cleanup_old_failed_actions()

        # 检查胜利条件
        if self._check_victory_conditions():
            return  # 游戏已结束

        # 1. 获取阵营状态
        faction_state = self._get_faction_state(player.faction)
        if not faction_state.get("success"):
            print(f"❌ Failed to get faction state: {faction_state.get('message')}")
            if not is_realtime:  # 只在回合制模式下结束回合
                self._end_turn(player.faction)
            return

        alive_units = faction_state.get("alive_units", 0)
        actionable_units = faction_state.get("actionable_units", 0)

        print(
            f"📊 Faction State: {alive_units} alive units, {actionable_units} actionable units"
        )

        if actionable_units == 0:
            print(f"⏭️ No actionable units")

            # 检查是否应该结束游戏（所有单位都无法行动）
            if alive_units == 0:
                print(f"💀 {player.faction.value} has no surviving units - defeat!")
                self._trigger_game_over(player.faction, "defeat")
                return

            if not is_realtime:  # 只在回合制模式下结束回合
                print(f"⏭️ Ending turn")
                self._end_turn(player.faction)
            return

        # 2. 为每个单位制定并执行策略
        units_info = faction_state.get("units", [])
        actions_executed = 0
        max_actions_per_turn = 3 if is_realtime else 5  # 实时模式限制更少动作

        for unit_info in units_info:
            if actions_executed >= max_actions_per_turn:
                break

            unit_id = unit_info.get("unit_id")
            if not unit_id:
                continue

            # 在实时模式下检查单位行动冷却
            if is_realtime:
                current_time = time.time()
                last_action_time = self.unit_last_action.get(unit_id, 0)
                if current_time - last_action_time < 1.0:  # 1秒冷却
                    continue

            # 执行单位策略
            action_taken = self._execute_unit_strategy(
                unit_id, unit_info, player.faction, is_realtime
            )
            if action_taken:
                actions_executed += 1
                if is_realtime:
                    self.unit_last_action[unit_id] = time.time()
                else:
                    time.sleep(0.3)  # 回合制模式添加延迟，让动作效果更明显

        # 3. 处理回合结束
        print(f"✅ {player.faction.value} executed {actions_executed} actions")

        if not is_realtime:  # 只在回合制模式下结束回合
            print(f"⏭️ Ending turn")
            self._end_turn(player.faction)
        else:
            print(f"🔄 Continuing in realtime mode")

    def _get_faction_state(self, faction: Faction) -> Dict[str, Any]:
        """通过LLM Action Handler获取阵营状态"""
        return self.llm_handler.handle_faction_state({"faction": faction.value})

    def _execute_unit_strategy(
        self,
        unit_id: int,
        unit_info: Dict[str, Any],
        faction: Faction,
        is_realtime: bool = False,
    ) -> bool:
        """为单位执行策略 - 通过LLM Action Handler V3"""

        capabilities = unit_info.get("capabilities", {})
        turn_resources = capabilities.get("turn_resources", {})
        properties = capabilities.get("properties", {})
        position = unit_info.get("position", {})
        unit_status = unit_info.get("unit_status", {})

        action_points = turn_resources.get("action_points", 0)
        movement_points = turn_resources.get("movement_points", 0)
        health_percentage = unit_status.get("health_percentage", 0)

        print(
            f"🤖 Processing unit {unit_id}: AP={action_points}, MP={movement_points}, HP={health_percentage:.1f}%"
        )

        # 检查单位是否能行动
        if action_points <= 0:
            print(f"  ⏸️ Unit {unit_id} has no action points")
            return False

        if health_percentage <= 10:
            print(f"  💀 Unit {unit_id} is too weak to act ({health_percentage:.1f}%)")
            return False

        # 获取单位观察信息
        observation = self._get_unit_observation(unit_id)
        if not observation.get("success"):
            print(f"  ❌ Failed to get observation for unit {unit_id}")
            return False

        visible_environment = observation.get("visible_environment", [])

        # 分析周围环境，寻找敌人和机会
        enemy_targets = []
        strategic_positions = []

        for tile in visible_environment:
            tile_units = tile.get("units", [])
            tile_position = tile.get("position", {})
            terrain = tile.get("terrain", "plain")

            for tile_unit in tile_units:
                if tile_unit.get("faction") != faction.value:
                    enemy_targets.append(
                        {
                            "unit_id": tile_unit.get("unit_id"),
                            "position": tile_position,
                            "unit_type": tile_unit.get("unit_type"),
                            "faction": tile_unit.get("faction"),
                        }
                    )

            # 收集战略位置（城市、山丘等）
            if terrain in ["city", "hill", "mountain"]:
                strategic_positions.append(
                    {
                        "position": tile_position,
                        "terrain": terrain,
                        "territory_control": tile.get("territory_control", {}),
                    }
                )

        # 策略决策逻辑
        strategy_result = self._decide_strategy(
            unit_id,
            position,
            enemy_targets,
            strategic_positions,
            action_points,
            movement_points,
            properties,
        )

        return self._execute_strategy(strategy_result, faction)

    def _get_unit_observation(self, unit_id: int) -> Dict[str, Any]:
        """获取单位观察信息"""
        return self.llm_handler.handle_observation_action(
            {"unit_id": unit_id, "observation_level": "detailed"}
        )

    def _decide_strategy(
        self,
        unit_id: int,
        position: Dict[str, Any],
        enemy_targets: List[Dict],
        strategic_positions: List[Dict],
        action_points: int,
        movement_points: int,
        properties: Dict[str, Any],
    ) -> Dict[str, Any]:
        """决策策略 - 模拟LLM思考过程"""

        current_pos = (position.get("col", 0), position.get("row", 0))
        attack_range = properties.get("attack_range", 1)

        print(f"  🧠 Analyzing strategy for unit {unit_id} at {current_pos}")
        print(
            f"     Found {len(enemy_targets)} enemies, {len(strategic_positions)} strategic positions"
        )

        # 优先级1: 如果有敌人在攻击范围内，优先攻击
        for enemy in enemy_targets:
            enemy_pos = (
                enemy["position"].get("col", 0),
                enemy["position"].get("row", 0),
            )
            distance = HexMath.hex_distance(current_pos, enemy_pos)

            if distance <= attack_range and action_points >= 1:
                print(
                    f"     ⚔️ Enemy {enemy['unit_id']} in attack range (distance: {distance})"
                )
                return {
                    "action": "attack",
                    "params": {"unit_id": unit_id, "target_id": enemy["unit_id"]},
                    "reason": f"Attack enemy {enemy['unit_type']} at distance {distance}",
                }

        # 优先级2: 移动接近最近的敌人
        if enemy_targets and movement_points > 0:
            nearest_enemy = min(
                enemy_targets,
                key=lambda e: HexMath.hex_distance(
                    current_pos,
                    (e["position"].get("col", 0), e["position"].get("row", 0)),
                ),
            )

            enemy_pos = (
                nearest_enemy["position"].get("col", 0),
                nearest_enemy["position"].get("row", 0),
            )
            distance = HexMath.hex_distance(current_pos, enemy_pos)

            if distance > attack_range:
                # 计算移动目标位置（向敌人方向移动）
                target_pos = self._calculate_move_towards_enemy(
                    current_pos, enemy_pos, movement_points
                )

                if target_pos and target_pos != current_pos:
                    print(
                        f"     🏃 Moving towards enemy {nearest_enemy['unit_id']} at {enemy_pos}"
                    )
                    return {
                        "action": "move",
                        "params": {
                            "unit_id": unit_id,
                            "target_position": {
                                "col": target_pos[0],
                                "row": target_pos[1],
                            },
                        },
                        "reason": f"Move towards enemy {nearest_enemy['unit_type']} (distance: {distance})",
                    }

        # 优先级3: 占领战略位置
        if strategic_positions and action_points >= 1:
            # 获取当前单位的阵营
            unit_obj = self.world.get_component(unit_id, Unit)
            current_faction = unit_obj.faction.value if unit_obj else None

            for strategic_pos in strategic_positions:
                pos = strategic_pos["position"]
                target_pos = (pos.get("col", 0), pos.get("row", 0))
                distance = HexMath.hex_distance(current_pos, target_pos)

                # 如果在当前位置或相邻位置，尝试占领
                if distance <= 1:
                    territory_control = strategic_pos.get("territory_control", {})
                    controlled_by = territory_control.get("controlled_by")

                    # 检查是否之前尝试过这个位置的占领但失败了
                    action_key = f"occupy_{target_pos[0]}_{target_pos[1]}"
                    if (
                        unit_id in self.failed_actions
                        and action_key in self.failed_actions[unit_id]
                    ):
                        continue  # 跳过之前失败的动作

                    # 只有当位置未被本阵营控制时才尝试占领
                    if controlled_by != current_faction:
                        print(f"     🏰 Occupying strategic position {target_pos}")
                        return {
                            "action": "occupy",
                            "params": {
                                "unit_id": unit_id,
                                "position": {
                                    "col": target_pos[0],
                                    "row": target_pos[1],
                                },
                            },
                            "reason": f"Occupy strategic {strategic_pos['terrain']} position",
                        }

        # 优先级4: 如果没有敌人，向地图中心或对方区域移动探索
        if not enemy_targets and movement_points > 0:
            # 获取所有单位占据的位置，避免移动到被占用的位置
            occupied_positions = set()
            for entity in self.world.query().with_all(HexPosition, Unit).entities():
                pos = self.world.get_component(entity, HexPosition)
                if pos:
                    occupied_positions.add((pos.col, pos.row))

            # 生成多个可能的目标位置，选择未被占用的
            potential_targets = [
                (0, 0),  # 地图中心
                (2, 2),  # 右上区域
                (-2, -2),  # 左下区域
                (3, 0),  # 右侧
                (-3, 0),  # 左侧
                (0, 3),  # 上方
                (0, -3),  # 下方
            ]

            # 找到最近的未被占用的目标
            best_target = None
            min_distance = float("inf")

            for target in potential_targets:
                if target not in occupied_positions:
                    distance = HexMath.hex_distance(current_pos, target)
                    if (
                        distance > 2 and distance < min_distance
                    ):  # 至少要有一定距离才值得移动
                        min_distance = distance
                        best_target = target

            if best_target:
                target_pos = self._calculate_move_towards_position(
                    current_pos, best_target, movement_points
                )
                if (
                    target_pos
                    and target_pos != current_pos
                    and target_pos not in occupied_positions
                ):
                    print(f"     🎯 Exploring towards {best_target}")
                    return {
                        "action": "move",
                        "params": {
                            "unit_id": unit_id,
                            "target_position": {
                                "col": target_pos[0],
                                "row": target_pos[1],
                            },
                        },
                        "reason": f"Explore towards strategic area (distance: {min_distance})",
                    }

        # 优先级6: 移动到战略位置
        if strategic_positions and movement_points > 0:
            # 获取所有单位占据的位置
            occupied_positions = set()
            for entity in self.world.query().with_all(HexPosition, Unit).entities():
                pos = self.world.get_component(entity, HexPosition)
                if pos:
                    occupied_positions.add((pos.col, pos.row))

            # 找到最近的未被占用的战略位置
            unoccupied_strategic = []
            for strategic_pos in strategic_positions:
                pos = strategic_pos["position"]
                target_pos = (pos.get("col", 0), pos.get("row", 0))
                if target_pos not in occupied_positions:
                    unoccupied_strategic.append(strategic_pos)

            if unoccupied_strategic:
                nearest_strategic = min(
                    unoccupied_strategic,
                    key=lambda s: HexMath.hex_distance(
                        current_pos,
                        (s["position"].get("col", 0), s["position"].get("row", 0)),
                    ),
                )

                strategic_pos = (
                    nearest_strategic["position"].get("col", 0),
                    nearest_strategic["position"].get("row", 0),
                )

                target_pos = self._calculate_move_towards_position(
                    current_pos, strategic_pos, movement_points
                )

                if (
                    target_pos
                    and target_pos != current_pos
                    and target_pos not in occupied_positions
                ):
                    print(f"     🎯 Moving towards strategic position {strategic_pos}")
                    return {
                        "action": "move",
                        "params": {
                            "unit_id": unit_id,
                            "target_position": {
                                "col": target_pos[0],
                                "row": target_pos[1],
                            },
                        },
                        "reason": f"Move towards strategic {nearest_strategic['terrain']} position",
                    }

        # 优先级7: 建设工事（如果在己方控制的重要位置）
        if action_points >= 1:
            print(f"     🔨 Attempting to fortify current position")
            return {
                "action": "fortify",
                "params": {
                    "unit_id": unit_id,
                    "position": {"col": current_pos[0], "row": current_pos[1]},
                },
                "reason": "Fortify current position for defense",
            }

        # 最后选择: 休息
        print(f"     😴 No better options, resting")
        return {
            "action": "rest",
            "params": {"unit_id": unit_id},
            "reason": "Rest and recover",
        }

    def _calculate_move_towards_enemy(
        self,
        current_pos: Tuple[int, int],
        enemy_pos: Tuple[int, int],
        movement_points: int,
    ) -> Optional[Tuple[int, int]]:
        """计算向敌人移动的目标位置"""
        # 简单的启发式：向敌人方向移动1格
        dx = enemy_pos[0] - current_pos[0]
        dy = enemy_pos[1] - current_pos[1]

        # 归一化方向
        if abs(dx) > abs(dy):
            move_x = 1 if dx > 0 else -1
            move_y = 0
        elif abs(dy) > abs(dx):
            move_x = 0
            move_y = 1 if dy > 0 else -1
        else:
            # 对角移动
            move_x = 1 if dx > 0 else -1
            move_y = 1 if dy > 0 else -1

        target_pos = (current_pos[0] + move_x, current_pos[1] + move_y)

        # 检查移动距离是否在范围内
        if HexMath.hex_distance(current_pos, target_pos) <= movement_points:
            return target_pos

        return current_pos

    def _calculate_move_towards_position(
        self,
        current_pos: Tuple[int, int],
        target_pos: Tuple[int, int],
        movement_points: int,
    ) -> Optional[Tuple[int, int]]:
        """计算向目标位置移动"""
        distance = HexMath.hex_distance(current_pos, target_pos)

        if distance <= movement_points:
            return target_pos

        # 向目标方向移动1格
        return self._calculate_move_towards_enemy(
            current_pos, target_pos, movement_points
        )

    def _execute_strategy(self, strategy: Dict[str, Any], faction: Faction) -> bool:
        """执行策略 - 通过LLM Action Handler V3"""
        action = strategy.get("action")
        params = strategy.get("params", {})
        reason = strategy.get("reason", "")

        print(f"     🎮 Executing {action}: {reason}")

        try:
            if action == "attack":
                result = self.llm_handler.handle_attack_action(params)
            elif action == "move":
                result = self.llm_handler.handle_move_action(params)
            elif action == "occupy":
                result = self.llm_handler.handle_occupy_action(params)
            elif action == "fortify":
                result = self.llm_handler.handle_fortify_action(params)
            elif action == "rest":
                result = self.llm_handler.handle_rest_action(params)
            elif action == "skill":
                result = self.llm_handler.handle_skill_action(params)
            else:
                print(f"     ❌ Unknown action: {action}")
                return False

            success = result.get("success", False)
            message = result.get("message", "")

            if success:
                print(f"     ✅ {action} succeeded: {message}")

                # 记录成功的行动到AI记忆
                unit_id = params.get("unit_id")
                if unit_id:
                    self.ai_memory[unit_id] = {
                        "last_action": action,
                        "last_success": True,
                        "last_reason": reason,
                        "timestamp": time.time(),
                    }

                    # 如果成功了，清除失败记录
                    if unit_id in self.failed_actions:
                        action_key = self._get_action_key(action, params)
                        if action_key in self.failed_actions[unit_id]:
                            del self.failed_actions[unit_id][action_key]

                return True
            else:
                print(f"     ❌ {action} failed: {message}")

                # 记录失败的行动到记忆和失败列表
                unit_id = params.get("unit_id")
                if unit_id:
                    self.ai_memory[unit_id] = {
                        "last_action": action,
                        "last_success": False,
                        "last_reason": reason,
                        "last_error": message,
                        "timestamp": time.time(),
                    }

                    # 记录到失败动作列表，避免重复尝试
                    if unit_id not in self.failed_actions:
                        self.failed_actions[unit_id] = {}
                    action_key = self._get_action_key(action, params)
                    self.failed_actions[unit_id][action_key] = time.time()

                return False

        except Exception as e:
            print(f"     💥 Exception executing {action}: {e}")
            return False

    def _get_action_key(self, action: str, params: Dict[str, Any]) -> str:
        """生成动作的唯一键，用于记录失败动作"""
        if action == "occupy":
            pos = params.get("position", {})
            return f"occupy_{pos.get('col', 0)}_{pos.get('row', 0)}"
        elif action == "fortify":
            pos = params.get("position", {})
            return f"fortify_{pos.get('col', 0)}_{pos.get('row', 0)}"
        elif action == "move":
            pos = params.get("target_position", {})
            return f"move_{pos.get('col', 0)}_{pos.get('row', 0)}"
        elif action == "attack":
            target_id = params.get("target_id", 0)
            return f"attack_{target_id}"
        else:
            return f"{action}_general"

    def _cleanup_old_failed_actions(self):
        """清理超过30秒的失败动作记录"""
        current_time = time.time()
        for unit_id in list(self.failed_actions.keys()):
            unit_failed_actions = self.failed_actions[unit_id]
            # 移除超过30秒的失败记录
            expired_keys = [
                key
                for key, timestamp in unit_failed_actions.items()
                if current_time - timestamp > 30.0
            ]
            for key in expired_keys:
                del unit_failed_actions[key]

            # 如果单位没有失败记录了，移除整个条目
            if not unit_failed_actions:
                del self.failed_actions[unit_id]

    def _end_turn(self, faction: Faction):
        """结束AI回合"""
        try:
            # 首先尝试通过LLM Action Handler结束回合
            result = self.llm_handler.handle_end_turn({"faction": faction.value})
            if result.get("success"):
                print(f"✅ {faction.value} turn ended successfully")
                return True
            else:
                print(f"⚠️ LLM Handler failed to end turn: {result.get('message')}")

            # 如果LLM Handler失败，尝试直接调用回合系统
            turn_system = self._get_turn_system()
            if turn_system:
                # 检查是否有end_turn方法
                if hasattr(turn_system, "end_turn"):
                    turn_system.end_turn()
                    print(f"✅ {faction.value} turn ended via TurnSystem")
                    return True
                elif hasattr(turn_system, "agent_end_turn"):
                    turn_system.agent_end_turn()
                    print(
                        f"✅ {faction.value} turn ended via TurnSystem.agent_end_turn"
                    )
                    return True
                else:
                    print(f"⚠️ TurnSystem found but no end_turn method")
            else:
                print(f"⚠️ No TurnSystem available")

            # 如果都失败了，至少记录尝试
            print(f"⚠️ Could not end turn for {faction.value}, but continuing")
            return False

        except Exception as e:
            print(f"💥 Exception ending turn: {e}")
            return False

    def _get_turn_system(self):
        """获取回合系统"""
        for system in self.world.systems:
            if system.__class__.__name__ == "TurnSystem":
                return system
        return None

    def _trigger_game_over(self, losing_faction: Faction, reason: str):
        """触发游戏结束"""
        print(f"🏁 Game Over! {losing_faction.value} {reason}")

        game_state = self.world.get_singleton_component(GameState)
        if game_state:
            game_state.game_over = True
            # 可以设置获胜阵营等信息
            print(f"🎉 Game marked as over")

    def _check_victory_conditions(self):
        """检查胜利条件"""
        faction_status = {}

        # 检查每个阵营的存活单位
        for faction in [Faction.WEI, Faction.SHU, Faction.WU]:
            alive_units = 0
            for entity in self.world.query().with_component(Unit).entities():
                unit = self.world.get_component(entity, Unit)
                unit_count = self.world.get_component(entity, UnitCount)

                if (
                    unit
                    and unit.faction == faction
                    and unit_count
                    and unit_count.current_count > 0
                ):
                    alive_units += 1

            faction_status[faction] = alive_units

        # 检查是否有阵营全军覆没
        eliminated_factions = [
            faction for faction, count in faction_status.items() if count == 0
        ]
        surviving_factions = [
            faction for faction, count in faction_status.items() if count > 0
        ]

        if len(surviving_factions) <= 1:
            if len(surviving_factions) == 1:
                winner = surviving_factions[0]
                print(f"🎉 {winner.value} wins! All other factions eliminated.")
            else:
                print(f"🤝 Draw! All factions eliminated.")

            self._trigger_game_over(
                eliminated_factions[0] if eliminated_factions else Faction.WEI,
                "eliminated",
            )
            return True

        return False

    def get_ai_memory_summary(self) -> Dict[str, Any]:
        """获取AI记忆摘要 - 用于调试"""
        return {
            "total_units_tracked": len(self.ai_memory),
            "recent_actions": {
                unit_id: {
                    "action": memory.get("last_action"),
                    "success": memory.get("last_success"),
                    "reason": memory.get("last_reason", memory.get("last_error", "")),
                }
                for unit_id, memory in self.ai_memory.items()
            },
        }
