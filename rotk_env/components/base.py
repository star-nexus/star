"""
Base component module.
"""

from dataclasses import dataclass
from typing import Tuple, Optional
from framework import Component


@dataclass
class HexPosition(Component):
    """Hex-grid position component."""

    col: int
    row: int


@dataclass
class Renderable(Component):
    """Renderable component."""

    color: Tuple[int, int, int]
    size: int = 20
    visible: bool = True


@dataclass
class AnimationState(Component):
    """Animation state component."""

    animation_type: str = "idle"
    frame: int = 0
    duration: float = 0.0


@dataclass
class PathFinding(Component):
    """Pathfinding component."""

    target_position: Optional[Tuple[int, int]] = None
    path: list = None
    path_index: int = 0
