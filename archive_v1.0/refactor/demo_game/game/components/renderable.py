from dataclasses import dataclass
from framework.core.ecs.component import Component
from typing import Tuple


@dataclass
class Renderable(Component):
    """渲染组件"""

    color: Tuple[int, int, int] = (255, 255, 255)  # 默认白色
    radius: float = 20.0  # 渲染半径
