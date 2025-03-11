# 导出所有系统类，以保持与现有代码的兼容性
from .faction_system import FactionSystem
from .resource_system import ResourceSystem
from .unit_system import UnitSystem
from .building_system import BuildingSystem
from .combat_system import CombatSystem
from .unit_control_system import UnitControlSystem

# 为了向后兼容
__all__ = [
    "FactionSystem",
    "ResourceSystem",
    "UnitSystem",
    "BuildingSystem",
    "CombatSystem",
    "UnitControlSystem",
]
