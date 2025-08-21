"""
游戏状态相关组件（单例组件）
"""

from dataclasses import dataclass, field
from typing import Dict, Set, Tuple, Optional, List
from framework import SingletonComponent
from ..prefabs.config import Faction, GameMode


@dataclass
class GameState(SingletonComponent):
    """游戏状态单例组件"""

    current_player: Faction
    turn_number: int = 1
    game_mode: GameMode = GameMode.TURN_BASED
    game_over: bool = False
    paused: bool = False
    winner: Optional[Faction] = None
    max_turns: int = 50


@dataclass
class MapData(SingletonComponent):
    """地图数据单例组件"""

    width: int
    height: int
    tiles: Dict[Tuple[int, int], int] = field(
        default_factory=dict
    )  # 坐标到地块实体ID的映射


@dataclass
class UIState(SingletonComponent):
    """UI状态单例组件"""

    selected_unit: Optional[int] = None
    hovered_tile: Optional[Tuple[int, int]] = None
    show_grid: bool = True
    show_stats: bool = False
    show_help: bool = False
    show_coordinates: bool = False  # 显示坐标
    camera_position: Tuple[float, float] = (0.0, 0.0)
    zoom_level: float = 1.0
    # 视角相关
    god_mode: bool = False  # 上帝视角（无战争迷雾）
    view_faction: Optional[Faction] = None  # 当前查看的阵营视角


@dataclass
class InputState(SingletonComponent):
    """输入状态单例组件"""

    mouse_pos: Tuple[int, int] = (0, 0)
    mouse_hex_pos: Optional[Tuple[int, int]] = None
    keys_pressed: Set[int] = field(default_factory=set)
    mouse_pressed: Set[int] = field(default_factory=set)


@dataclass
class FogOfWar(SingletonComponent):
    """战争迷雾单例组件"""

    faction_vision: Dict[Faction, Set[Tuple[int, int]]] = field(default_factory=dict)
    explored_tiles: Dict[Faction, Set[Tuple[int, int]]] = field(default_factory=dict)


@dataclass
class GameStats(SingletonComponent):
    """游戏统计单例组件 - 纯数据存储"""

    # 阵营统计
    faction_stats: Dict[Faction, Dict[str, int]] = field(default_factory=dict)

    # 战斗历史
    battle_history: List[Dict] = field(default_factory=list)

    # 回合历史
    turn_history: List[Dict] = field(default_factory=list)

    # 单位观测数据历史
    unit_observation_history: List[Dict] = field(default_factory=list)

    # 游戏模式特定统计
    game_mode_stats: Dict[str, any] = field(default_factory=dict)

    # 游戏开始时间
    game_start_time: float = 0.0

    # 当前游戏时间（实时模式用）
    total_game_time: float = 0.0
    
    # 🆕 添加初始单位数记录
    initial_unit_counts: Dict[Faction, int] = field(default_factory=dict)

    # 🆕 交互统计：ENV <-> Agent 的交互次数
    # 按 Agent 统计（agent_id -> count）
    response_times_by_agent: Dict[str, int] = field(default_factory=dict)
    # 按阵营统计（Faction -> count）
    response_times_by_faction: Dict[Faction, int] = field(default_factory=dict)
    # 🆕 记录agent与阵营的映射（用于按阵营汇总）
    agent_id_to_faction: Dict[str, Faction] = field(default_factory=dict)

    # 🆕 策略评分统计
    strategy_scores_by_faction: Dict[Faction, float] = field(default_factory=dict)
    strategy_ping_count_by_faction: Dict[Faction, int] = field(default_factory=dict)
    strategy_evidence: Dict[Faction, List[str]] = field(default_factory=dict)
    last_strategy_ping_ts: Dict[Faction, float] = field(default_factory=dict)