"""
玩家相关组件
"""

from dataclasses import dataclass, field
from typing import Set, Tuple
from framework_v2 import Component
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


@dataclass
class TurnOrder(Component):
    """回合顺序组件"""

    order: int  # 回合顺序
