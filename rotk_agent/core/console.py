"""Shared rich consoles.

`console` carries per-iteration gameplay chatter; `console_system` carries
lifecycle output (startup, connection, summary) that stays useful even when
gameplay logging is silenced.
"""

from __future__ import annotations

from rich.console import Console

console = Console()
console_system = Console()

__all__ = ["console", "console_system"]
