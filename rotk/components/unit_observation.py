"""
单位观测和统计组件
Unit Observation and Statistics Components
"""

from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Tuple, Any
import time
from framework_v2 import Component, SingletonComponent
from ..prefabs.config import Faction, UnitType


@dataclass
class UnitObservation(Component):
    """单位观测组件 - 记录单位的可观测状态"""

    # 位置信息
    current_position: Tuple[int, int] = (0, 0)
    previous_position: Tuple[int, int] = (0, 0)

    # 健康状态
    health_percentage: float = 100.0

    # 行动状态
    movement_remaining: int = 0
    has_acted_this_turn: bool = False

    # 可见状态
    is_visible_to: Set[Faction] = field(default_factory=set)
    last_seen_time: float = field(default_factory=time.time)

    # 地形效果
    current_terrain_type: str = "plains"
    terrain_bonus_active: bool = False

    # 战斗状态
    in_combat: bool = False
    last_combat_time: float = 0.0

    # 移动轨迹
    movement_path: List[Tuple[int, int]] = field(default_factory=list)
    total_distance_moved: int = 0


@dataclass
class UnitStatistics(Component):
    """单位个体统计组件"""

    # 基础统计
    kills: int = 0
    deaths: int = 0
    damage_dealt: int = 0
    damage_taken: int = 0

    # 行动统计
    moves_made: int = 0
    attacks_made: int = 0
    turns_survived: int = 0

    # 战斗统计
    battles_participated: int = 0
    battles_won: int = 0
    battles_lost: int = 0

    # 地形统计
    terrain_types_visited: Set[str] = field(default_factory=set)
    terrain_bonuses_used: int = 0

    # 时间统计
    total_active_time: float = 0.0
    creation_time: float = field(default_factory=time.time)


@dataclass
class VisibilityTracker(SingletonComponent):
    """可见性追踪器 - 跟踪单位的可见状态 - 纯数据存储"""

    # 阵营可见单位映射
    faction_visible_units: Dict[Faction, Set[int]] = field(default_factory=dict)

    # 单位可见历史
    visibility_history: Dict[int, List[Dict]] = field(default_factory=dict)

    # 侦察统计
    reconnaissance_stats: Dict[Faction, Dict[str, int]] = field(default_factory=dict)


@dataclass
class GameModeStatistics(SingletonComponent):
    """游戏模式统计组件 - 纯数据存储"""

    # 回合制统计
    turn_based_stats: Dict[str, Any] = field(
        default_factory=lambda: {
            "total_turns": 0,
            "average_turn_duration": 0.0,
            "longest_turn": 0.0,
            "shortest_turn": float("inf"),
            "turn_durations": [],
            "faction_turn_times": {},
            "actions_per_turn": {},
        }
    )

    # 实时制统计
    realtime_stats: Dict[str, Any] = field(
        default_factory=lambda: {
            "total_game_time": 0.0,
            "actions_per_minute": 0.0,
            "peak_activity_time": 0.0,
            "action_frequency": [],
            "faction_activity": {},
            "concurrent_actions": 0,
        }
    )

    # 当前统计
    current_mode: str = "turn_based"
    current_turn_start_time: float = 0.0
    actions_this_turn: int = 0
    actions_this_minute: int = 0
    last_action_time: float = 0.0
