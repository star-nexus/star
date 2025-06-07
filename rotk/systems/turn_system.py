"""
回合系统 - 管理回合制游戏的回合逻辑
"""

from framework_v2 import System, World
from framework_v2.engine.events import EBS
from ..components import Player, GameState, Movement, Combat, Unit, GameModeComponent
from ..prefabs.config import GameConfig, GameMode, Faction
from ..events import TurnStartEvent


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
        # 在回合制模式下，主要检查回合结束条件
        # 具体的回合切换由事件触发

        # 检查游戏结束条件
        if self._check_game_over():
            return

        # 可以添加自动回合切换逻辑
        self.turn_timer += delta_time
        if self.turn_timer > self.auto_turn_duration:
            self.end_turn()

    def end_turn(self):
        """结束当前回合"""
        # 重置单位行动状态
        self._reset_unit_actions()

        # 检查游戏结束条件
        if self._check_game_over():
            return

        # 开始下一个回合
        self._start_next_turn()

    def _reset_unit_actions(self):
        """重置所有单位的行动状态"""
        for entity in self.world.query().with_component(Movement).entities():
            movement = self.world.get_component(entity, Movement)
            if movement:
                movement.current_movement = movement.max_movement
                movement.has_moved = False

        for entity in self.world.query().with_component(Combat).entities():
            combat = self.world.get_component(entity, Combat)
            if combat:
                combat.has_attacked = False

    def _start_next_turn(self):
        """开始下一个回合"""
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
            game_state.current_player = next_player.faction

            # 如果回到第一个玩家，增加回合数
            if current_index == 0:
                game_state.turn_number += 1

            # 重置回合计时器
            self.turn_timer = 0.0

            # 发送回合开始事件
            EBS.publish(TurnStartEvent(game_state.current_player))

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
            if unit:
                factions_with_units.add(unit.faction)

        if len(factions_with_units) <= 1:
            game_state.game_over = True
            if factions_with_units:
                game_state.winner = list(factions_with_units)[0]
            return True

        return False
