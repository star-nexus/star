"""
游戏模式组件
"""

from dataclasses import dataclass
from framework_v2 import SingletonComponent
from ..prefabs.config import GameMode


@dataclass
class GameModeComponent(SingletonComponent):
    """游戏模式单例组件"""

    mode: GameMode = GameMode.TURN_BASED

    def is_turn_based(self) -> bool:
        """是否为回合制模式"""
        return self.mode == GameMode.TURN_BASED

    def is_real_time(self) -> bool:
        """是否为实时模式"""
        return self.mode == GameMode.REAL_TIME
