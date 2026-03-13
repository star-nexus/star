"""
Terrain-related components.
"""

from dataclasses import dataclass
from typing import Tuple, Optional
from framework import Component
from ..prefabs.config import TerrainType, Faction


@dataclass
class Terrain(Component):
    """Terrain component."""

    terrain_type: TerrainType
    movement_cost: int = 1
    defense_bonus: int = 0
    attack_bonus: int = 0
    vision_bonus: int = 0
    blocks_line_of_sight: bool = False


@dataclass
class TerrainModifier(Component):
    """Terrain modifier component."""

    attack_modifier: float = 1.0
    defense_modifier: float = 1.0
    movement_modifier: float = 1.0
    vision_modifier: float = 1.0


@dataclass
class Tile(Component):
    """Map tile component."""

    position: Tuple[int, int]  # Tile coordinates
    occupied_by: Optional[int] = None  # Occupying unit entity id


@dataclass
class TerritoryControl(Component):
    """Territory control component."""

    # Faction controlling this tile
    controlling_faction: Optional[Faction] = None

    # Whether capture is in progress
    being_captured: bool = False

    # Unit currently capturing
    capturing_unit: Optional[int] = None

    # Capture progress (0.0-1.0)
    capture_progress: float = 0.0

    # Time required to capture (seconds)
    capture_time_required: float = 5.0

    # Whether the tile is fortified
    fortified: bool = False

    # Fortification level (affects defense bonus)
    fortification_level: int = 0

    # Capture timestamp
    captured_time: float = 0.0

    # Whether this tile is a city (higher capture cost, higher reward)
    is_city: bool = False


@dataclass
class CaptureAction(Component):
    """Capture action component."""

    # Capturing unit
    capturing_unit: int

    # Target tile position
    target_position: Tuple[int, int]

    # Capture start time
    start_time: float = 0.0

    # Whether action points are used in turn-based mode
    uses_action_points: bool = True

    # Action point cost
    action_points_cost: int = 1

    # Whether the capture is completed
    completed: bool = False
