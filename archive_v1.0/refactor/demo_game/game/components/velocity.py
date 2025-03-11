from dataclasses import dataclass
from framework.core.ecs.component import Component


@dataclass
class Velocity(Component):
    """速度组件"""

    x: float = 0.0
    y: float = 0.0
