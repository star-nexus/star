"""
组件模块

包含游戏中使用的所有组件定义。
"""

# 导入所有组件
from .unit_component import *
from .map_component import *
from .faction_component import *
from .control_component import *
from .unique_component import *
from .misc_components import *
from .unit_enums import *
# from .map_component_extended import VisibilityComponent



# 导出所有组件名称
__all__ = [
    # 单位组件
    'UnitStatsComponent',
    'UnitPositionComponent',
    'UnitMovementComponent',
    'UnitStateComponent',
    'UnitSupplyComponent',

    # 地图组件
    'MapComponent',
    'TerrainComponent',
    'VisibilityComponent',

    # 派系组件
    'FactionComponent',
    'FactionRelationComponent',
    'FactionResourceComponent',
    'FactionTerritoryComponent',

    # 控制组件
    'AIControlComponent',
    'HumanControlComponent',
    'BehaviorComponent',
    
    # 唯一组件
    'UniqueComponent',

    # 杂项组件
    'RenderComponent',
    'TimerComponent',
    
    # 枚举类型
    'UnitType',
    'UnitCategory',
    'UnitState',
    'TerrainType',
    'TerrainAdaptability',
    'FactionType',
]

from .map_component import (
    MapComponent,
    TerrainComponent,
    PositionComponent,
    # MovableComponent,
    ObstacleComponent,
    # PlayerComponent,
    # EnemyComponent,
    RenderableComponent,
    TerrainType,
    # TERRAIN_MOVEMENT_COST,
    TERRAIN_COLORS,
)

from .unit_enums import (
    UnitType,
    UnitCategory,
    UnitState,
    TerrainAdaptability,
    SupplyStatus,
)

from .faction_component import FactionComponent
from .unit_component import (
    UnitStatsComponent,
    UnitMovementComponent,
    UnitSupplyComponent,
    UnitStateComponent,
    UnitPositionComponent,
    UnitRenderComponent,
)
from .unique_component import UniqueComponent
from .control_component import (
    HumanControlComponent,
    AgentControlComponent,
    AIControlComponent,
)
