from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
import numpy as np
from framework.ecs.component import Component
from framework.ecs.entity import Entity


@dataclass
class MapComponent(Component):
    """地图组件，存储整个地图的数据"""

    width: int = 50  # 地图宽度
    height: int = 50  # 地图高度
    tile_size: int = 32  # 格子大小（像素）
    elevation_map: np.ndarray = field(
        default_factory=lambda: np.zeros((50, 50), dtype=np.int32)
    )
    terrain_map: np.ndarray = field(
        default_factory=lambda: np.zeros((50, 50), dtype=np.int32)
    )
    moisture_map: np.ndarray = field(
        default_factory=lambda: np.zeros((50, 50), dtype=np.float32)
    )
    tile_entities: Dict[Tuple[int, int], Entity] = field(
        default_factory=dict
    )  # 坐标 -> 格子实体的映射
