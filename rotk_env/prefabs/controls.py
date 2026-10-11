"""Human control bindings shared by input, the F1 help panel, and CLI --help.

This is prefab configuration, not World state. InputHandlingSystem dispatches
KEY_BINDINGS by ``action`` name; help text is generated from the same tables.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple



@dataclass(frozen=True)
class MouseBinding:
    button: int  # Semantic primary=1, secondary=3.
    label: str
    help: str


@dataclass(frozen=True)
class KeyBinding:
    key: str
    label: str
    help: str
    action: str
    modifiers: bool = False


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
    KeyBinding('SPACE', "SPACE", "End turn", "end_turn"),
    KeyBinding('TAB', "Tab", "Toggle statistics", "toggle_stats"),
    KeyBinding('F1', "F1", "Toggle help", "toggle_help"),
    KeyBinding('ESCAPE', "ESC", "Cancel target, then selection", "clear_selection"),
    KeyBinding('PAGEUP', "Page Up", "Scroll battle log up", "battle_log_up"),
    KeyBinding(
        'PAGEDOWN', "Page Down", "Scroll battle log down", "battle_log_down"
    ),
    KeyBinding('END', "End", "Jump battle log to bottom", "battle_log_bottom"),
    KeyBinding('h', "H", "Toggle hex orientation", "toggle_hex_orientation"),
    KeyBinding('1', "Shift+1", "Toggle fog (whole map / unit vision)", "toggle_fog", True),
    KeyBinding('1', "1", "Select infantry", "select_infantry"),
    KeyBinding('2', "2", "Select cavalry", "select_cavalry"),
    KeyBinding('3', "3", "Select first archer", "select_archer_1"),
    KeyBinding('4', "4", "Select second archer", "select_archer_2"),
    KeyBinding('5', "5", "Select third archer", "select_archer_3"),
    KeyBinding('m', "M", "Choose movement target", "unit_move"),
    KeyBinding('a', "A", "Choose attack target", "unit_attack"),
    KeyBinding('w', "W", "Wait", "unit_wait"),
    KeyBinding('g', "G", "Garrison", "unit_garrison"),
    KeyBinding('c', "C", "Capture", "unit_capture"),
    KeyBinding('f', "F", "Fortify", "unit_fortify"),
    KeyBinding('2', "Shift+2", "Wei spectator view (fog on)", "view_wei", True),
    KeyBinding('3', "Shift+3", "Shu spectator view (fog on)", "view_shu", True),
    KeyBinding('4', "Shift+4", "Wu spectator view (fog on)", "view_wu", True),
    KeyBinding('v', "V", "Toggle coordinate overlay", "toggle_coordinates"),
)

HOLD_BINDINGS: Tuple[HoldBinding, ...] = (
    HoldBinding("Arrows", "Move camera"),
    HoldBinding("+ / -", "Zoom in / out"),
)

RULE_NOTES: Tuple[str, ...] = (
    "Move spends MP along the path; attack spends AP.",
    "Fog on = your units' vision; Shift+1 toggles the whole map.",
)

def binding_for_key(key: str, shifted: bool = False) -> Optional[KeyBinding]:
    """Resolve a semantic key after the selected input adapter decodes its event."""
    return next((b for b in KEY_BINDINGS if b.key == key and b.modifiers == shifted), None)


def action_hotkey(action: str) -> str:
    binding = next((b for b in KEY_BINDINGS if b.action == 'unit_'+action), None)
    return binding.label if binding else ''


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
