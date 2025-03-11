from framework.core.ecs.component import Component
from dataclasses import dataclass


@dataclass
class UniqueComponent(Component):
    unique_id: str = None
