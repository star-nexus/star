"""
游戏状态相关组件（单例组件）
"""

from dataclasses import dataclass, field
from typing import Dict, Set, Tuple, Optional, List
from framework_v2 import SingletonComponent
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
    camera_position: Tuple[float, float] = (0.0, 0.0)
    zoom_level: float = 1.0


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
class Camera(SingletonComponent):
    """摄像机单例组件"""
    
    offset_x: float = 0.0  # 摄像机X偏移
    offset_y: float = 0.0  # 摄像机Y偏移
    zoom: float = 1.0      # 缩放级别
    speed: float = 200.0   # 移动速度(像素/秒)
    
    def get_offset(self) -> Tuple[float, float]:
        """获取摄像机偏移"""
        return (self.offset_x, self.offset_y)
    
    def set_offset(self, x: float, y: float) -> None:
        """设置摄像机偏移"""
        self.offset_x = x
        self.offset_y = y
    
    def move(self, dx: float, dy: float) -> None:
        """移动摄像机"""
        self.offset_x += dx
        self.offset_y += dy


@dataclass
class GameStats(SingletonComponent):
    """游戏统计单例组件"""

    faction_stats: Dict[Faction, Dict[str, int]] = field(default_factory=dict)
    battle_history: List[Dict] = field(default_factory=list)
    turn_history: List[Dict] = field(default_factory=list)
