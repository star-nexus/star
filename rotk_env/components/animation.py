"""
Animation components (movement, combat, effects).
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Optional
from framework import Component


@dataclass
class MovementAnimation(Component):
    """Movement animation component."""

    # Movement path (hex coordinates)
    path: List[Tuple[int, int]] = field(default_factory=list)

    # Current target index
    current_target_index: int = 0

    # Progress (0.0-1.0)
    progress: float = 0.0

    # Speed (tiles/sec)
    speed: float = 2.0

    # Whether currently moving
    is_moving: bool = False

    # Start position (world pixel coordinates)
    start_pixel_pos: Optional[Tuple[float, float]] = None

    # Target position (world pixel coordinates)
    target_pixel_pos: Optional[Tuple[float, float]] = None


@dataclass
class UnitStatus(Component):
    """Unit visual/animation status component."""

    # Current status
    current_status: str = "idle"  # idle, moving, combat, hidden, resting

    # Status duration
    status_duration: float = 0.0

    # Status change timestamp
    status_change_time: float = 0.0

    # Defensive state
    is_defending: bool = False

    # Fortified state
    is_fortified: bool = False

    # Moving state
    is_moving: bool = False

    # Patrolling state
    is_patrolling: bool = False

    # Scouting state
    is_scouting: bool = False


@dataclass
class DamageNumber(Component):
    """Floating damage number component."""

    # Display text (numeric or special text)
    text: str = "0"

    # Display position (screen coordinates)
    position: Tuple[float, float] = (0, 0)

    # Lifetime
    lifetime: float = 2.0

    # Elapsed time
    elapsed_time: float = 0.0

    # Velocity
    velocity: Tuple[float, float] = (0, -50)  # Move upward

    # Color
    color: Tuple[int, int, int] = (255, 0, 0)  # Red

    # Font size
    font_size: int = 24


@dataclass
class AttackAnimation(Component):
    """Attack animation component."""

    # Target position (hex coordinates)
    target_position: Tuple[int, int] = (0, 0)

    # Progress (0.0-1.0)
    progress: float = 0.0

    # Speed
    speed: float = 8.0  # Attacks animate faster

    # Whether currently attacking
    is_attacking: bool = False

    # Attack type
    attack_type: str = "melee"  # melee, ranged, magic

    # Phase: prepare, aim, strike/shoot, return
    phase: str = "prepare"

    # Start position (world pixel coordinates)
    start_pixel_pos: Optional[Tuple[float, float]] = None

    # Target position (world pixel coordinates)
    target_pixel_pos: Optional[Tuple[float, float]] = None

    # Current render position
    current_render_pos: Optional[Tuple[float, float]] = None

    # Total duration
    total_duration: float = 0.8  # 0.8 seconds total

    # Phase ratios
    prepare_ratio: float = 0.2  # Prepare: 20%
    aim_ratio: float = 0.2  # Aim: 20% (shows aim line)
    strike_ratio: float = 0.4  # Strike/shoot: 40%
    return_ratio: float = 0.2  # Return: 20%

    # Aim line
    show_aim_line: bool = False  # Whether to show aim line
    aim_line_alpha: float = 0.0  # Aim line opacity
    aim_line_color: Tuple[int, int, int] = (255, 255, 0)  # Aim line color

    # Ranged projectile
    projectile_pos: Optional[Tuple[float, float]] = None  # Projectile position
    projectile_progress: float = 0.0  # Projectile flight progress


@dataclass
class ProjectileAnimation(Component):
    """Projectile animation component (for ranged attacks)."""

    # Start position (world pixel coordinates)
    start_pos: Tuple[float, float] = (0, 0)

    # Target position (world pixel coordinates)
    target_pos: Tuple[float, float] = (0, 0)

    # Current position
    current_pos: Tuple[float, float] = (0, 0)

    # Flight progress (0.0-1.0)
    flight_progress: float = 0.0

    # Flight speed
    flight_speed: float = 800.0  # Pixels/sec

    # Whether currently flying
    is_flying: bool = False

    # Projectile type
    projectile_type: str = "arrow"  # arrow, bolt, stone, magic

    # Arc height (parabolic approximation)
    arc_height: float = 50.0

    # Projectile size
    size: float = 1.0

    # Projectile color
    color: Tuple[int, int, int] = (139, 69, 19)  # Brown arrow

    # Rotation angle (by flight direction)
    rotation: float = 0.0


@dataclass
class EffectAnimation(Component):
    """Effect animation component."""

    # Effect type
    effect_type: str = "none"  # slash, impact, explosion, heal, buff, debuff

    # Progress (0.0-1.0)
    progress: float = 0.0

    # Speed
    speed: float = 6.0

    # Whether currently playing
    is_playing: bool = False

    # Effect position (world pixel coordinates)
    effect_position: Tuple[float, float] = (0, 0)

    # Effect size
    effect_size: float = 1.0

    # Effect color
    effect_color: Tuple[int, int, int] = (255, 255, 255)

    # Duration
    duration: float = 0.5

    # Elapsed time
    elapsed_time: float = 0.0
