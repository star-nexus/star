from dataclasses import dataclass
from framework.ecs.component import Component
from game.utils import TerrainType


@dataclass
class TileComponent(Component):
    """地图格子组件，存储格子的地形、高度、水系和资源等信息"""

    # 基本属性
    terrain_type: TerrainType = TerrainType.PLAIN  # 主要地形类型
    elevation: int = 0  # 海拔高度值（用于等高线）
    moisture: float = 0.5  # 湿度值（0.0-1.0）

    # 游戏属性
    movement_cost: float = 1.0  # 移动成本
    defense_bonus: float = 0.0  # 防御加成

    # 特殊属性
    has_road: bool = False  # 是否有道路
    has_river: bool = False  # 是否有河流
    has_bridge: bool = False  # 是否有桥

    # 位置属性
    x: int = 0  # 格子的x坐标
    y: int = 0  # 格子的y坐标

    # 状态属性
    visible: bool = True  # 是否可见
    explored: bool = False  # 是否被探索过

    # 资源属性
    resources: list = None  # 资源列表（如果有的话）
