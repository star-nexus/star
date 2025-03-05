from dataclasses import dataclass
from framework.core.ecs.component import Component
from typing import Dict, Any


@dataclass
class MapTile(Component):
    """地图格子组件，表示地图上的一个单元格"""

    x: int = 0  # 格子的X坐标（网格坐标，不是屏幕坐标）
    y: int = 0  # 格子的Y坐标
    # 格子高度，可用于表示海拔或视觉效果
    height: float = 0.0
    # 额外属性，如资源点、起始点等
    properties: Dict[str, Any] = None

    def __post_init__(self):
        if self.properties is None:
            self.properties = {}
