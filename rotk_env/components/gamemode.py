"""
Game mode components.
"""

from dataclasses import dataclass
from typing import Tuple

from framework import SingletonComponent
from ..prefabs.config import GameMode


@dataclass
class GameModeComponent(SingletonComponent):
    """Singleton game mode component."""

    mode: GameMode = GameMode.TURN_BASED

    def is_turn_based(self) -> bool:
        """Return whether the current mode is turn-based."""
        return self.mode == GameMode.TURN_BASED

    def is_real_time(self) -> bool:
        """Return whether the current mode is real-time."""
        return self.mode == GameMode.REAL_TIME


@dataclass
class MatchRules(SingletonComponent):
    """This match's allowed game-level verbs.

    A slice of the catalog master table, not the table itself. Set at
    scene init from mode + scenario. Missing this component fails closed
    to realtime skirmish (move / attack / get_faction_state).
    """

    game_actions: Tuple[str, ...] = ()
