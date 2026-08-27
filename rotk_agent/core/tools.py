"""Tool registry and the canonical tool schemas.

There is one schema per tool, shared by every model. Names, parameter shapes,
and board bounds after join come from ``register_agent_info`` — this module
must not import ``rotk_env``.

The pre-join fallback is a local copy of the skirmish three, used only until
the ENV replies (or if join fails). It is a string tuple in this file, not a
shared symbol with the ENV catalog.
"""

from __future__ import annotations

import asyncio
import copy
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence

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


# Pre-join placeholder. Must stay a local literal — do not import ENV.
FALLBACK_ACTION_NAMES: tuple[str, ...] = ("move", "attack", "get_faction_state")

_JSON_TYPES = {
    "int": "integer",
    "integer": "integer",
    "str": "string",
    "string": "string",
    "bool": "boolean",
    "boolean": "boolean",
    "object": "object",
    "array": "array",
    "number": "number",
}


@dataclass(frozen=True)
class BoardBounds:
    """Inclusive even-q offset range for one match, from the join map sheet."""

    col_min: int
    col_max: int
    row_min: int
    row_max: int


def board_bounds_from_map(briefing: Optional[dict]) -> Optional[BoardBounds]:
    """Read board limits from ``register_agent_info.map``.

    Prefer the explicit ``col_min``/``col_max``/``row_min``/``row_max`` the ENV
    now sends. Older replies only had ``width``/``height``: those are treated as
    a centered even-q grid (the map-file convention), not as 0-based indices.
    """
    if not isinstance(briefing, dict):
        return None

    keys = ("col_min", "col_max", "row_min", "row_max")
    if all(type(briefing.get(k)) is int for k in keys):
        return BoardBounds(
            col_min=briefing["col_min"],
            col_max=briefing["col_max"],
            row_min=briefing["row_min"],
            row_max=briefing["row_max"],
        )

    width = briefing.get("width")
    height = briefing.get("height")
    if isinstance(width, int) and isinstance(height, int) and width > 0 and height > 0:
        half_w = width // 2
        half_h = height // 2
        return BoardBounds(
            col_min=-half_w,
            col_max=width - half_w - 1,
            row_min=-(height - half_h - 1),
            row_max=half_h,
        )
    return None


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
                    "description": "Target column (even-q offset).",
                },
                "row": {
                    "type": "integer",
                    "description": "Target row (even-q offset).",
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
        "visible (id, type, position, count). Fog on = your units' vision; fog "
        "off (key 1) = the whole map. faction must be your own. Does not "
        "consume any points."
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

_FALLBACK_PARAM_SCHEMAS = {
    "move": MOVE_PARAMS,
    "attack": ATTACK_PARAMS,
    "get_faction_state": FACTION_STATE_PARAMS,
}

PERFORM_ACTION_DESCRIPTION = "Execute a specific action in the game environment."


def perform_action_names(names: Optional[Iterable[str]] = None) -> List[str]:
    """Names advertised on ``perform_action``. ``end_turn`` is a dedicated tool."""
    source = FALLBACK_ACTION_NAMES if names is None else names
    cleaned: List[str] = []
    for name in source:
        if not isinstance(name, str):
            continue
        if name == "end_turn" or not name:
            continue
        cleaned.append(name)
    return sorted(cleaned)


def _env_field_to_json(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Translate one ENV ActionSpec field into JSON Schema."""
    out: Dict[str, Any] = {}
    raw_type = spec.get("type")
    json_type = _JSON_TYPES.get(raw_type) if isinstance(raw_type, str) else None
    if json_type:
        out["type"] = json_type
    description = spec.get("description")
    if description:
        out["description"] = description
    if isinstance(spec.get("enum"), list) and spec["enum"]:
        out["enum"] = list(spec["enum"])
    for bound in ("minimum", "maximum"):
        value = spec.get(bound)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        out[bound] = value

    nested = spec.get("properties")
    if json_type == "object" or isinstance(nested, dict):
        out["type"] = "object"
        out["additionalProperties"] = False
        properties = nested if isinstance(nested, dict) else {}
        out["properties"] = {
            key: _env_field_to_json(value) if isinstance(value, dict) else {}
            for key, value in properties.items()
        }
        if properties:
            out["required"] = list(properties)
    return out


def _env_params_to_json_schema(parameters: Dict[str, Any], title: str) -> Dict[str, Any]:
    properties: Dict[str, Any] = {}
    required: List[str] = []
    for name, spec in parameters.items():
        if not isinstance(spec, dict):
            properties[name] = {}
            continue
        properties[name] = _env_field_to_json(spec)
        if spec.get("required") is True:
            required.append(name)
    schema: Dict[str, Any] = {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
        "title": title,
    }
    if required:
        schema["required"] = required
    return schema


def _apply_board_bounds(node: Any, board: BoardBounds) -> Any:
    """Stamp inclusive col/row ranges onto integer axis fields."""
    if isinstance(node, list):
        return [_apply_board_bounds(item, board) for item in node]
    if not isinstance(node, dict):
        return node

    updated = {key: _apply_board_bounds(value, board) for key, value in node.items()}
    properties = updated.get("properties")
    if not isinstance(properties, dict):
        return updated

    axes = (
        ("col", board.col_min, board.col_max),
        ("row", board.row_min, board.row_max),
    )
    for axis, lo, hi in axes:
        field = properties.get(axis)
        if not isinstance(field, dict):
            continue
        if field.get("type") not in (None, "integer"):
            continue
        field = dict(field)
        field["type"] = "integer"
        field["minimum"] = lo
        field["maximum"] = hi
        description = str(field.get("description") or axis).rstrip(".")
        if "range" not in description.lower():
            field["description"] = f"{description} (range {lo} to {hi})."
        properties[axis] = field
    return updated


def _param_schema_for(
    name: str,
    docs: Optional[Dict[str, Any]],
    board: Optional[BoardBounds],
) -> Dict[str, Any]:
    """One ``params`` oneOf variant for ``name``."""
    spec = docs.get(name) if isinstance(docs, dict) else None
    schema: Optional[Dict[str, Any]] = None
    parameters = spec.get("parameters") if isinstance(spec, dict) else None
    if isinstance(parameters, dict) and parameters:
        schema = _env_params_to_json_schema(parameters, name)
        description = spec.get("description")
        if isinstance(description, str) and description:
            schema["description"] = description
    elif name in _FALLBACK_PARAM_SCHEMAS:
        schema = copy.deepcopy(_FALLBACK_PARAM_SCHEMAS[name])
    else:
        schema = {
            "type": "object",
            "title": name,
            "additionalProperties": True,
        }

    if board is not None:
        schema = _apply_board_bounds(schema, board)
    return schema


def perform_action_schema(
    names: Optional[Sequence[str]] = None,
    *,
    docs: Optional[Dict[str, Any]] = None,
    board: Optional[BoardBounds] = None,
) -> Dict[str, Any]:
    """JSON schema for ``perform_action``.

    ``names`` / ``docs`` / ``board`` are the join payload. Omit them for the
    pre-join fallback (skirmish three, no coordinate clamp).
    """
    advertised = perform_action_names(names)
    variants = [_param_schema_for(name, docs, board) for name in advertised]
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "action": {
                "type": "string",
                "description": "The name of the action to execute.",
                "enum": advertised,
            },
            "params": {
                "description": "Parameters object for the specified action.",
                "oneOf": variants or [{"type": "object"}],
            },
        },
        "required": ["action", "params"],
    }


PERFORM_ACTION_SCHEMA = perform_action_schema()

END_TURN_SCHEMA = {"type": "object", "properties": {}, "required": []}

END_TURN_DESCRIPTION = (
    "End the current turn. Action Points and Movement Points are restored, and "
    "play passes to the next faction."
)


def perform_action_tool(
    function: Callable,
    names: Optional[Sequence[str]] = None,
    *,
    docs: Optional[Dict[str, Any]] = None,
    board: Optional[BoardBounds] = None,
) -> ToolDefinition:
    """The one tool every agent gets, in every mode."""
    return ToolDefinition(
        name="perform_action",
        description=PERFORM_ACTION_DESCRIPTION,
        parameters=perform_action_schema(names, docs=docs, board=board),
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
    "BoardBounds",
    "FALLBACK_ACTION_NAMES",
    "PERFORM_ACTION_SCHEMA",
    "PERFORM_ACTION_DESCRIPTION",
    "END_TURN_SCHEMA",
    "END_TURN_DESCRIPTION",
    "board_bounds_from_map",
    "perform_action_names",
    "perform_action_schema",
    "perform_action_tool",
    "end_turn_tool",
]
