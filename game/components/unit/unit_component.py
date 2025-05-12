from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
from enum import Enum, auto
from framework.ecs.component import Component
from game.utils.game_types import UnitType, UnitState


@dataclass
class UnitComponent(Component):
    """单位组件，存储单位的基本属性和状态

    按照ECS设计原则，组件只存储数据，不包含逻辑
    所有逻辑功能已移至UnitSystem中实现
    """

    # 基本属性
    name: str = "未命名单位"  # 单位名称
    unit_type: UnitType = UnitType.INFANTRY  # 单位类型
    level: int = 1  # 单位等级
    faction: int = 0  # 单位阵营

    # 位置信息
    position_x: float = 0.0  # 地图X坐标（米，支持连续坐标）
    position_y: float = 0.0  # 地图Y坐标（米，支持连续坐标）
    unit_size: float = 1.0  # 单位实际尺寸（米）

    # 战斗属性
    max_health: int = 100  # 最大生命值
    current_health: int = 100  # 当前生命值
    attack: int = 10  # 攻击力
    defense: int = 5  # 防御力
    range: int = 1  # 攻击范围

    # 移动属性
    base_speed: float = 2  # 基础移动速度
    movement: int = 5  # 移动力
    movement_left: int = 5  # 剩余移动力

    # 状态
    state: UnitState = UnitState.IDLE  # 当前状态
    is_selected: bool = False  # 是否被选中
    is_alive: bool = True  # 是否存活

    # 其他属性
    owner_id: int = 0  # 所属玩家ID
    abilities: List[str] = field(default_factory=list)  # 特殊能力列表
