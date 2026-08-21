"""Pacing helpers for the real-time mode.

In real-time mode the ENV animates movement, so firing the next action the
instant the ENV acknowledges the previous one makes the agent act on a world
state that is still mid-animation. Turn-based mode has no animation race and
uses no delay at all.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

from .console import console, console_system

ATTACK_ANIMATION_SECONDS = 0.2
DEFAULT_ACTION_SECONDS = 0.1
FALLBACK_MOVE_SECONDS = 1.0
INSTANT_ACTIONS = ("get_faction_state", "observation", "get_action_list")


async def rpm_limit_interval() -> None:
    """Sleep between LLM calls to stay under a provider's requests-per-minute cap."""
    interval = float(os.environ.get("INTERVAL", "0"))
    console_system.print(f"🕒 Interval: {interval}s", style="bold blue")
    await asyncio.sleep(interval)


def calculate_move_delay(params: Any, response: Any) -> float:
    """Prefer the ENV's own duration estimate, then path length, then a guess."""
    try:
        details = response.get("movement_details") if isinstance(response, dict) else None
        if isinstance(details, dict):
            estimated = details.get("estimated_duration_seconds", 0)
            if estimated and estimated > 0:
                return estimated * 1.1  # buffer so the animation surely finished

            path_length = details.get("path_length", 0)
            if path_length and path_length > 0:
                return path_length / 2.0 + 0.2  # roughly two tiles per second

        return FALLBACK_MOVE_SECONDS
    except Exception as e:
        console.print(f"⚠️ Error calculating move delay: {e}", style="yellow")
        return FALLBACK_MOVE_SECONDS


def calculate_action_delay(action: str, params: Any, response: Any) -> float:
    """How long to wait after a successful action before acting again."""
    if not (isinstance(response, dict) and response.get("result", False)):
        return 0.0

    if action == "move":
        return calculate_move_delay(params, response)
    if action == "attack":
        return ATTACK_ANIMATION_SECONDS
    if action in INSTANT_ACTIONS:
        return 0.0
    return DEFAULT_ACTION_SECONDS


def no_delay(action: str, params: Any, response: Any) -> float:
    """Delay policy for turn-based mode: never wait."""
    return 0.0


__all__ = [
    "rpm_limit_interval",
    "calculate_action_delay",
    "calculate_move_delay",
    "no_delay",
]
