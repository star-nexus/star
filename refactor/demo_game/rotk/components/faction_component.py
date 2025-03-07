from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple, Optional
from framework.core.ecs.component import Component
from .unit_enums import (
    UnitType,
    UnitCategory,
    UnitState,
    TerrainAdaptability,
    SupplyStatus,
)
from .map_component import TerrainType


@dataclass
class FactionComponent(Component):
    """阵营组件，定义单位所属的阵营"""

    faction_id: int  # 阵营唯一ID
    name: str  # 阵营名称
    color: Tuple[int, int, int]  # 阵营颜色 (RGB)
    active: bool = True  # 阵营是否激活
    city_count: int = 0  # 控制的城市数量
    unit_count: int = 0  # 拥有的单位数量
    # diplomacy: Dict[int, int] = field(
    #     default_factory=dict
    # )  # 与其他阵营的外交关系 {faction_id: relation_value}


# @dataclass
# class UnitStatsComponent(Component):
#     """单位基本属性组件"""

#     name: str  # 单位名称
#     unit_type: UnitType  # 单位类型
#     category: UnitCategory  # 单位类别(步兵、骑兵等)
#     faction_id: int  # 所属阵营ID

#     # 基本属性
#     health: float = 100.0  # 当前血量
#     max_health: float = 100.0  # 最大血量
#     attack: float = 10.0  # 攻击力
#     defense: float = 5.0  # 防御力
#     morale: float = 70.0  # 士气(0-100)
#     experience: float = 0.0  # 经验值
#     level: int = 1  # 等级

#     # 高级属性
#     leadership: float = 0.0  # 统率力
#     intelligence: float = 0.0  # 智力
#     politics: float = 0.0  # 政治
#     charm: float = 0.0  # 魅力


# @dataclass
# class UnitMovementComponent(Component):
#     """单位移动组件，处理连续移动"""

#     base_speed: float = 5.0  # 基础速度(米/秒)
#     current_speed: float = 5.0  # 当前实际速度(米/秒)
#     max_speed: float = 10.0  # 最大速度(米/秒)
#     path: List[Tuple[float, float]] = field(default_factory=list)  # 移动路径
#     destination: Optional[Tuple[float, float]] = None  # 目标位置
#     is_moving: bool = False  # 是否在移动
#     terrain_adaptability: Dict[TerrainType, TerrainAdaptability] = field(
#         default_factory=dict
#     )  # 地形适应性
#     fatigue: float = 0.0  # 疲劳值 (0-100)
#     attack_range: float = 1.0  # 攻击范围(格子)


# @dataclass
# class UnitSupplyComponent(Component):
#     """单位补给组件，管理单位的补给状态"""

#     food_supply: float = 100.0  # 粮草补给，满值100
#     ammo_supply: float = 100.0  # 弹药补给，满值100
#     food_consumption_rate: float = 0.5  # 每分钟消耗粮食率
#     ammo_consumption_rate: float = 0.0  # 每次攻击消耗弹药率
#     days_without_supply: int = 0  # 无补给天数
#     supply_status: SupplyStatus = SupplyStatus.FULL  # 当前补给状态
#     supply_efficiency: float = 1.0  # 补给效率，小于1时表示补给不足


# @dataclass
# class UnitStateComponent(Component):
#     """单位状态组件"""

#     state: UnitState = UnitState.IDLE  # 当前状态
#     target_entity: Optional[int] = None  # 目标实体
#     target_position: Optional[Tuple[float, float]] = None  # 目标位置
#     formation: str = "standard"  # 阵型
#     is_routed: bool = False  # 是否溃逃
#     is_engaged: bool = False  # 是否交战中
#     commander_entity: Optional[int] = None  # 指挥官实体ID


# @dataclass
# class PrecisePositionComponent(Component):
#     """精确位置组件，支持格子内连续移动"""

#     grid_x: int = 0  # 格子X坐标
#     grid_y: int = 0  # 格子Y坐标
#     offset_x: float = 0.5  # 格子内X偏移(0-1)
#     offset_y: float = 0.5  # 格子内Y偏移(0-1)
#     direction: float = 0.0  # 朝向角度(弧度)
#     prev_grid_x: int = 0  # 上一格子X坐标
#     prev_grid_y: int = 0  # 上一格子Y坐标

#     @property
#     def world_x(self) -> float:
#         """获取精确的X世界坐标"""
#         return self.grid_x + self.offset_x

#     @property
#     def world_y(self) -> float:
#         """获取精确的Y世界坐标"""
#         return self.grid_y + self.offset_y


# @dataclass
# class UnitRenderComponent(Component):
#     """单位渲染组件"""

#     main_color: Tuple[int, int, int]  # 主要颜色(通常是阵营颜色)
#     accent_color: Tuple[int, int, int]  # 点缀颜色
#     symbol: str  # 单位标志
#     size: int  # 渲染大小
#     banner: str = ""  # 旗帜图像名称
#     animation_state: str = "idle"  # 动画状态
#     visibility: float = 1.0  # 可见度(0.0-1.0)
