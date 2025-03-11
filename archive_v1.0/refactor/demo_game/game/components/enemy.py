from dataclasses import dataclass
from framework.core.ecs.component import Component


@dataclass
class Enemy(Component):
    """敌人组件，标记实体为敌人"""

    speed: float = 150.0  # 敌人移动速度
    state: str = "idle"
