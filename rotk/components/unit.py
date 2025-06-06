"""
单位相关组件
"""

from dataclasses import dataclass, field
from typing import Set, Optional
from framework_v2 import Component
from ..prefabs.config import UnitType, Faction


@dataclass
class Unit(Component):
    """单位组件"""

    unit_type: UnitType
    faction: Faction
    name: str = ""
    level: int = 1
    experience: int = 0


@dataclass
class Movement(Component):
    """移动组件"""

    max_movement: int
    current_movement: int
    has_moved: bool = False


@dataclass
class Combat(Component):
    """战斗组件"""

    attack: int
    defense: int
    attack_range: int = 1
    has_attacked: bool = False


@dataclass
class Vision(Component):
    """视野组件"""

    range: int
    visible_tiles: Set[tuple] = field(default_factory=set)


@dataclass
class Selected(Component):
    """选中状态组件"""

    selected: bool = True


@dataclass
class AIControlled(Component):
    """AI控制组件"""

    difficulty: str = "normal"
    last_action_time: float = 0.0
