"""
移动动画相关组件
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Optional
from framework import Component


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

    # 防御状态
    is_defending: bool = False

    # 驻防状态
    is_fortified: bool = False

    # 移动状态
    is_moving: bool = False

    # 巡逻状态
    is_patrolling: bool = False

    # 侦察状态
    is_scouting: bool = False


@dataclass
class DamageNumber(Component):
    """伤害数字显示组件"""

    # 显示文本（可以是数字或特殊文本）
    text: str = "0"

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
    font_size: int = 24


@dataclass
class AttackAnimation(Component):
    """攻击动画组件"""

    # 目标位置（hex坐标）
    target_position: Tuple[int, int] = (0, 0)

    # 动画进度 (0.0-1.0)
    progress: float = 0.0

    # 动画速度
    speed: float = 8.0  # 攻击动画较快

    # 是否正在播放攻击动画
    is_attacking: bool = False

    # 攻击类型
    attack_type: str = "melee"  # melee, ranged, magic

    # 动画阶段：prepare, aim, strike/shoot, return
    phase: str = "prepare"

    # 起始位置（世界像素坐标）
    start_pixel_pos: Optional[Tuple[float, float]] = None

    # 目标位置（世界像素坐标）
    target_pixel_pos: Optional[Tuple[float, float]] = None

    # 当前渲染位置
    current_render_pos: Optional[Tuple[float, float]] = None

    # 动画持续时间
    total_duration: float = 0.8  # 总持续时间0.8秒

    # 各阶段持续时间比例
    prepare_ratio: float = 0.2  # 准备阶段20%
    aim_ratio: float = 0.2  # 瞄准阶段20%（显示指示线）
    strike_ratio: float = 0.4  # 打击/射击阶段40%
    return_ratio: float = 0.2  # 返回阶段20%

    # 攻击指示线相关
    show_aim_line: bool = False  # 是否显示瞄准线
    aim_line_alpha: float = 0.0  # 瞄准线透明度
    aim_line_color: Tuple[int, int, int] = (255, 255, 0)  # 瞄准线颜色

    # 远程攻击投射物
    projectile_pos: Optional[Tuple[float, float]] = None  # 投射物位置
    projectile_progress: float = 0.0  # 投射物飞行进度


@dataclass
class ProjectileAnimation(Component):
    """投射物动画组件（用于远程攻击）"""

    # 起始位置（世界像素坐标）
    start_pos: Tuple[float, float] = (0, 0)

    # 目标位置（世界像素坐标）
    target_pos: Tuple[float, float] = (0, 0)

    # 当前位置
    current_pos: Tuple[float, float] = (0, 0)

    # 飞行进度 (0.0-1.0)
    flight_progress: float = 0.0

    # 飞行速度
    flight_speed: float = 800.0  # 像素/秒

    # 是否正在飞行
    is_flying: bool = False

    # 投射物类型
    projectile_type: str = "arrow"  # arrow, bolt, stone, magic

    # 弧度高度（模拟抛物线）
    arc_height: float = 50.0

    # 投射物大小
    size: float = 1.0

    # 投射物颜色
    color: Tuple[int, int, int] = (139, 69, 19)  # 棕色箭矢

    # 旋转角度（根据飞行方向）
    rotation: float = 0.0


@dataclass
class EffectAnimation(Component):
    """特效动画组件"""

    # 特效类型
    effect_type: str = "none"  # slash, impact, explosion, heal, buff, debuff

    # 动画进度 (0.0-1.0)
    progress: float = 0.0

    # 动画速度
    speed: float = 6.0

    # 是否正在播放
    is_playing: bool = False

    # 特效位置（世界像素坐标）
    effect_position: Tuple[float, float] = (0, 0)

    # 特效大小
    effect_size: float = 1.0

    # 特效颜色
    effect_color: Tuple[int, int, int] = (255, 255, 255)

    # 持续时间
    duration: float = 0.5

    # 已播放时间
    elapsed_time: float = 0.0
