"""
Terrain-related components.

Numeric rules live on GameConfig.TERRAIN_EFFECTS. Terrain is a type tag on
the tile entity; look up effects with ``effect_for``.
"""

from dataclasses import dataclass
from typing import Optional, Tuple

from framework import Component

from ..prefabs.config import Faction, GameConfig, TerrainEffect, TerrainType


@dataclass
class Terrain(Component):
    """Terrain type on a map tile. Stats come from GameConfig.TERRAIN_EFFECTS."""

    terrain_type: TerrainType


def effect_for(terrain_type: TerrainType) -> TerrainEffect:
    """Rules-table row for a terrain type. Missing types use TerrainEffect defaults."""
    return GameConfig.TERRAIN_EFFECTS.get(terrain_type) or TerrainEffect()


def terrain_at(world, position: Tuple[int, int]) -> Optional[Terrain]:
    """Terrain component on the map tile at ``position``, if any."""
    from .state import MapData

    map_data = world.get_singleton_component(MapData)
    if not map_data:
        return None
    tile_entity = map_data.tiles.get(position)
    if not tile_entity:
        return None
    return world.get_component(tile_entity, Terrain)


def movement_cost_at(world, position: Tuple[int, int]) -> int:
    """Enter-cost of a map hex. Off-board tiles are impassable (999)."""
    terrain = terrain_at(world, position)
    if terrain is None:
        return 999
    return int(effect_for(terrain.terrain_type).movement_cost)


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
