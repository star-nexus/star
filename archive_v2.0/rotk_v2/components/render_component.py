from dataclasses import dataclass
from framework_v2.ecs.component import Component
from typing import Tuple

@dataclass
class RenderComponent(Component):
    """实体渲染组件"""
    color: Tuple[int, int, int] = (255, 255, 255)
    width: int = 32
    height: int = 32
    layer: int = 0
    visible: bool = True
    image: str = None  # 图像路径或Surface对象