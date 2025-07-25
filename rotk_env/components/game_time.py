"""
游戏时间系统组件
提供统一的游戏时间管理，支持回合制和实时模式
"""

from dataclasses import dataclass, field
from typing import Optional
import time
from framework import SingletonComponent
from ..prefabs.config import GameMode


@dataclass
class GameTime(SingletonComponent):
    """游戏时间统一管理组件"""

    # 游戏开始时间（真实时间戳）
    game_start_time: float = field(default_factory=time.time)

    # 当前游戏模式
    current_mode: GameMode = GameMode.TURN_BASED

    # 回合制相关
    current_turn: int = 1
    turn_start_time: float = field(default_factory=time.time)

    # 实时模式相关
    game_elapsed_time: float = 0.0  # 游戏内经过的时间（秒）
    time_scale: float = 1.0  # 时间倍率（可用于加速/减速）
    paused: bool = False  # 是否暂停
    last_update_time: float = field(default_factory=time.time)

    def initialize(self, mode: GameMode):
        """初始化游戏时间系统"""
        current_time = time.time()
        self.game_start_time = current_time
        self.current_mode = mode
        self.turn_start_time = current_time
        self.last_update_time = current_time
        self.game_elapsed_time = 0.0
        self.current_turn = 1
        self.paused = False

    def update(self, delta_time: float):
        """更新游戏时间（由时间系统调用）"""
        if not self.paused and self.current_mode == GameMode.REAL_TIME:
            # 只在实时模式下累积时间
            self.game_elapsed_time += delta_time * self.time_scale

        self.last_update_time = time.time()

    def advance_turn(self):
        """推进到下一回合（回合制模式）"""
        if self.current_mode == GameMode.TURN_BASED:
            self.current_turn += 1
            self.turn_start_time = time.time()

    def get_current_time_display(self) -> str:
        """获取当前时间的显示字符串"""
        if self.current_mode == GameMode.TURN_BASED:
            return f"T{self.current_turn}"
        else:
            # 实时模式：显示游戏内时间
            total_seconds = int(self.game_elapsed_time)
            if total_seconds < 3600:  # 小于1小时
                minutes = total_seconds // 60
                seconds = total_seconds % 60
                return f"{minutes:02d}:{seconds:02d}"
            else:  # 超过1小时
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                return f"{hours}h{minutes:02d}m"

    def get_turn_number(self) -> Optional[int]:
        """获取当前回合数（仅回合制模式有效）"""
        if self.current_mode == GameMode.TURN_BASED:
            return self.current_turn
        return None

    def get_game_elapsed_seconds(self) -> float:
        """获取游戏经过的总秒数"""
        if self.current_mode == GameMode.REAL_TIME:
            return self.game_elapsed_time
        else:
            # 回合制模式：返回真实经过的时间
            return time.time() - self.game_start_time

    def pause(self):
        """暂停游戏时间"""
        self.paused = True

    def resume(self):
        """恢复游戏时间"""
        self.paused = False
        self.last_update_time = time.time()

    def set_time_scale(self, scale: float):
        """设置时间倍率（仅实时模式）"""
        if scale > 0:
            self.time_scale = scale

    def is_turn_based(self) -> bool:
        """是否为回合制模式"""
        return self.current_mode == GameMode.TURN_BASED

    def is_real_time(self) -> bool:
        """是否为实时模式"""
        return self.current_mode == GameMode.REAL_TIME

    def get_formatted_time_since_start(self) -> str:
        """获取自游戏开始以来的格式化时间"""
        elapsed = time.time() - self.game_start_time
        if elapsed < 60:
            return f"{int(elapsed)}s"
        elif elapsed < 3600:
            return f"{int(elapsed//60)}m{int(elapsed%60)}s"
        else:
            hours = int(elapsed // 3600)
            minutes = int((elapsed % 3600) // 60)
            return f"{hours}h{minutes}m"
