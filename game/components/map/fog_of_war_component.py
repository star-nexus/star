from dataclasses import dataclass, field
import numpy as np
from typing import Dict
from framework.ecs.component import Component
from game.utils.game_types import ViewMode


@dataclass
class FogOfWarComponent(Component):
    """战争迷雾组件，存储战争迷雾的状态数据

    功能：
    1. 存储每个玩家的可见性地图和已探索地图
    2. 存储战争迷雾开关状态和视图模式
    3. 存储单位视野范围信息
    """

    # 迷雾状态
    visibility_map: Dict[int, np.ndarray] = field(
        default_factory=dict
    )  # 玩家ID -> 可见性地图的字典
    explored_map: Dict[int, np.ndarray] = field(
        default_factory=dict
    )  # 玩家ID -> 已探索地图的字典

    view_mode: ViewMode = ViewMode.PLAYER  # 视图模式：GLOBAL（全局）或PLAYER（玩家）
    current_player_id: int = 0  # 当前玩家ID

    # 单位视野范围（根据单位类型）
    unit_vision_range: Dict[str, int] = field(
        default_factory=lambda: {
            "INFANTRY": 3,
            "CAVALRY": 4,
            "ARCHER": 5,
            "SIEGE": 2,
            "HERO": 6,
        }
    )
