"""
游戏时间系统 - 统一管理游戏时间
"""

from framework import System, World
from ..components import GameTime, GameModeComponent, GameState, TurnManager
from ..prefabs.config import GameMode


class GameTimeSystem(System):
    """游戏时间系统 - 提供统一的时间管理"""

    def __init__(self):
        super().__init__(priority=10)  # 较早执行，为其他系统提供时间服务

    def initialize(self, world: World) -> None:
        """初始化游戏时间系统"""
        self.world = world

        # 确保GameTime组件存在
        game_time = world.get_singleton_component(GameTime)
        if not game_time:
            game_time = GameTime()
            world.add_singleton_component(game_time)

        # 根据当前游戏模式初始化
        game_mode = world.get_singleton_component(GameModeComponent)
        if game_mode:
            game_time.initialize(game_mode.mode)
        else:
            game_time.initialize(GameMode.TURN_BASED)

    def subscribe_events(self):
        """订阅事件"""
        pass

    def update(self, delta_time: float) -> None:
        """更新游戏时间"""
        game_time = self.world.get_singleton_component(GameTime)
        if game_time:
            game_time.update(delta_time)

            # 同步回合数（如果是回合制模式）
            if game_time.is_turn_based():
                self._sync_turn_number(game_time)

    def _sync_turn_number(self, game_time: GameTime):
        """同步回合数与游戏状态"""
        game_state = self.world.get_singleton_component(GameState)
        if game_state and game_state.turn_number != game_time.current_turn:
            # 如果游戏状态的回合数发生变化，同步到时间系统
            if game_state.turn_number > game_time.current_turn:
                game_time.current_turn = game_state.turn_number
                game_time.turn_start_time = game_time.last_update_time

    def advance_turn(self):
        """推进到下一回合（供回合系统调用）"""
        game_time = self.world.get_singleton_component(GameTime)
        if game_time:
            game_time.advance_turn()

    def pause_game(self):
        """暂停游戏时间"""
        game_time = self.world.get_singleton_component(GameTime)
        if game_time:
            game_time.pause()

    def resume_game(self):
        """恢复游戏时间"""
        game_time = self.world.get_singleton_component(GameTime)
        if game_time:
            game_time.resume()

    def set_time_scale(self, scale: float):
        """设置时间倍率"""
        game_time = self.world.get_singleton_component(GameTime)
        if game_time:
            game_time.set_time_scale(scale)

    def get_current_time_display(self) -> str:
        """获取当前时间显示"""
        game_time = self.world.get_singleton_component(GameTime)
        if game_time:
            return game_time.get_current_time_display()
        return "00:00"

    def get_current_turn(self) -> int:
        """获取当前回合数"""
        game_time = self.world.get_singleton_component(GameTime)
        if game_time:
            return game_time.current_turn
        return 1
