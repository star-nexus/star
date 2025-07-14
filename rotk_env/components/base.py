"""
基础组件模块
"""

from dataclasses import dataclass
from typing import Tuple, Optional
from framework import Component


@dataclass
class HexPosition(Component):
    """六边形位置组件"""

    col: int
    row: int


@dataclass
class Health(Component):
    """生命值组件"""

    current: int
    maximum: int

    @property
    def percentage(self) -> float:
        """生命值百分比"""
        return self.current / self.maximum if self.maximum > 0 else 0.0

    def is_alive(self) -> bool:
        """是否存活"""
        return self.current > 0


@dataclass
class Renderable(Component):
    """可渲染组件"""

    color: Tuple[int, int, int]
    size: int = 20
    visible: bool = True


@dataclass
class AnimationState(Component):
    """动画状态组件"""

    animation_type: str = "idle"
    frame: int = 0
    duration: float = 0.0


@dataclass
class PathFinding(Component):
    """寻路组件"""

    target_position: Optional[Tuple[int, int]] = None
    path: list = None
    path_index: int = 0
