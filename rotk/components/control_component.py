from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple, Optional
from framework.core.ecs.component import Component
from dataclasses import dataclass


@dataclass
class HumanControlComponent(Component):
    """人类玩家控制组件，记录玩家控制的状态"""

    selected_faction_id: int = 2  # 当前选择的阵营ID (默认蜀国)
    selected_unit: Optional[int] = None  # 当前选中的单位实体ID
    selected_target: Optional[int] = None  # 当前目标单位实体ID
    move_target: Optional[Tuple[float, float]] = None  # 移动目标位置
    hover_unit: Optional[int] = None  # 当前鼠标悬停的单位
    selected_position: Optional[Tuple[float, float]] = None  # 当前选中的地图位置
    command_mode: str = "normal"  # 当前命令模式 (normal, attack, defend, patrol)
    selection_rect: Optional[Tuple[float, float, float, float]] = None  # 选择框


@dataclass
class AIControlComponent(Component):
    """AI控制组件，记录AI控制的状态"""

    faction_id: int  # 阵营ID
    difficulty: int = 1  # AI难度 (1-5)
    behavior_type: str = "balanced"  # AI行为类型 (aggressive, defensive, balanced, etc)
    target_faction_id: Optional[int] = None  # 当前主要目标阵营
    controlled_units: List[int] = field(default_factory=list)  # 控制的单位列表


@dataclass
class AgentControlComponent(Component):
    """控制代理组件，用于控制单位的行为"""

    pass
