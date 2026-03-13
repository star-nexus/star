"""
Game time system components.

Provides unified game time management for both turn-based and real-time modes.
"""

from dataclasses import dataclass, field
from typing import Optional
import time
from framework import SingletonComponent
from ..prefabs.config import GameMode


@dataclass
class GameTime(SingletonComponent):
    """Unified game time management component."""

    # Game start time (wall-clock timestamp)
    game_start_time: float = field(default_factory=time.time)

    # Current game mode
    current_mode: GameMode = GameMode.TURN_BASED

    # Turn-based
    current_turn: int = 1
    turn_start_time: float = field(default_factory=time.time)

    # Real-time
    game_elapsed_time: float = 0.0  # In-game elapsed time (seconds)
    time_scale: float = 1.0  # Time multiplier (speed up / slow down)
    paused: bool = False  # Paused flag
    last_update_time: float = field(default_factory=time.time)

    def initialize(self, mode: GameMode):
        """Initialize the game time system."""
        current_time = time.time()
        self.game_start_time = current_time
        self.current_mode = mode
        self.turn_start_time = current_time
        self.last_update_time = current_time
        self.game_elapsed_time = 0.0
        self.current_turn = 1
        self.paused = False

    def update(self, delta_time: float):
        """Update game time (called by the time system)."""
        if not self.paused and self.current_mode == GameMode.REAL_TIME:
            # Only accumulate time in real-time mode.
            self.game_elapsed_time += delta_time * self.time_scale

        self.last_update_time = time.time()

    def advance_turn(self):
        """Advance to the next turn (turn-based mode)."""
        if self.current_mode == GameMode.TURN_BASED:
            self.current_turn += 1
            self.turn_start_time = time.time()

    def get_current_time_display(self) -> str:
        """Get a display string for the current game time."""
        if self.current_mode == GameMode.TURN_BASED:
            return f"T{self.current_turn}"
        else:
            # Real-time mode: show in-game time.
            total_seconds = int(self.game_elapsed_time)
            if total_seconds < 3600:  # < 1 hour
                minutes = total_seconds // 60
                seconds = total_seconds % 60
                return f"{minutes:02d}:{seconds:02d}"
            else:  # >= 1 hour
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                return f"{hours}h{minutes:02d}m"

    def get_turn_number(self) -> Optional[int]:
        """Get the current turn number (turn-based only)."""
        if self.current_mode == GameMode.TURN_BASED:
            return self.current_turn
        return None

    def get_game_elapsed_seconds(self) -> float:
        """Get total elapsed seconds."""
        if self.current_mode == GameMode.REAL_TIME:
            return self.game_elapsed_time
        else:
            # Turn-based mode: return real wall-clock elapsed time.
            return time.time() - self.game_start_time

    def pause(self):
        """Pause game time."""
        self.paused = True

    def resume(self):
        """Resume game time."""
        self.paused = False
        self.last_update_time = time.time()

    def set_time_scale(self, scale: float):
        """Set time scale (real-time mode only)."""
        if scale > 0:
            self.time_scale = scale

    def is_turn_based(self) -> bool:
        """Return whether the current mode is turn-based."""
        return self.current_mode == GameMode.TURN_BASED

    def is_real_time(self) -> bool:
        """Return whether the current mode is real-time."""
        return self.current_mode == GameMode.REAL_TIME

    def get_formatted_time_since_start(self) -> str:
        """Get formatted wall-clock time since game start."""
        elapsed = time.time() - self.game_start_time
        if elapsed < 60:
            return f"{int(elapsed)}s"
        elif elapsed < 3600:
            return f"{int(elapsed//60)}m{int(elapsed%60)}s"
        else:
            hours = int(elapsed // 3600)
            minutes = int((elapsed % 3600) // 60)
            return f"{hours}h{minutes}m"
