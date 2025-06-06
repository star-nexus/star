"""
围棋游戏组件定义
"""

from dataclasses import dataclass, field
from typing import Optional, List, Tuple, Dict
import time
from enum import Enum

from framework_v2 import Component, SingletonComponent


class StoneColor(Enum):
    BLACK = 1
    WHITE = 2
    EMPTY = 0


@dataclass
class Position(Component):
    """位置组件 - 表示棋盘上的位置"""

    x: int
    y: int


@dataclass
class Stone(Component):
    """棋子组件"""

    color: StoneColor
    capture_time: Optional[float] = None  # 被吃掉的时间


@dataclass
class BoardPosition(Component):
    """棋盘位置组件 - 棋盘上某个点的状态"""

    x: int
    y: int
    stone_color: StoneColor = StoneColor.EMPTY
    group_id: Optional[int] = None  # 所属棋群ID


@dataclass
class Selectable(Component):
    """可选择组件"""

    selected: bool = False
    hover: bool = False


@dataclass
class Clickable(Component):
    """可点击组件"""

    enabled: bool = True
    on_click: Optional[callable] = None


@dataclass
class Renderable(Component):
    """可渲染组件"""

    visible: bool = True
    layer: int = 0  # 渲染层级


@dataclass
class UIElement(Component):
    """UI元素基础组件"""

    position: Tuple[int, int] = (0, 0)
    size: Tuple[int, int] = (100, 30)
    visible: bool = True
    layer: int = 10  # UI层级通常较高


@dataclass
class UIPanel(Component):
    """UI面板组件"""

    background_color: Tuple[int, int, int] = (50, 50, 50)
    border_color: Optional[Tuple[int, int, int]] = None
    border_width: int = 1


@dataclass
class UILabel(Component):
    """UI标签组件"""

    text: str = ""
    font_size: int = 24
    text_color: Tuple[int, int, int] = (255, 255, 255)
    background_color: Optional[Tuple[int, int, int]] = None


@dataclass
class UIButton(Component):
    """UI按钮组件"""

    text: str = "Button"
    font_size: int = 20
    text_color: Tuple[int, int, int] = (255, 255, 255)
    background_color: Tuple[int, int, int] = (70, 70, 70)
    hover_color: Tuple[int, int, int] = (100, 100, 100)
    pressed_color: Tuple[int, int, int] = (50, 50, 50)
    border_color: Optional[Tuple[int, int, int]] = (200, 200, 200)
    border_width: int = 2
    on_click: Optional[callable] = None
    is_hovered: bool = False
    is_pressed: bool = False


@dataclass
class BoardRenderer(Component):
    """棋盘渲染组件"""

    grid_size: int = 30
    start_x: int = 50
    start_y: int = 50
    line_color: Tuple[int, int, int] = (0, 0, 0)
    background_color: Tuple[int, int, int] = (139, 69, 19)


@dataclass
class StoneRenderer(Component):
    """棋子渲染组件"""

    radius: int = 12
    black_color: Tuple[int, int, int] = (0, 0, 0)
    white_color: Tuple[int, int, int] = (255, 255, 255)
    border_color: Tuple[int, int, int] = (50, 50, 50)


# 单例组件
@dataclass
class GameBoard(SingletonComponent):
    """游戏棋盘"""

    size: int = 19  # 19x19标准围棋
    board: List[List[StoneColor]] = field(
        default_factory=lambda: [
            [StoneColor.EMPTY for _ in range(19)] for _ in range(19)
        ]
    )
    groups: Dict[int, List[Tuple[int, int]]] = field(default_factory=dict)  # 棋群
    next_group_id: int = 1


@dataclass
class GameState(SingletonComponent):
    """游戏状态"""

    current_player: StoneColor = StoneColor.BLACK
    game_phase: str = "playing"  # playing, ended
    winner: Optional[StoneColor] = None
    move_count: int = 0
    pass_count: int = 0  # 连续pass次数
    game_start_time: float = field(default_factory=time.time)
    last_move_time: float = field(default_factory=time.time)


@dataclass
class GameStats(SingletonComponent):
    """游戏统计"""

    black_captures: int = 0  # 黑子吃掉的白子数
    white_captures: int = 0  # 白子吃掉的黑子数
    black_territory: int = 0  # 黑方势力范围
    white_territory: int = 0  # 白方势力范围
    black_stones: int = 0  # 黑子数量
    white_stones: int = 0  # 白子数量
    black_score: float = 0.0  # 黑方总分
    white_score: float = 0.0  # 白方总分
    black_win_rate: float = 0.5  # 黑方胜率
    white_win_rate: float = 0.5  # 白方胜率
    komi: float = 6.5  # 贴目
    game_duration: float = 0.0
    moves_history: List[Tuple[int, int, StoneColor]] = field(default_factory=list)


@dataclass
class AIPlayer(SingletonComponent):
    """AI玩家"""

    enabled: bool = True
    difficulty: str = "medium"  # easy, medium, hard
    thinking_time: float = 1.0  # AI思考时间
    last_move_time: float = 0.0
    is_thinking: bool = False


@dataclass
class UIState(SingletonComponent):
    """UI状态"""

    show_coordinates: bool = True
    show_captured: bool = True
    show_territory: bool = False
    selected_position: Optional[Tuple[int, int]] = None
    hover_position: Optional[Tuple[int, int]] = None


@dataclass
class MouseState(SingletonComponent):
    """鼠标状态"""

    x: int = 0
    y: int = 0
    clicked: bool = False
    board_x: int = -1  # 棋盘坐标
    board_y: int = -1


@dataclass
class GameResultDialog(SingletonComponent):
    """游戏结果对话框"""

    visible: bool = False
    winner: Optional[StoneColor] = None
    black_score: float = 0.0
    white_score: float = 0.0
    score_difference: float = 0.0
    game_duration: float = 0.0
    total_moves: int = 0


@dataclass
class DialogOverlay(Component):
    """对话框遮罩组件"""

    alpha: int = 150  # 透明度 (0-255)
    blur_radius: int = 5  # 高斯模糊半径
    background_color: Tuple[int, int, int] = (0, 0, 0)
