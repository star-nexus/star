"""
回合系统 - 管理回合制游戏的回合逻辑（按规则手册v1.2）
"""

from framework import System, World
from framework.engine.events import EBS
from ..components import (
    Player,
    GameState,
    MovementPoints,
    Combat,
    Unit,
    GameModeComponent,
    ActionPoints,
    UnitCount,
)
from ..prefabs.config import GameConfig, GameMode, Faction
from ..utils.env_events import TurnStartEvent


class TurnSystem(System):
    """回合系统 - 专注于回合制游戏的回合逻辑"""

    def __init__(self):
        super().__init__(required_components={Player}, priority=90)
        self.turn_timer = 0.0
        self.auto_turn_duration = 30.0  # 自动回合时间（秒）

    def initialize(self, world: World) -> None:
        self.world = world

        # 检查是否已经有游戏状态组件
        game_state = self.world.get_singleton_component(GameState)
        if not game_state:
            # 如果没有，创建一个默认的游戏状态
            game_state = GameState(
                current_player=Faction.WEI,
                turn_number=1,
                game_over=False,
                max_turns=GameConfig.MAX_TURNS,
            )
            self.world.add_singleton_component(game_state)

        # 设置第一个玩家
        self._start_next_turn()

    def subscribe_events(self):
        pass

    def update(self, delta_time: float) -> None:
        game_mode = self.world.get_singleton_component(GameModeComponent)
        game_state = self.world.get_singleton_component(GameState)

        # 只在回合制模式下工作
        if not game_mode or not game_mode.is_turn_based():
            return

        if not game_state or game_state.game_over:
            return

        self._update_turn_based(delta_time)

    def _update_turn_based(self, delta_time: float) -> None:
        """更新回合制模式"""
        # 检查游戏结束条件
        if self._check_game_over():
            return

    def end_turn(self):
        """结束当前回合"""
        # 重置单位行动状态
        self._reset_unit_actions()

        # 检查游戏结束条件
        if self._check_game_over():
            return

        # 开始下一个回合
        self._start_next_turn()

    def agent_end_turn(self):
        """结束当前阵营的行动，切换到下一个阵营"""
        # 检查游戏结束条件
        if self._check_game_over():
            return True

        # 切换到下一个阵营（不重置单位状态）
        self._switch_to_next_faction()

        # 向下一个要行动的 agent 发送 start_turn 通知
        # self._notify_next_agent_turn()

        return True

    def _switch_to_next_faction(self):
        """切换到下一个阵营（阵营轮转逻辑）"""
        game_state = self.world.get_singleton_component(GameState)
        players = list(self.world.query().with_component(Player).entities())

        if not players:
            return

        # 获取下一个玩家
        current_index = 0
        if game_state.current_player:
            for i, entity in enumerate(players):
                player = self.world.get_component(entity, Player)
                if player and player.faction == game_state.current_player:
                    current_index = (i + 1) % len(players)
                    break

        # 设置新的当前玩家
        next_player_entity = players[current_index]
        next_player = self.world.get_component(next_player_entity, Player)

        if next_player:
            previous_faction = game_state.current_player
            game_state.current_player = next_player.faction

            print(
                f"🔄 阵营切换: {previous_faction.value} -> {next_player.faction.value}"
            )

            # 记录阵营变化到统计系统
            statistics_system = self._get_statistics_system()
            if statistics_system:
                statistics_system.record_turn_change(
                    previous_faction, next_player.faction
                )

            # 如果回到第一个玩家（索引0），说明所有阵营都行动完毕，开始新回合
            if current_index == 0:
                game_state.turn_number += 1
                print(f"🔄 新回合开始: 第 {game_state.turn_number} 回合")

                # 只有在新回合开始时才重置所有单位的行动状态
                self._reset_unit_actions()

            # 重置回合计时器
            self.turn_timer = 0.0

            # 发送回合开始事件
            EBS.publish(TurnStartEvent(game_state.current_player))

    def _reset_unit_actions(self):
        """重置所有单位的行动状态"""
        # 获取行动系统来重置回合行动
        action_system = self._get_action_system()
        if action_system:
            action_system.reset_turn_actions()
        else:
            # 备用方案：直接重置
            self._manual_reset_actions()

    def _manual_reset_actions(self):
        """手动重置行动状态"""
        for entity in self.world.query().with_component(MovementPoints).entities():
            movement = self.world.get_component(entity, MovementPoints)
            unit_count = self.world.get_component(entity, UnitCount)
            action_points = self.world.get_component(entity, ActionPoints)

            if movement:
                if unit_count:
                    movement.current_mp = movement.get_effective_movement(unit_count)
                else:
                    movement.current_mp = movement.base_mp
                # movement.has_moved = False  # 移除单次移动限制

            if action_points:
                action_points.reset()

        for entity in self.world.query().with_component(Combat).entities():
            combat = self.world.get_component(entity, Combat)
            if combat:
                pass  # combat.has_attacked = False  # 移除单次攻击限制

    def _start_next_turn(self):
        """开始下一个回合（完整的回合重置，用于游戏开始等情况）"""
        game_state = self.world.get_singleton_component(GameState)
        players = list(self.world.query().with_component(Player).entities())

        if not players:
            return

        # 获取下一个玩家
        current_index = 0
        if game_state.current_player:
            for i, entity in enumerate(players):
                player = self.world.get_component(entity, Player)
                if player and player.faction == game_state.current_player:
                    current_index = (i + 1) % len(players)
                    break

        # 设置新的当前玩家
        next_player_entity = players[current_index]
        next_player = self.world.get_component(next_player_entity, Player)

        if next_player:
            previous_faction = game_state.current_player
            game_state.current_player = next_player.faction

            print(f"🎮 游戏开始: {game_state.current_player.value} 阵营先行动")

            # 记录回合变化到统计系统
            statistics_system = self._get_statistics_system()
            if statistics_system:
                statistics_system.record_turn_change(
                    previous_faction, next_player.faction
                )

            # 如果回到第一个玩家，增加回合数
            if current_index == 0:
                game_state.turn_number += 1

            # 重置回合计时器
            self.turn_timer = 0.0

            # 发送回合开始事件
            EBS.publish(TurnStartEvent(game_state.current_player))

    # def _notify_next_agent_turn(self):
    #     """向下一个要行动的 agent 发送 start_turn 通知"""
    #     game_state = self.world.get_singleton_component(GameState)
    #     if not game_state:
    #         return

    #     # 获取 LLM 系统来发送通知
    #     llm_system = self._get_llm_system()
    #     if llm_system and hasattr(llm_system, "client"):
    #         try:
    #             # 构造 start_turn 消息
    #             start_turn_message = {
    #                 "type": "start_turn",
    #                 "data": {
    #                     "faction": game_state.current_player.value,
    #                     "turn_number": game_state.turn_number,
    #                     "timestamp": self._get_current_timestamp(),
    #                     "message": f"It's {game_state.current_player.value}'s turn to act",
    #                 },
    #             }

    #             # 发送给所有连接的 agents
    #             for agent_id in llm_system.client.connected_agents:
    #                 llm_system.client.send_message(
    #                     start_turn_message, target={"type": "agent", "id": agent_id}
    #                 )

    #             print(
    #                 f"📢 已向 agents 发送回合开始通知: {game_state.current_player.value}"
    #             )

    #         except Exception as e:
    #             print(f"❌ 发送回合开始通知失败: {e}")

    def _get_current_timestamp(self):
        """获取当前时间戳"""
        import time

        return time.time()

    def _get_statistics_system(self):
        """获取统计系统"""
        for system in self.world.systems:
            if system.__class__.__name__ == "StatisticsSystem":
                return system
        return None

    def _get_action_system(self):
        """获取行动系统"""
        for system in self.world.systems:
            if system.__class__.__name__ == "ActionSystem":
                return system
        return None

    # def _get_llm_system(self):
    #     """获取 LLM 系统"""
    #     for system in self.world.systems:
    #         if system.__class__.__name__ == "LLMSystem":
    #             return system
    #     return None

    def _check_game_over(self) -> bool:
        """检查游戏是否结束"""
        game_state = self.world.get_singleton_component(GameState)

        # 检查回合数限制
        if game_state.turn_number > game_state.max_turns:
            game_state.game_over = True
            return True

        # 检查是否只剩一个阵营有单位
        factions_with_units = set()
        for entity in self.world.query().with_component(Unit).entities():
            unit = self.world.get_component(entity, Unit)
            unit_count = self.world.get_component(entity, UnitCount)

            # 只计算还有人数的单位
            if unit and unit_count and unit_count.current_count > 0:
                factions_with_units.add(unit.faction)

        if len(factions_with_units) <= 1:
            game_state.game_over = True
            if factions_with_units:
                game_state.winner = list(factions_with_units)[0]
            return True

        return False
