"""
Player-related components.
"""

from dataclasses import dataclass, field
from typing import Set, Tuple, List
from framework import Component, SingletonComponent
from ..prefabs.config import Faction, PlayerType


@dataclass
class Player(Component):
    """Player component."""

    faction: Faction
    player_type: PlayerType
    color: Tuple[int, int, int]
    units: Set[int] = field(default_factory=set)
    resources: int = 0
    score: int = 0
    name: str = ""

    def __post_init__(self):
        if not self.name:
            self.name = self.faction.value


@dataclass
class TurnOrder(Component):
    """Turn order component."""

    order: int  # Turn order


@dataclass
class TurnManager(SingletonComponent):
    """Singleton turn manager."""

    players: List[int] = field(default_factory=list)  # Player entity ids
    current_player_index: int = 0

    def get_current_player(self) -> int:
        """Get current player entity id."""
        if self.players and 0 <= self.current_player_index < len(self.players):
            return self.players[self.current_player_index]
        return None

    def next_player(self):
        """Advance to the next player."""
        if self.players:
            self.current_player_index = (self.current_player_index + 1) % len(
                self.players
            )

    def add_player(self, player_entity: int):
        """Add a player."""
        if player_entity not in self.players:
            self.players.append(player_entity)
