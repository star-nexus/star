"""Tool registry and the canonical tool schemas.

There is one schema per tool, shared by every model. The old per-file agents
had drifted apart here too: the Nemotron scripts shipped a Chinese schema with
every field description stripped, so that model saw materially less guidance
than the others, and they registered an extra `stop_running` tool whose name,
description, docstring, and return value all disagreed with each other.
"""

from __future__ import annotations

import asyncio
from typing import Any, Callable, Dict, List
import os

from rotk_env.prefabs.action_catalog import BENCH, action_names, resolve_profile

from .types import ToolDefinition


class ToolManager:
    """Name-to-tool registry with uniform async dispatch."""

    def __init__(self):
        self.tools: Dict[str, ToolDefinition] = {}

    def register_tool(self, tool: ToolDefinition) -> None:
        self.tools[tool.name] = tool

    def get_tool_definitions(self) -> List[ToolDefinition]:
        return list(self.tools.values())

    def has(self, tool_name: str) -> bool:
        return tool_name in self.tools

    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        if tool_name not in self.tools:
            raise ValueError(f"Tool {tool_name} does not exist")

        tool = self.tools[tool_name]
        if asyncio.iscoroutinefunction(tool.function):
            return await tool.function(**arguments)
        return tool.function(**arguments)


# Hex coordinates are flat-topped even-q offsets centred on the origin, so the
# 15x15 board spans -7..7 on both axes.
BOARD_MIN = -7
BOARD_MAX = 7

MOVE_PARAMS = {
    "type": "object",
    "description": "Move a unit to a target position. Consumes Movement Points (MP).",
    "additionalProperties": False,
    "properties": {
        "unit_id": {
            "type": "integer",
            "minimum": 0,
            "description": "Friendly unit identifier.",
        },
        "target_position": {
            "type": "object",
            "description": "Target position in flat-topped even-q offset coordinates.",
            "additionalProperties": False,
            "properties": {
                "col": {
                    "type": "integer",
                    "minimum": BOARD_MIN,
                    "maximum": BOARD_MAX,
                    "description": f"Target column (even-q offset), range {BOARD_MIN} to {BOARD_MAX}.",
                },
                "row": {
                    "type": "integer",
                    "minimum": BOARD_MIN,
                    "maximum": BOARD_MAX,
                    "description": f"Target row (even-q offset), range {BOARD_MIN} to {BOARD_MAX}.",
                },
            },
            "required": ["col", "row"],
        },
    },
    "required": ["unit_id", "target_position"],
    "title": "move",
}

ATTACK_PARAMS = {
    "type": "object",
    "description": "Attack a target unit with a friendly unit. Consumes 1 Action Point (AP).",
    "additionalProperties": False,
    "properties": {
        "unit_id": {
            "type": "integer",
            "minimum": 0,
            "description": "Attacking friendly unit identifier.",
        },
        "target_id": {
            "type": "integer",
            "minimum": 0,
            "description": "Target enemy unit identifier.",
        },
    },
    "required": ["unit_id", "target_id"],
    "title": "attack",
}

FACTION_STATE_PARAMS = {
    "type": "object",
    "description": (
        "Your army (positions, HP, remaining AP and MP) plus enemies currently "
        "visible on screen (id, type, position, count). faction must be your "
        "own. Does not consume any points."
    ),
    "additionalProperties": False,
    "properties": {
        "faction": {
            "type": "string",
            "enum": ["wei", "shu", "wu"],
            "description": "Your faction (one of: wei, shu, wu).",
        },
    },
    "required": ["faction"],
    "title": "get_faction_state",
}

PERFORM_ACTION_DESCRIPTION = "Execute a specific action in the game environment."


def perform_action_schema(profile: str = BENCH) -> Dict[str, Any]:
    """JSON schema for ``perform_action``. Enum comes from the shared catalog."""
    names = sorted(action_names(profile))
    schema: Dict[str, Any] = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "action": {
                "type": "string",
                "description": "The name of the action to execute.",
                "enum": names,
            },
            "params": {
                "description": "Parameters object for the specified action.",
                "oneOf": [MOVE_PARAMS, ATTACK_PARAMS, FACTION_STATE_PARAMS],
            },
        },
        "required": ["action", "params"],
    }
    if profile != BENCH:
        # Full/debug: advertise every catalog verb; params stay a free object
        # so occupy/skill/etc. are not forced into the three bench shapes.
        schema["properties"]["params"] = {
            "description": "Parameters object for the specified action.",
            "type": "object",
        }
    return schema


def _default_action_profile() -> str:
    try:
        return resolve_profile(os.environ.get("STAR_ACTION_PROFILE"), BENCH)
    except ValueError:
        return BENCH


PERFORM_ACTION_SCHEMA = perform_action_schema(_default_action_profile())

END_TURN_SCHEMA = {"type": "object", "properties": {}, "required": []}

END_TURN_DESCRIPTION = (
    "End the current turn. Action Points and Movement Points are restored, and "
    "play passes to the next faction."
)


def perform_action_tool(function: Callable) -> ToolDefinition:
    """The one tool every agent gets, in every mode."""
    return ToolDefinition(
        name="perform_action",
        description=PERFORM_ACTION_DESCRIPTION,
        parameters=PERFORM_ACTION_SCHEMA,
        function=function,
    )


def end_turn_tool(function: Callable) -> ToolDefinition:
    """Turn-based mode only; real-time mode has no turn to end."""
    return ToolDefinition(
        name="end_turn",
        description=END_TURN_DESCRIPTION,
        parameters=END_TURN_SCHEMA,
        function=function,
    )


__all__ = [
    "ToolManager",
    "PERFORM_ACTION_SCHEMA",
    "PERFORM_ACTION_DESCRIPTION",
    "END_TURN_SCHEMA",
    "END_TURN_DESCRIPTION",
    "perform_action_schema",
    "perform_action_tool",
    "end_turn_tool",
]
