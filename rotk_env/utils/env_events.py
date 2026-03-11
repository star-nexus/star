"""
Game event module.
Defines various in-game events.
"""

from dataclasses import dataclass
from typing import Tuple, Optional
from framework import Event
from ..prefabs.config import Faction


@dataclass
class TurnStartEvent(Event):
    """Turn start event."""

    faction: Faction


@dataclass
class TurnEndEvent(Event):
    """Turn end event."""

    faction: Faction


@dataclass
class BattleEvent(Event):
    """Battle event."""

    attacker_entity: int
    target_entity: int
    damage: int


@dataclass
class UnitDeathEvent(Event):
    """Unit death event."""

    entity: int
    faction: Faction


@dataclass
class UnitMoveEvent(Event):
    """Unit move event."""

    entity: int
    from_pos: Tuple[int, int]
    to_pos: Tuple[int, int]


@dataclass
class UnitSelectedEvent(Event):
    """Unit selected event."""

    entity: int


@dataclass
class TileClickedEvent(Event):
    """Tile clicked event."""

    position: Tuple[int, int]
    mouse_button: int


@dataclass
class GameOverEvent(Event):
    """Game over event."""

    winner: Optional[Faction]


@dataclass
class TerrainEffectEvent(Event):
    """Terrain effect event."""

    entity: int
    terrain_type: str
    effect_type: str
    value: float
