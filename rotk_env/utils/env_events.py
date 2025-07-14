"""
游戏事件模块
定义游戏中的各种事件
"""

from dataclasses import dataclass
from typing import Tuple, Optional
from framework import Event
from ..prefabs.config import Faction


@dataclass
class TurnStartEvent(Event):
    """回合开始事件"""

    faction: Faction


@dataclass
class TurnEndEvent(Event):
    """回合结束事件"""

    faction: Faction


@dataclass
class BattleEvent(Event):
    """战斗事件"""

    attacker_entity: int
    target_entity: int
    damage: int


@dataclass
class UnitDeathEvent(Event):
    """单位死亡事件"""

    entity: int
    faction: Faction


@dataclass
class UnitMoveEvent(Event):
    """单位移动事件"""

    entity: int
    from_pos: Tuple[int, int]
    to_pos: Tuple[int, int]


@dataclass
class UnitSelectedEvent(Event):
    """单位选中事件"""

    entity: int


@dataclass
class TileClickedEvent(Event):
    """地块点击事件"""

    position: Tuple[int, int]
    mouse_button: int


@dataclass
class GameOverEvent(Event):
    """游戏结束事件"""

    winner: Optional[Faction]


@dataclass
class TerrainEffectEvent(Event):
    """地形效果事件"""

    entity: int
    terrain_type: str
    effect_type: str
    value: float
