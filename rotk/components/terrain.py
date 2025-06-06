"""
地形相关组件
"""

from dataclasses import dataclass
from typing import Tuple, Optional
from framework_v2 import Component
from ..prefabs.config import TerrainType


@dataclass
class Terrain(Component):
    """地形组件"""

    terrain_type: TerrainType
    movement_cost: int = 1
    defense_bonus: int = 0
    attack_bonus: int = 0
    vision_bonus: int = 0
    blocks_line_of_sight: bool = False


@dataclass
class TerrainModifier(Component):
    """地形修正器组件"""

    attack_modifier: float = 1.0
    defense_modifier: float = 1.0
    movement_modifier: float = 1.0
    vision_modifier: float = 1.0


@dataclass
class Tile(Component):
    """地块组件"""

    position: Tuple[int, int]  # 地块坐标
    occupied_by: Optional[int] = None  # 占据此地块的单位实体ID
