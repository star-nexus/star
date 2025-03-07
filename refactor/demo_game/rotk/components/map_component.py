from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Tuple, Optional
from framework.core.ecs.component import Component


class TerrainType(Enum):
    """地形类型枚举"""

    PLAINS = "plains"  # 平原
    FOREST = "forest"  # 森林
    MOUNTAIN = "mountain"  # 山地
    HILL = "hill"  # 丘陵
    RIVER = "river"  # 河流
    LAKE = "lake"  # 湖泊
    BRIDGE = "bridge"  # 桥梁
    PLATEAU = "plateau"  # 高原
    BASIN = "basin"  # 盆地
    SWAMP = "swamp"  # 湿地
    DESERT = "desert"  # 沙漠
    VALLEY = "valley"  # 山谷
    OCEAN = "ocean"  # 海洋
    COAST = "coast"  # 海岸
    CITY = "city"  # 城市


# 定义地形的移动消耗
# TERRAIN_MOVEMENT_COST = {
#     TerrainType.PLAINS: 1,
#     TerrainType.FOREST: 2,
#     TerrainType.MOUNTAIN: 3,
#     TerrainType.HILL: 2,
#     TerrainType.RIVER: 3,
#     TerrainType.LAKE: 5,
#     TerrainType.BRIDGE: 1,
#     TerrainType.PLATEAU: 2,
#     TerrainType.BASIN: 2,
#     TerrainType.SWAMP: 4,
#     TerrainType.DESERT: 3,
#     TerrainType.VALLEY: 2,
#     TerrainType.OCEAN: 10,
#     TerrainType.COAST: 2,
#     TerrainType.CITY: 1,
# }

# 定义地形的颜色 RGB
TERRAIN_COLORS = {
    TerrainType.PLAINS: (180, 230, 100),
    TerrainType.FOREST: (0, 130, 0),
    TerrainType.MOUNTAIN: (120, 100, 80),
    TerrainType.HILL: (140, 170, 80),
    TerrainType.RIVER: (30, 144, 255),
    TerrainType.LAKE: (0, 102, 204),
    TerrainType.BRIDGE: (150, 75, 0),
    TerrainType.PLATEAU: (210, 180, 140),
    TerrainType.BASIN: (200, 200, 180),
    TerrainType.SWAMP: (80, 125, 80),
    TerrainType.DESERT: (238, 214, 175),
    TerrainType.VALLEY: (160, 125, 100),
    TerrainType.OCEAN: (0, 0, 128),
    TerrainType.COAST: (210, 210, 255),
    TerrainType.CITY: (128, 128, 128),
}


@dataclass
class MapComponent(Component):
    """地图组件，存储地图数据"""

    width: int = 20
    height: int = 15
    cell_size: int = 32
    grid: List[List[TerrainType]] = field(default_factory=list)
    # entities_positions: Dict[int, Tuple[int, int]] = field(default_factory=dict)


@dataclass
class TerrainComponent(Component):
    """地形组件"""

    terrain_type: TerrainType
    movement_cost: int = 1


@dataclass
class PositionComponent(Component):
    """位置组件"""

    x: int = 0
    y: int = 0
    prev_x: int = 0  # 用于动画和平滑移动
    prev_y: int = 0


# @dataclass
# class MovableComponent(Component):
#     """可移动组件"""

#     speed: int = 1  # 每回合可移动的格子数
#     movement_points: int = 1  # 当前可用的移动点数


@dataclass
class ObstacleComponent(Component):
    """障碍物组件"""

    is_destructible: bool = False  # 是否可被破坏


# @dataclass
# class PlayerComponent(Component):
#     """玩家组件"""

#     name: str = "玩家"


# @dataclass
# class EnemyComponent(Component):
#     """敌人组件"""

#     name: str = "敌人"
#     aggression: int = 1  # 敌人侵略性，影响AI决策


@dataclass
class RenderableComponent(Component):
    """可渲染组件"""

    color: Tuple[int, int, int] = (255, 255, 255)
    symbol: str = "?"
    size: int = 20
