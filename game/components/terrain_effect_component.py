from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any
from framework.ecs.component import Component
from framework.ecs.entity import Entity
from game.utils.game_types import TerrainType


@dataclass
class TerrainEffectComponent(Component):
    """地形效果组件，存储单位受到的地形效果

    用于跟踪单位当前所处地形及其受到的效果
    """

    # 当前所处地形类型
    current_terrain: TerrainType = TerrainType.PLAIN

    # 当前激活的效果ID列表
    active_effects: List[str] = field(default_factory=list)

    # 效果数据，用于存储各种效果的具体数值
    effect_data: Dict[str, Any] = field(default_factory=dict)

    # 占领的城市实体ID（如果有）
    occupied_city: Optional[Entity] = None

    # 占领时间（回合数）
    occupation_turns: int = 0
