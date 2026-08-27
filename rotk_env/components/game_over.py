"""
Game Over related components (data only; no pygame).
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Tuple
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
class GameOverButton:
    """One Game Over screen button. Geometry is screen pixels, not a pygame.Rect."""

    action: str
    label: str
    x: int
    y: int
    w: int
    h: int
    hover: bool = False
    default_color: Tuple[int, int, int] = (60, 60, 80)
    hover_color: Tuple[int, int, int] = (80, 80, 100)

    def contains(self, pos: Tuple[int, int]) -> bool:
        px, py = pos
        return self.x <= px < self.x + self.w and self.y <= py < self.y + self.h


@dataclass
class GameOverButtons(SingletonComponent):
    """Game Over screen buttons."""

    buttons: Dict[str, GameOverButton] = field(default_factory=dict)
