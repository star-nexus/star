"""
Minimap-related components.
"""

from dataclasses import dataclass
from typing import Tuple
from framework import SingletonComponent


@dataclass
class MiniMap(SingletonComponent):
    """Singleton minimap component (data-only)."""

    # Display
    visible: bool = True
    width: int = 200
    height: int = 150
    position: Tuple[int, int] = (10, 10)  # Screen position

    # Scale and anchoring
    scale: float = 0.1  # Relative to main map
    center_on_camera: bool = True  # Center on camera

    # Visuals
    background_alpha: int = 180  # Background opacity
    border_color: Tuple[int, int, int] = (255, 255, 255)  # Border color
    border_width: int = 2

    # Layers
    show_units: bool = True
    show_terrain: bool = True
    show_fog_of_war: bool = True
    show_camera_viewport: bool = True  # Show main camera viewport

    # Interaction
    clickable: bool = True  # Click minimap to navigate
