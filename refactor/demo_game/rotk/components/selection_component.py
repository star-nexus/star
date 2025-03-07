from framework.core.ecs.component import Component
from dataclasses import dataclass


@dataclass
class SelectionComponent(Component):
    """选择组件，用于标记被选中的实体"""

    selectedEntitie: int = None
    selectedEntities: list = None
