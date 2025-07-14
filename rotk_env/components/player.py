"""
玩家相关组件
"""

from dataclasses import dataclass, field
from typing import Set, Tuple, List
from framework import Component, SingletonComponent
from ..prefabs.config import Faction, PlayerType


@dataclass
class Player(Component):
    """玩家组件"""

    faction: Faction
    player_type: PlayerType
    color: Tuple[int, int, int]
    units: Set[int] = field(default_factory=set)
    resources: int = 0
    score: int = 0
    name: str = ""

    def __post_init__(self):
        if not self.name:
            self.name = self.faction.value


@dataclass
class TurnOrder(Component):
    """回合顺序组件"""

    order: int  # 回合顺序


@dataclass
class TurnManager(SingletonComponent):
    """回合管理单例组件"""

    players: List[int] = field(default_factory=list)  # 玩家实体ID列表
    current_player_index: int = 0

    def get_current_player(self) -> int:
        """获取当前玩家实体ID"""
        if self.players and 0 <= self.current_player_index < len(self.players):
            return self.players[self.current_player_index]
        return None

    def next_player(self):
        """切换到下一个玩家"""
        if self.players:
            self.current_player_index = (self.current_player_index + 1) % len(
                self.players
            )

    def add_player(self, player_entity: int):
        """添加玩家"""
        if player_entity not in self.players:
            self.players.append(player_entity)
