from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
import numpy as np
from framework.ecs.component import Component
from framework.ecs.entity import Entity
from game.utils.hex_utils import HexOrientation


@dataclass
class MapComponent(Component):
    """地图组件，存储整个地图的数据"""

    # 基本属性
    map_type: str = "hexagonal"  # 地图类型：hexagonal 或 square
    orientation: HexOrientation = (
        HexOrientation.POINTY_TOP
    )  # 六边形方向（仅用于六边形地图）
    width: int = 50  # 地图宽度
    height: int = 50  # 地图高度
    radius: int = 3  # 六边形地图半径（仅用于六边形地图）
    hex_size: float = 20.0  # 六边形大小（仅用于六边形地图）
    tile_size: int = 32  # 格子大小（像素）

    # 地图数据
    elevation_map: np.ndarray = field(
        default_factory=lambda: np.zeros((50, 50), dtype=np.int32)
    )
    terrain_map: np.ndarray = field(
        default_factory=lambda: np.zeros((50, 50), dtype=np.int32)
    )
    moisture_map: np.ndarray = field(
        default_factory=lambda: np.zeros((50, 50), dtype=np.float32)
    )

    # 实体映射
    tile_entities: Dict[Tuple[int, int], Entity] = field(
        default_factory=dict
    )  # 坐标 -> 格子实体的映射

    # 六边形地图专用：六边形坐标到实体的映射
    hex_entities: Dict[Tuple[int, int, int], Entity] = field(
        default_factory=dict
    )  # (q, r, s) -> 格子实体的映射
