"""Implemented game-level verbs, plus this match's subset.

Prefab-level static config (same layer as ``ActionType`` / ``PLAYER_PRESETS``).
Not a Component (no per-entity state) and not a System (no tick).

Two interaction classes:

- **Game-level** (this file): changes or reads what a human sees on the board.
  The master table is every *implemented* verb. A match subset is a slice of
  that table, stored on ``MatchRules``. Agents never see the master table.
- **System-level** (``LLMSystem.system_actions``): identity, telemetry, hub
  session. ``get_action_list`` lives there and returns this match's subset.

Unit-kind names must match ``ActionType.value``, except ``end_turn`` (a
turn-based rule verb, not an ECS action type). Unimplemented ``ActionType``
members (defend / scout / retreat) stay on the enum and stay off this table.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Sequence, Tuple

from .config import ActionType

SKIRMISH_ACTIONS: Tuple[str, ...] = ("move", "attack", "get_faction_state")
_FACTION_ENUM = ["wei", "shu", "wu"]


@dataclass(frozen=True)
class ActionSpec:
    name: str
    description: str
    kind: str  # unit | query | rule
    parameters: Dict[str, Any]


def _p(typ: str, required: bool, description: str, **extra: Any) -> Dict[str, Any]:
    payload = {
        "type": typ,
        "required": required,
        "description": description,
    }
    payload.update(extra)
    return payload


def _hex(description: str) -> Dict[str, Any]:
    return {
        "type": "object",
        "required": True,
        "description": description,
        "properties": {
            "col": {"type": "int", "description": "column"},
            "row": {"type": "int", "description": "row"},
        },
    }


GAME_ACTIONS: Tuple[ActionSpec, ...] = (
    ActionSpec(
        "move",
        "Move a unit to a target tile. Spends movement points (MP) for the "
        "terrain path; does not spend action points (AP). Repeatable while MP remains.",
        "unit",
        {
            "unit_id": _p("int", True, "ID of the moving unit (must be alive)"),
            "target_position": _hex("Target position (col/row)"),
        },
    ),
    ActionSpec(
        "attack",
        "Attack a target enemy unit (may repeat until AP is exhausted)",
        "unit",
        {
            "unit_id": _p("int", True, "Attacker unit ID"),
            "target_id": _p("int", True, "Target unit ID"),
        },
    ),
    ActionSpec(
        "get_faction_state",
        "Your army (full detail, owner/commandable) plus living enemies in "
        "the current vision: unit id, type, position, count. Each own unit "
        "also has reachable (positions move would accept now) and attackable "
        "(enemy ids attack would accept now). Enemies have neither. Also "
        "visible_terrain (type and movement cost) on the same tiles. Fog on = "
        "union of your units' vision; fog off (key 1) = the whole map. Same "
        "rule for human, BOT, and agents. faction must be your own; querying "
        "another faction is rejected. Orders on units you do not own still fail.",
        "query",
        {
            "faction": _p(
                "string",
                True,
                "Your faction (one of: wei, shu, wu).",
                enum=_FACTION_ENUM,
            ),
        },
    ),
    ActionSpec(
        "rest",
        "Unit rests and recovers",
        "unit",
        {"unit_id": _p("int", True, "Unit ID")},
    ),
    ActionSpec(
        "occupy",
        "Occupy a territory tile",
        "unit",
        {
            "unit_id": _p("int", True, "Unit ID"),
            "position": _hex("Tile to occupy (col/row)"),
        },
    ),
    ActionSpec(
        "fortify",
        "Build fortification on a tile",
        "unit",
        {
            "unit_id": _p("int", True, "Unit ID"),
            "position": _hex("Tile to fortify (col/row)"),
        },
    ),
    ActionSpec(
        "skill",
        "Use a unit skill",
        "unit",
        {
            "unit_id": _p("int", True, "Unit ID"),
            "skill_name": _p("string", True, "Skill name"),
            "target": _p("any", False, "Optional skill target"),
        },
    ),
    ActionSpec(
        "get_faction_state_vlm",
        "Same JSON as get_faction_state (own army + currently visible enemies), "
        "plus a PNG of the current board render.",
        "query",
        {
            "faction": _p(
                "string",
                True,
                "Your faction (one of: wei, shu, wu).",
                enum=_FACTION_ENUM,
            ),
        },
    ),
    ActionSpec(
        "end_turn",
        "End the current faction's turn. Turn-based only.",
        "rule",
        {
            "faction": _p(
                "string",
                True,
                "Your faction (one of: wei, shu, wu).",
                enum=_FACTION_ENUM,
            ),
            "force": _p("bool", False, "Force end turn"),
        },
    ),
    ActionSpec(
        "observation",
        "Request an observation at a named level (unit | faction | limited)",
        "query",
        {
            "observation_level": _p(
                "string",
                False,
                "unit | faction | limited",
            ),
            "faction": _p("string", False, "Required for faction/limited"),
            "unit_id": _p("int", False, "Required for unit"),
        },
    ),
    ActionSpec(
        "limited_observation",
        "Fog-of-war observation for one faction",
        "query",
        {"faction": _p("string", True, "Faction name")},
    ),
    ActionSpec(
        "unit_observation",
        "Observation centered on one unit",
        "query",
        {"unit_id": _p("int", True, "Unit ID")},
    ),
    ActionSpec(
        "faction_observation",
        "Faction-level observation",
        "query",
        {"faction": _p("string", True, "Faction name")},
    ),
    ActionSpec(
        "godview_observation",
        "Omniscient observation",
        "query",
        {},
    ),
)

# Alias so existing "iterate the catalog" tests can keep using ACTIONS.
ACTIONS = GAME_ACTIONS

GAME_ACTION_NAMES = frozenset(spec.name for spec in GAME_ACTIONS)
_SPEC_BY_NAME = {spec.name: spec for spec in GAME_ACTIONS}

_ACTION_TYPE_VALUES = {member.value for member in ActionType}
for _spec in GAME_ACTIONS:
    if _spec.kind == "unit" and _spec.name not in _ACTION_TYPE_VALUES:
        raise RuntimeError(
            f"unit action {_spec.name!r} is not an ActionType value: {_ACTION_TYPE_VALUES}"
        )


def specs_for_names(names: Iterable[str]) -> List[ActionSpec]:
    specs = []
    for name in names:
        spec = _SPEC_BY_NAME.get(name)
        if spec is not None:
            specs.append(spec)
    return specs


def docs_for_names(names: Iterable[str]) -> Dict[str, Any]:
    return {
        spec.name: {
            "description": spec.description,
            "kind": spec.kind,
            "parameters": spec.parameters,
        }
        for spec in specs_for_names(names)
    }


def skirmish_actions(*, turn_based: bool) -> Tuple[str, ...]:
    """Default match subset: the three eval verbs, plus end_turn in turn mode."""
    if turn_based:
        return SKIRMISH_ACTIONS + ("end_turn",)
    return SKIRMISH_ACTIONS


def match_game_actions(
    *, turn_based: bool, extra: Sequence[str] = ()
) -> Tuple[str, ...]:
    """Build a match subset. ``extra`` must already be on the master table."""
    names = list(skirmish_actions(turn_based=turn_based))
    for name in extra:
        if name not in GAME_ACTION_NAMES:
            raise ValueError(
                f"{name!r} is not an implemented game action: {sorted(GAME_ACTION_NAMES)}"
            )
        if name not in names:
            names.append(name)
    return tuple(names)


def _world_is_turn_based(world: Any) -> bool:
    from ..components.gamemode import GameModeComponent

    mode = world.get_singleton_component(GameModeComponent)
    return bool(mode is not None and mode.is_turn_based())


def allowed_game_actions(world: Any = None) -> Tuple[str, ...]:
    """This match's subset.

    Missing ``MatchRules`` follows ``GameModeComponent`` (turn-based adds
    ``end_turn``). No world and no mode fail closed to realtime skirmish.
    Names on ``MatchRules`` that are not on the master table are dropped.
    """
    if world is None:
        return SKIRMISH_ACTIONS
    from ..components.gamemode import MatchRules

    rules = world.get_singleton_component(MatchRules)
    if rules is not None and getattr(rules, "game_actions", None):
        names = tuple(n for n in rules.game_actions if n in GAME_ACTION_NAMES)
        if names:
            return names
    return skirmish_actions(turn_based=_world_is_turn_based(world))


def game_actions_payload(world: Any = None) -> Dict[str, Any]:
    """Join / get_action_list body: this match's names and docs, never the master table."""
    names = allowed_game_actions(world)
    return {
        "names": list(names),
        "docs": docs_for_names(names),
    }


def is_world_mutating(name: str) -> bool:
    """Whether executing ``name`` can change what an observation would see.

    ``get_action_list`` is a system docs read. Unknown names are treated as
    mutating so a successful handler-only verb still invalidates the cache.
    """
    if name == "get_action_list":
        return False
    spec = _SPEC_BY_NAME.get(name)
    if spec is not None:
        return spec.kind != "query"
    return True


__all__ = [
    "ACTIONS",
    "ActionSpec",
    "GAME_ACTIONS",
    "GAME_ACTION_NAMES",
    "SKIRMISH_ACTIONS",
    "allowed_game_actions",
    "docs_for_names",
    "game_actions_payload",
    "is_world_mutating",
    "match_game_actions",
    "skirmish_actions",
    "specs_for_names",
]
