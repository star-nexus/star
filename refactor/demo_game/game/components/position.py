from dataclasses import dataclass
from framework.core.ecs.component import Component


@dataclass
class Position(Component):
    """位置组件"""

    x: float = 0.0
    y: float = 0.0
