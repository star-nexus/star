from dataclasses import dataclass
from framework.core.ecs.component import Component


@dataclass
class Player(Component):
    """玩家组件，标记实体为玩家"""

    speed: float = 200.0  # 玩家移动速度
