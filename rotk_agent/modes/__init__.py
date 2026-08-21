"""Game modes. Each hooks the shared chat loop rather than replacing it."""

from .base import ModeStrategy
from .realtime import RealTimeMode
from .turn import TurnBasedMode

__all__ = ["ModeStrategy", "RealTimeMode", "TurnBasedMode"]
