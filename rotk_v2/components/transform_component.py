from dataclasses import dataclass
from framework_v2.ecs.component import Component

@dataclass
class TransformComponent(Component):
    """实体变换组件"""
    x: float = 0.0
    y: float = 0.0
    scale: float = 1.0
    rotation: float = 0.0