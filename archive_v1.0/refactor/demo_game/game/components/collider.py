from dataclasses import dataclass
from framework.core.ecs.component import Component


@dataclass
class Collider(Component):
    """碰撞组件"""

    radius: float = 20.0  # 使用圆形碰撞盒
    is_glowing: bool = False  # 是否发光
    glow_timer: float = 0.0  # 发光计时器
