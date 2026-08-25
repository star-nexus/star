"""LLM-facing views of in-world ``ActionType``, plus query/meta verbs.

Prefab-level static config (same layer as ``ActionType`` / ``PLAYER_PRESETS``).
Not a Component (no per-entity state) and not a System (no tick).

Unit-kind names must match ``ActionType.value``. Query/meta/observation names
are the LLM gateway around that enum — they are not extra ECS action types.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, FrozenSet, List, Tuple

from .config import ActionType

BENCH = "bench"
FULL = "full"
DEBUG = "debug"

_TIER = {BENCH: 0, FULL: 1, DEBUG: 2}


@dataclass(frozen=True)
class ActionSpec:
    name: str
    description: str
    kind: str  # unit | query | meta | observation
    min_profile: str
    parameters: Dict[str, Any]


def _p(typ: str, required: bool, description: str) -> Dict[str, Any]:
    return {
        "type": typ,
        "required": required,
        "description": description,
    }


ACTIONS: Tuple[ActionSpec, ...] = (
    ActionSpec(
        "move",
        "Move a unit to target position (may repeat until AP is exhausted)",
        "unit",
        BENCH,
        {
            "unit_id": _p("int", True, "ID of the moving unit (must be alive)"),
            "target_position": {
                "type": "object",
                "required": True,
                "description": "Target position (col/row)",
                "properties": {
                    "col": {"type": "int", "description": "column"},
                    "row": {"type": "int", "description": "row"},
                },
            },
        },
    ),
    ActionSpec(
        "attack",
        "Attack a target enemy unit (may repeat until AP is exhausted)",
        "unit",
        BENCH,
        {
            "unit_id": _p("int", True, "Attacker unit ID"),
            "target_id": _p("int", True, "Target unit ID"),
        },
    ),
    ActionSpec(
        "get_faction_state",
        "Get state for a faction: surviving unit positions and remaining strength",
        "query",
        BENCH,
        {
            "faction": _p("string", True, "Faction name (wei | shu | wu)"),
        },
    ),
    ActionSpec(
        "rest",
        "Unit rests and recovers",
        "unit",
        FULL,
        {"unit_id": _p("int", True, "Unit ID")},
    ),
    ActionSpec(
        "occupy",
        "Occupy a territory tile",
        "unit",
        FULL,
        {
            "unit_id": _p("int", True, "Unit ID"),
            "position": {
                "type": "object",
                "required": True,
                "description": "Tile to occupy (col/row)",
            },
        },
    ),
    ActionSpec(
        "fortify",
        "Build fortification on a tile",
        "unit",
        FULL,
        {
            "unit_id": _p("int", True, "Unit ID"),
            "position": {
                "type": "object",
                "required": True,
                "description": "Tile to fortify (col/row)",
            },
        },
    ),
    ActionSpec(
        "skill",
        "Use a unit skill",
        "unit",
        FULL,
        {
            "unit_id": _p("int", True, "Unit ID"),
            "skill_name": _p("string", True, "Skill name"),
            "target": _p("any", False, "Optional skill target"),
        },
    ),
    ActionSpec(
        "get_faction_state_vlm",
        "Faction state plus the current rendered frame as base64 PNG",
        "query",
        FULL,
        {
            "faction": _p("string", True, "Faction name (wei | shu | wu)"),
        },
    ),
    ActionSpec(
        "get_action_list",
        "Return docs for the requested profile (default bench). Does not change the board.",
        "meta",
        FULL,
        {
            "profile": _p(
                "string",
                False,
                "bench | full | debug. Default bench (same verbs as the eval agent).",
            ),
        },
    ),
    ActionSpec(
        "end_turn",
        "End the current faction's turn. Turn-based only.",
        "meta",
        FULL,
        {
            "faction": _p("string", True, "Your faction (wei | shu | wu)"),
            "force": _p("bool", False, "Force end turn"),
        },
    ),
    ActionSpec(
        "observation",
        "Request an observation at a named level (unit | faction | limited)",
        "observation",
        FULL,
        {
            "observation_level": _p(
                "string",
                False,
                "unit | faction | limited (godview is debug-only)",
            ),
            "faction": _p("string", False, "Required for faction/limited"),
            "unit_id": _p("int", False, "Required for unit"),
        },
    ),
    ActionSpec(
        "limited_observation",
        "Fog-of-war observation for one faction",
        "observation",
        FULL,
        {"faction": _p("string", True, "Faction name")},
    ),
    ActionSpec(
        "unit_observation",
        "Observation centered on one unit",
        "observation",
        FULL,
        {"unit_id": _p("int", True, "Unit ID")},
    ),
    ActionSpec(
        "faction_observation",
        "Faction-level observation",
        "observation",
        FULL,
        {"faction": _p("string", True, "Faction name")},
    ),
    ActionSpec(
        "godview_observation",
        "Omniscient observation (debug / opt-in only)",
        "observation",
        DEBUG,
        {},
    ),
)


_ACTION_TYPE_VALUES = {member.value for member in ActionType}
for _spec in ACTIONS:
    if _spec.kind == "unit" and _spec.name not in _ACTION_TYPE_VALUES:
        raise RuntimeError(
            f"unit action {_spec.name!r} is not an ActionType value: {_ACTION_TYPE_VALUES}"
        )


def _included(spec: ActionSpec, profile: str) -> bool:
    if profile not in _TIER:
        raise ValueError(f"Unknown action profile: {profile}")
    return _TIER[spec.min_profile] <= _TIER[profile]


def specs_for(profile: str) -> List[ActionSpec]:
    return [spec for spec in ACTIONS if _included(spec, profile)]


def action_names(profile: str) -> FrozenSet[str]:
    return frozenset(spec.name for spec in specs_for(profile))


def docs_for(profile: str) -> Dict[str, Any]:
    return {
        spec.name: {
            "description": spec.description,
            "kind": spec.kind,
            "parameters": spec.parameters,
        }
        for spec in specs_for(profile)
    }


def is_observation(name: str) -> bool:
    return any(spec.name == name and spec.kind == "observation" for spec in ACTIONS)


def observation_names(profile: str) -> FrozenSet[str]:
    return frozenset(
        spec.name for spec in specs_for(profile) if spec.kind == "observation"
    )


def resolve_profile(name: str | None, default: str = BENCH) -> str:
    if not name:
        return default
    key = str(name).strip().lower()
    if key not in _TIER:
        raise ValueError(f"Unknown action profile: {name}")
    return key


_READ_KINDS = frozenset({"query", "observation"})
_READ_META = frozenset({"get_action_list"})


def is_world_mutating(name: str) -> bool:
    """Whether executing ``name`` can change what an observation would see.

    ``get_action_list`` is catalogued as meta but is a docs read. Unknown
    names are treated as mutating so a successful handler-only verb still
    invalidates the observation cache.
    """
    if name in _READ_META:
        return False
    for spec in ACTIONS:
        if spec.name == name:
            return spec.kind not in _READ_KINDS
    return True


__all__ = [
    "ACTIONS",
    "ActionSpec",
    "BENCH",
    "DEBUG",
    "FULL",
    "action_names",
    "docs_for",
    "is_observation",
    "is_world_mutating",
    "observation_names",
    "resolve_profile",
    "specs_for",
]
