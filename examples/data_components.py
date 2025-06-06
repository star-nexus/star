"""
常用组件定义
"""

from dataclasses import dataclass
from typing import Optional
from ..framework_v2.ecs.core import Component


@dataclass
class Position(Component):
    """位置组件"""

    x: float = 0.0
    y: float = 0.0
    z: float = 0.0


@dataclass
class Velocity(Component):
    """速度组件"""

    x: float = 0.0
    y: float = 0.0
    z: float = 0.0


@dataclass
class Health(Component):
    """生命值组件"""

    current: float = 100.0
    max: float = 100.0

    @property
    def is_alive(self) -> bool:
        return self.current > 0

    @property
    def health_percentage(self) -> float:
        return self.current / self.max if self.max > 0 else 0.0


@dataclass
class Name(Component):
    """名称组件"""

    value: str = ""


@dataclass
class Renderable(Component):
    """渲染组件"""

    sprite: Optional[str] = None
    visible: bool = True
    layer: int = 0


@dataclass
class Transform(Component):
    """变换组件"""

    position: tuple = (0.0, 0.0, 0.0)
    rotation: tuple = (0.0, 0.0, 0.0)
    scale: tuple = (1.0, 1.0, 1.0)


@dataclass
class Collider(Component):
    """碰撞体组件"""

    width: float = 1.0
    height: float = 1.0
    is_trigger: bool = False
