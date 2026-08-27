"""Human control bindings shared by input, the F1 help panel, and CLI --help.

This is prefab configuration, not World state. InputHandlingSystem dispatches
KEY_BINDINGS by ``action`` name; help text is generated from the same tables.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

import pygame


@dataclass(frozen=True)
class MouseBinding:
    button: int  # pygame mouse button (1=left, 3=right)
    label: str
    help: str


@dataclass(frozen=True)
class KeyBinding:
    key: int
    label: str
    help: str
    action: str


@dataclass(frozen=True)
class HoldBinding:
    label: str
    help: str


MOUSE_BINDINGS: Tuple[MouseBinding, ...] = (
    MouseBinding(
        1,
        "Left click",
        "Select own unit; empty tile moves; enemy attacks",
    ),
    MouseBinding(3, "Right click", "Deselect"),
)

KEY_BINDINGS: Tuple[KeyBinding, ...] = (
    KeyBinding(pygame.K_SPACE, "SPACE", "End turn", "end_turn"),
    KeyBinding(pygame.K_TAB, "Tab", "Toggle statistics", "toggle_stats"),
    KeyBinding(pygame.K_F1, "F1", "Toggle help", "toggle_help"),
    KeyBinding(pygame.K_ESCAPE, "ESC", "Cancel selection", "clear_selection"),
    KeyBinding(pygame.K_PAGEUP, "Page Up", "Scroll battle log up", "battle_log_up"),
    KeyBinding(
        pygame.K_PAGEDOWN, "Page Down", "Scroll battle log down", "battle_log_down"
    ),
    KeyBinding(pygame.K_END, "End", "Jump battle log to bottom", "battle_log_bottom"),
    KeyBinding(pygame.K_h, "H", "Toggle hex orientation", "toggle_hex_orientation"),
    KeyBinding(pygame.K_1, "1", "Toggle fog (whole map / unit vision)", "toggle_fog"),
    KeyBinding(pygame.K_2, "2", "Wei spectator view (fog on)", "view_wei"),
    KeyBinding(pygame.K_3, "3", "Shu spectator view (fog on)", "view_shu"),
    KeyBinding(pygame.K_4, "4", "Wu spectator view (fog on)", "view_wu"),
    KeyBinding(pygame.K_v, "V", "Toggle coordinate overlay", "toggle_coordinates"),
)

HOLD_BINDINGS: Tuple[HoldBinding, ...] = (
    HoldBinding("WASD / arrows", "Move camera"),
    HoldBinding("+ / -", "Zoom in / out"),
)

RULE_NOTES: Tuple[str, ...] = (
    "Move spends MP along the path; attack spends AP.",
    "Fog on = your units' vision; key 1 = the whole map.",
)

_KEY_BY_CODE = {b.key: b for b in KEY_BINDINGS}


def binding_for_key(key: int) -> Optional[KeyBinding]:
    return _KEY_BY_CODE.get(key)


def help_panel_lines() -> List[str]:
    """Lines drawn in the F1 help overlay."""
    lines = ["Basic Controls:"]
    for item in MOUSE_BINDINGS:
        lines.append(f"  {item.label} - {item.help}")
    lines.append("")
    lines.append("Keyboard Shortcuts:")
    for item in KEY_BINDINGS:
        lines.append(f"  {item.label} - {item.help}")
    lines.append("")
    lines.append("Camera (hold):")
    for item in HOLD_BINDINGS:
        lines.append(f"  {item.label} - {item.help}")
    lines.append("")
    lines.append("Game Rules:")
    for note in RULE_NOTES:
        lines.append(f"  {note}")
    lines.append("")
    lines.append("Press F1 to close this help panel")
    return lines


def format_cli_controls() -> str:
    """Controls block for ``python rotk_env/main.py --help``."""
    rows = ["Controls:"]
    for item in MOUSE_BINDINGS:
        rows.append(f"  {item.label}: {item.help}")
    for item in KEY_BINDINGS:
        rows.append(f"  {item.label}: {item.help}")
    for item in HOLD_BINDINGS:
        rows.append(f"  {item.label}: {item.help}")
    return "\n".join(rows)
