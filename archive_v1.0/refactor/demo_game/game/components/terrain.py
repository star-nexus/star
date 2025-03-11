from dataclasses import dataclass
from framework.core.ecs.component import Component
from typing import Dict
from .terrain_type import TerrainType


@dataclass
class Terrain(Component):
    """地形组件，描述一个格子的地形类型及其属性"""

    type: TerrainType = TerrainType.PLAIN
    # 地形对单位属性的影响，使用字典存储修改值
    effects: Dict[str, float] = None
    # 是否可以在此地形上建造建筑
    buildable: bool = True
    # 是否可以通过此地形
    passable: bool = True

    def __post_init__(self):
        if self.effects is None:
            self.effects = {}

        # 根据地形类型设置默认属性
        if self.type == TerrainType.PLAIN:
            self.effects = {"movement_speed": 1.0, "attack": 1.0, "defense": 1.0}
            self.buildable = True
            self.passable = True
        elif self.type == TerrainType.MOUNTAIN:
            self.effects = {"movement_speed": 0.5, "attack": 0.8, "defense": 1.5}
            self.buildable = False
            self.passable = True
        elif self.type == TerrainType.RIVER:
            self.effects = {"movement_speed": 0.7, "attack": 0.9, "defense": 0.8}
            self.buildable = False
            self.passable = True
        elif self.type == TerrainType.FOREST:
            self.effects = {"movement_speed": 0.8, "attack": 1.1, "defense": 1.2}
            self.buildable = True
            self.passable = True
        elif self.type == TerrainType.LAKE:
            self.effects = {"movement_speed": 0.3, "attack": 0.7, "defense": 0.6}
            self.buildable = False
            self.passable = False
