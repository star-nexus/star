"""
移动动画相关组件
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Optional
from framework_v2 import Component


@dataclass
class MovementAnimation(Component):
    """移动动画组件"""

    # 移动路径（hex坐标列表）
    path: List[Tuple[int, int]] = field(default_factory=list)

    # 当前目标索引
    current_target_index: int = 0

    # 移动进度 (0.0-1.0)
    progress: float = 0.0

    # 移动速度 (格子/秒)
    speed: float = 2.0

    # 是否正在移动
    is_moving: bool = False

    # 起始位置（世界像素坐标）
    start_pixel_pos: Optional[Tuple[float, float]] = None

    # 目标位置（世界像素坐标）
    target_pixel_pos: Optional[Tuple[float, float]] = None


@dataclass
class UnitStatus(Component):
    """单位状态组件"""

    # 当前状态
    current_status: str = "idle"  # idle, moving, combat, hidden, resting

    # 状态持续时间
    status_duration: float = 0.0

    # 状态变化时间戳
    status_change_time: float = 0.0


@dataclass
class DamageNumber(Component):
    """伤害数字显示组件"""

    # 伤害值
    damage: int = 0

    # 显示位置（屏幕坐标）
    position: Tuple[float, float] = (0, 0)

    # 生存时间
    lifetime: float = 2.0

    # 已存在时间
    elapsed_time: float = 0.0

    # 移动速度
    velocity: Tuple[float, float] = (0, -50)  # 向上移动

    # 颜色
    color: Tuple[int, int, int] = (255, 0, 0)  # 红色

    # 字体大小
    font_size: int = 20
