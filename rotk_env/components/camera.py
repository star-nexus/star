from dataclasses import dataclass
from typing import Tuple
from framework import SingletonComponent


@dataclass
class Camera(SingletonComponent):
    """Singleton camera component."""

    offset_x: float = 0.0  # Camera X offset
    offset_y: float = 0.0  # Camera Y offset
    zoom: float = 1.0  # Zoom level
    speed: float = 200.0  # Pan speed (pixels/sec)

    def get_offset(self) -> Tuple[float, float]:
        """Get camera offset."""
        return (self.offset_x, self.offset_y)

    def set_offset(self, x: float, y: float) -> None:
        """Set camera offset."""
        self.offset_x = x
        self.offset_y = y

    def move(self, dx: float, dy: float) -> None:
        """Move the camera by (dx, dy)."""
        self.offset_x += dx
        self.offset_y += dy
