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
