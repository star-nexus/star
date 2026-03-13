"""
Battle log components.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from framework import SingletonComponent


@dataclass
class BattleLogEntry:
    """Battle log entry."""

    game_time_display: str = ""  # Game time display (e.g., "T1" or "02:30")
    turn_number: Optional[int] = None  # Turn number in turn-based mode
    message: str = ""
    log_type: str = "info"  # "info", "combat", "movement", "death", "turn"
    faction: str = ""
    color: tuple = (255, 255, 255)  # Text color


@dataclass
class BattleLog(SingletonComponent):
    """Singleton battle log."""

    entries: List[BattleLogEntry] = field(default_factory=list)
    max_entries: int = 100  # Max number of entries
    show_log: bool = True  # Whether to show the log UI
    scroll_offset: int = 0  # Scroll offset (lines)
    visible_lines: int = 8  # Visible lines

    def add_entry(
        self,
        message: str,
        log_type: str = "info",
        faction: str = "",
        color: tuple = (255, 255, 255),
        game_time_display: str = "",
        turn_number: Optional[int] = None,
    ):
        """Add a battle log entry."""
        entry = BattleLogEntry(
            message=message,
            log_type=log_type,
            faction=faction,
            color=color,
            game_time_display=game_time_display,
            turn_number=turn_number,
        )

        self.entries.append(entry)

        # Enforce max size
        if len(self.entries) > self.max_entries:
            self.entries = self.entries[-self.max_entries :]

        # Auto-scroll to the newest entry
        self.scroll_to_bottom()

    def scroll_up(self):
        """Scroll up."""
        if self.scroll_offset > 0:
            self.scroll_offset -= 1

    def scroll_down(self):
        """Scroll down."""
        max_scroll = max(0, len(self.entries) - self.visible_lines)
        if self.scroll_offset < max_scroll:
            self.scroll_offset += 1

    def scroll_to_bottom(self):
        """Scroll to bottom."""
        self.scroll_offset = max(0, len(self.entries) - self.visible_lines)

    def get_visible_entries(self) -> List[BattleLogEntry]:
        """Get currently visible entries."""
        if not self.entries:
            return []

        start_idx = self.scroll_offset
        end_idx = min(start_idx + self.visible_lines, len(self.entries))
        return self.entries[start_idx:end_idx]

    def get_recent_entries(self, count: int = 10) -> List[BattleLogEntry]:
        """Get recent entries."""
        return self.entries[-count:] if self.entries else []

    def clear(self):
        """Clear the log."""
        self.entries.clear()
        self.scroll_offset = 0
        self.entries.clear()
