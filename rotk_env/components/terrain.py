"""
地形相关组件
"""

from dataclasses import dataclass
from typing import Tuple, Optional
from framework import Component
from ..prefabs.config import TerrainType, Faction


@dataclass
class Terrain(Component):
    """地形组件"""

    terrain_type: TerrainType
    movement_cost: int = 1
    defense_bonus: int = 0
    attack_bonus: int = 0
    vision_bonus: int = 0
    blocks_line_of_sight: bool = False


@dataclass
class TerrainModifier(Component):
    """地形修正器组件"""

    attack_modifier: float = 1.0
    defense_modifier: float = 1.0
    movement_modifier: float = 1.0
    vision_modifier: float = 1.0


@dataclass
class Tile(Component):
    """地块组件"""

    position: Tuple[int, int]  # 地块坐标
    occupied_by: Optional[int] = None  # 占据此地块的单位实体ID


@dataclass
class TerritoryControl(Component):
    """领土控制组件"""

    # 控制该地块的阵营
    controlling_faction: Optional[Faction] = None

    # 是否正在占领中
    being_captured: bool = False

    # 正在占领的单位
    capturing_unit: Optional[int] = None

    # 占领进度 (0.0-1.0)
    capture_progress: float = 0.0

    # 占领所需时间（秒）
    capture_time_required: float = 5.0

    # 是否已建立工事
    fortified: bool = False

    # 工事等级（影响防御加成）
    fortification_level: int = 0

    # 占领时间戳
    captured_time: float = 0.0

    # 是否为城市（占领代价更高，收益更高）
    is_city: bool = False


@dataclass
class CaptureAction(Component):
    """占领行动组件"""

    # 执行占领的单位
    capturing_unit: int

    # 目标地块位置
    target_position: Tuple[int, int]

    # 占领开始时间
    start_time: float = 0.0

    # 是否在回合制模式下使用行动力
    uses_action_points: bool = True

    # 所需行动力
    action_points_cost: int = 1

    # 是否已完成
    completed: bool = False
