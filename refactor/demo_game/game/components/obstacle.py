from dataclasses import dataclass
from framework.core.ecs.component import Component


@dataclass
class Obstacle(Component):
    """障碍物组件，标记实体为障碍物"""

    pass
