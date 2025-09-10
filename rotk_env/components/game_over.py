"""
Game Over related components.
"""

import pygame
from dataclasses import dataclass
from typing import Dict, Any, Optional
from ..prefabs.config import Faction
from framework import SingletonComponent


@dataclass
class Winner(SingletonComponent):
    """Winner component holding the winning faction (if any)."""

    faction: Optional[Faction] = None


@dataclass
class GameStatistics(SingletonComponent):
    """Game statistics component (aggregated data)."""

    data: Dict[str, Any]


@dataclass
class GameOverButtons(SingletonComponent):
    """Game Over screen buttons component."""

    buttons: Dict[str, Dict[str, Any]]
