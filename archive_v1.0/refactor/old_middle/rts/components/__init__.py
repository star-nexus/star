# 导出所有组件类，以保持与现有代码的兼容性
from .faction import FactionComponent
from .resource import ResourceComponent
from .unit import UnitComponent
from .building import BuildingComponent
from .attack import AttackComponent
from .defense import DefenseComponent
from .movement import MovementComponent
from .resource_node import ResourceNodeComponent
from .position import PositionComponent
from .sprite import SpriteComponent

# 为了向后兼容
__all__ = [
    "FactionComponent",
    "ResourceComponent",
    "UnitComponent",
    "BuildingComponent",
    "AttackComponent",
    "DefenseComponent",
    "MovementComponent",
    "ResourceNodeComponent",
    "PositionComponent",
    "SpriteComponent",
]
