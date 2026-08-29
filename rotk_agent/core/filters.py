"""Trim ENV responses before they enter the conversation history.

These filters exist to save context, not to hide information: they drop fields
the model cannot act on (verbose path descriptions, empty skill lists) and keep
everything needed to make the next decision, including failure diagnostics.

Note on unit state keys: the `observation` action nests unit state under
`status`, while `get_unit_info` and `get_faction_state` use `unit_status`. The
old per-file filters each hardcoded one of the two, so half of them silently
did nothing. These check both.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from typing import Any, Dict, Optional

NOISE_CAPABILITIES = ("attack_points", "construction_points", "skill_points")
NOISE_UNIT_STATE = ("morale", "fatigue")
UNIT_STATE_KEYS = ("unit_status", "status")
DEFAULT_TERRAIN_TYPE = "plain"

# Compact JSON for conversation history: nested hexes stay `[3,4]` on one line.
# `indent=2` would re-expand each coordinate across four lines.
COMPACT_JSON_SEPARATORS = (",", ":")

OWN_UNIT_BASIC_COLUMNS = (
    "id",
    "type",
    "col",
    "row",
    "current_manpower",
    "max_manpower",
    "current_AP",
    "current_MP",
    "attack_range",
    "attack_power",
    "vision_range",
    "defense",
)
ENEMY_UNIT_COLUMNS = ("id", "type", "faction", "col", "row", "current")


@dataclass(frozen=True)
class FactionStateFilterSpec:
    """One ablation pack: which channels to keep, plus the matching decoder.

    Lookup a name in FILTER_PROFILES and use that object for both
    ``filter_faction_state_result`` and the tool-schema description.
    Do not keep a module-level decoder string — it would freeze pack F
    while the data path uses another pack.
    """

    name: str
    reachable: bool
    attackable: bool
    terrain: bool

    @property
    def decoder(self) -> str:
        """How to *read* this pack's payload. No tactical policy."""
        return _compact_decoder_text(self)


# Pack = channels + decoder. Same object drives the transform and the schema.
FILTER_PROFILES = {
    "A": FactionStateFilterSpec(
        "A", reachable=False, attackable=False, terrain=False
    ),
    "B": FactionStateFilterSpec(
        "B", reachable=True, attackable=False, terrain=False
    ),
    "C": FactionStateFilterSpec(
        "C", reachable=False, attackable=True, terrain=False
    ),
    "D": FactionStateFilterSpec(
        "D", reachable=True, attackable=True, terrain=False
    ),
    "E": FactionStateFilterSpec(
        "E", reachable=False, attackable=False, terrain=True
    ),
    "F": FactionStateFilterSpec(
        "F", reachable=True, attackable=True, terrain=True
    ),
}
DEFAULT_FACTION_STATE_FILTER = "F"


def resolve_faction_state_filter(
    name: Optional[str] = None,
) -> FactionStateFilterSpec:
    key = (name or DEFAULT_FACTION_STATE_FILTER).strip().upper()
    try:
        return FILTER_PROFILES[key]
    except KeyError:
        available = ", ".join(sorted(FILTER_PROFILES))
        raise ValueError(
            f"Unknown state filter '{name}'. Available: {available}"
        ) from None


CURRENT_RESOURCE_NOTE = (
    "current_AP and current_MP are the unit's currently available resources "
    "in this snapshot, not maximum values."
)
TERRAIN_OMISSION_NOTE = (
    "terrain is a partial snapshot under fog. A coordinate absent from the "
    "latest terrain object does NOT imply that its terrain changed or became "
    "plain; it may simply be currently unobserved. Do not infer terrain "
    "changes from omission."
)
REACHABLE_MOVE_PROTOCOL = (
    "For every move action, target_position MUST be selected exactly from that "
    "unit's reachable list in the latest get_faction_state result. Do not invent, "
    "estimate, calculate, or substitute another coordinate. If reachable is empty, "
    "that unit currently has no legal move target. Treat reachable as authoritative "
    "for movement legality. Do not override it using your own distance, terrain, "
    "pathfinding, obstacle, or occupancy assumptions. If a coordinate appears in "
    "reachable, it is a legal move target for that unit in this snapshot. When "
    "multiple historical get_faction_state results exist, use the most recent one "
    "for current unit positions, MP, and reachable when issuing actions."
)


def _affordance_anchor_schema(spec: FactionStateFilterSpec) -> str:
    """Named trailing object for action affordances. Empty when the pack has none."""
    fields = []
    if spec.reachable:
        fields.append("reachable:[[col,row],...]")
    if spec.attackable:
        fields.append("attackable:[enemy_id,...]")
    if not fields:
        return ""
    return "{" + ",".join(fields) + "}"


def _compact_decoder_text(spec: FactionStateFilterSpec) -> str:
    """Row-schema decoder for one pack.

    Attached only to the get_faction_state tool description in tools.py —
    do not copy into prompts or $game_actions_block.
    """
    units_schema = ",".join(OWN_UNIT_BASIC_COLUMNS)
    anchor = _affordance_anchor_schema(spec)
    if anchor:
        units_schema = f"{units_schema},{anchor}"

    text = (
        "The result you receive is filtered compact JSON (no extra whitespace), "
        "not the raw ENV object. "
        "state; fog; counts=[total,alive,actionable]; "
        f"units=[{units_schema}]"
    )
    text += f"; enemies=[{','.join(ENEMY_UNIT_COLUMNS)}]"
    if spec.terrain:
        text += (
            "; terrain={type:[[col,row],...]} currently visible non-plain "
            "hexes only; unlisted hexes may be visible plain or currently unknown"
        )
    else:
        text += "; no terrain key"
    text += "."
    text += " " + CURRENT_RESOURCE_NOTE
    if spec.terrain:
        text += " " + TERRAIN_OMISSION_NOTE
    if spec.reachable:
        text += " " + REACHABLE_MOVE_PROTOCOL
    return text


def dumps_for_agent(data: Any) -> str:
    """Serialize a filtered tool result for the conversation history."""
    if isinstance(data, str):
        return data
    return json.dumps(data, ensure_ascii=False, separators=COMPACT_JSON_SEPARATORS)


def _strip_unit_state(container: Dict[str, Any]) -> None:
    """Drop unactionable unit state, under whichever key the ENV used."""
    for key in UNIT_STATE_KEYS:
        state = container.get(key)
        if isinstance(state, dict):
            for noise in NOISE_UNIT_STATE:
                state.pop(noise, None)


def _strip_capabilities(container: Dict[str, Any], *extra: str) -> None:
    capabilities = container.get("capabilities")
    if isinstance(capabilities, dict):
        for noise in NOISE_CAPABILITIES + extra:
            capabilities.pop(noise, None)


def filter_observation_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """Keep position, terrain, occupants, reachability, and attackability."""
    filtered = copy.deepcopy(result)

    unit_info = filtered.get("unit_info")
    if isinstance(unit_info, dict):
        _strip_unit_state(unit_info)
        _strip_capabilities(unit_info)
        unit_info.pop("available_skills", None)

    environment = filtered.get("visible_environment")
    if isinstance(environment, list):
        trimmed = []
        for tile in environment:
            if not isinstance(tile, dict):
                continue
            entry = {
                "position": tile.get("position"),
                "terrain": tile.get("terrain"),
                "units": tile.get("units", []),
            }

            movement = tile.get("movement_accessibility")
            if isinstance(movement, dict) and "reachable" in movement:
                entry["reachable"] = movement["reachable"]

            attack = tile.get("attack_range_info")
            if isinstance(attack, dict) and "in_attack_range" in attack:
                entry["attackable"] = attack["in_attack_range"]
            elif isinstance(attack, bool):
                entry["attackable"] = attack

            trimmed.append(entry)
        filtered["visible_environment"] = trimmed

    return filtered


def _col_row(point: Any) -> Optional[list]:
    """Turn a {col,row} object (or already-compact pair) into [col, row]."""
    if isinstance(point, dict):
        if "col" in point or "row" in point:
            return [point.get("col"), point.get("row")]
        position = point.get("position")
        if isinstance(position, dict):
            return [position.get("col"), position.get("row")]
        return None
    if isinstance(point, (list, tuple)) and len(point) >= 2:
        return [point[0], point[1]]
    return None


def _compact_hexes(points: Any) -> Any:
    """ENV reachable tiles → [[col, row], ...], same order, no recomputation."""
    if not isinstance(points, list):
        return [] if points is None else points
    compact = []
    for point in points:
        pair = _col_row(point)
        if pair is not None:
            compact.append(pair)
    return compact


def _own_unit_basic_values(unit: Dict[str, Any]) -> Dict[str, Any]:
    """Map decoder column names to ENV fields. Order comes from OWN_UNIT_BASIC_COLUMNS."""
    position = unit.get("position") or {}
    status = unit.get("unit_status") or unit.get("status") or {}
    capabilities = unit.get("capabilities") or {}
    properties = capabilities.get("properties") or {}
    resources = capabilities.get("unit_resources") or {}
    return {
        "id": unit.get("unit_id"),
        "type": unit.get("unit_type"),
        "col": position.get("col"),
        "row": position.get("row"),
        "current_manpower": status.get("current_count"),
        "max_manpower": status.get("max_count"),
        "current_AP": resources.get("remaining_action_points"),
        "current_MP": resources.get("remaining_movement_points"),
        "attack_range": properties.get("attack_range"),
        "attack_power": properties.get("attack_power"),
        "vision_range": properties.get("vision_range"),
        "defense": properties.get("defense"),
    }


def _compact_own_units(units: Any, spec: FactionStateFilterSpec) -> Any:
    """Serialize friendly units as observation columns plus an affordance anchor.

    Columns follow OWN_UNIT_BASIC_COLUMNS. When the pack enables reachable
    and/or attackable, those go in one trailing object so the decoder can name
    them; disabled channels are omitted, not emptied.
    """
    if not isinstance(units, list):
        return units

    rows = []
    for unit in units:
        if not isinstance(unit, dict):
            continue

        values = _own_unit_basic_values(unit)
        row = [values[col] for col in OWN_UNIT_BASIC_COLUMNS]
        affordance: Dict[str, Any] = {}
        if spec.reachable:
            affordance["reachable"] = _compact_hexes(unit.get("reachable"))
        if spec.attackable:
            attackable = unit.get("attackable")
            affordance["attackable"] = (
                list(attackable) if isinstance(attackable, list) else []
            )
        if affordance:
            row.append(affordance)
        rows.append(row)

    return rows


def _enemy_unit_values(unit: Dict[str, Any]) -> Dict[str, Any]:
    position = unit.get("position") or {}
    status = unit.get("unit_status") or unit.get("status") or {}
    return {
        "id": unit.get("unit_id"),
        "type": unit.get("unit_type"),
        "faction": unit.get("faction"),
        "col": position.get("col"),
        "row": position.get("row"),
        "current": status.get("current_count"),
    }


def _compact_enemy_units(units: Any) -> Any:
    """Serialize visible enemy units as fixed-order rows (ENEMY_UNIT_COLUMNS)."""
    if not isinstance(units, list):
        return units

    rows = []
    for unit in units:
        if not isinstance(unit, dict):
            continue
        values = _enemy_unit_values(unit)
        rows.append([values[col] for col in ENEMY_UNIT_COLUMNS])

    return rows


def _compact_terrain(tiles: Any) -> Any:
    """Group currently visible non-plain terrain by type.

    Plains are omitted to save space. A missing hex is therefore either a
    visible plain or outside current vision — not "plain by default".
    """
    if not isinstance(tiles, list):
        return tiles

    grouped: Dict[str, list] = {}
    for tile in tiles:
        pair = _col_row(tile)
        if pair is None or not isinstance(tile, dict):
            continue
        kind = tile.get("type", tile.get("terrain"))
        if not isinstance(kind, str) or kind == DEFAULT_TERRAIN_TYPE:
            continue
        grouped.setdefault(kind, []).append(pair)
    return grouped


def filter_faction_state_result(
    result: Dict[str, Any],
    spec: FactionStateFilterSpec,
) -> Dict[str, Any]:
    """Whitelist get_faction_state into the compact decision-state schema.

    Failures (success or result is false) pass through so the model still sees
    the ENV diagnosis. Success is rebuilt from scratch: no leftover keys.
    Optional channels follow ``spec`` — callers must pass a FILTER_PROFILES
    entry so the transform cannot silently fall back to pack F.
    """
    if result.get("success") is False or result.get("result") is False:
        return result

    filtered: Dict[str, Any] = {}

    if "state" in result:
        filtered["state"] = result["state"]
    if "fog" in result:
        filtered["fog"] = result["fog"]

    if any(
        key in result
        for key in ("total_units", "alive_units", "actionable_units")
    ):
        filtered["counts"] = [
            result.get("total_units"),
            result.get("alive_units"),
            result.get("actionable_units"),
        ]

    if "units" in result:
        filtered["units"] = _compact_own_units(result["units"], spec)

    if "visible_enemy_units" in result:
        filtered["enemies"] = _compact_enemy_units(result["visible_enemy_units"])

    if spec.terrain and "visible_terrain" in result:
        filtered["terrain"] = _compact_terrain(result["visible_terrain"])

    return filtered


def filter_move_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """On failure keep the diagnosis; on success drop the animation narration."""
    if not result.get("result", True) and (
        "suggested_action" in result
        or result.get("failure_reason") == "insufficient_movement_points"
    ):
        essential = {
            "result",
            "details",
            "reason",
            "failure_reason",
            "current_movement_points",
            "required_movement_points",
            "path",
            "terrain_costs",
            "closest_reachable_position",
            "farthest_reachable_on_path",
            "suggested_action",
            "suggestion",
        }
        return {k: v for k, v in result.items() if k in essential}

    try:
        filtered = dict(result)
        for key in ("success", "message", "movement_descriptions", "action_status"):
            filtered.pop(key, None)
        return filtered
    except Exception:
        return result


def filter_attack_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """On success keep the combat outcome; on failure keep the whole error."""
    if not result.get("result", True):
        return result

    filtered: Dict[str, Any] = {
        "result": result.get("result"),
        "remaining_resources": result.get("remaining_resources"),
    }

    battle_summary = result.get("battle_summary")
    if isinstance(battle_summary, dict):
        summary: Dict[str, Any] = {}

        for side in ("attacker_info", "target_info"):
            info = battle_summary.get(side)
            if isinstance(info, dict):
                summary[side] = {
                    k: info[k]
                    for k in ("unit_id", "unit_type", "faction", "position", "terrain")
                    if k in info
                }

        battle_result = battle_summary.get("battle_result")
        if isinstance(battle_result, dict):
            summary["battle_result"] = {
                k: battle_result[k]
                for k in (
                    "is_critical",
                    "damage_dealt",
                    "target_destroyed",
                    "terrain_effects",
                    "combat_log",
                )
                if k in battle_result
            }

        filtered["battle_summary"] = summary

    tactical = result.get("tactical_info")
    if isinstance(tactical, dict):
        if "attack_was_effective" in tactical:
            filtered["attack_was_effective"] = tactical["attack_was_effective"]
        if "target_strength_percentage" in tactical:
            filtered["target_remaining_manpower"] = (
                f"{tactical['target_strength_percentage']}%"
            )

    return filtered


ACTION_FILTERS = {
    "move": filter_move_result,
    "attack": filter_attack_result,
    "observation": filter_observation_result,
    # get_faction_state is not here: it needs the pack spec. filter_tool_result
    # calls filter_faction_state_result(data, spec) directly.
}


def replace_booleans_with_strings(data: Any) -> Any:
    """Render JSON booleans as "true"/"false" strings, recursively.

    Some models (notably the GPT-OSS family behind the Responses API) echo
    JSON booleans back as tool arguments the ENV then rejects. Stringifying
    them in tool results keeps the model from copying the bare literal.
    """
    if isinstance(data, bool):
        return "true" if data else "false"
    if isinstance(data, dict):
        return {k: replace_booleans_with_strings(v) for k, v in data.items()}
    if isinstance(data, list):
        return [replace_booleans_with_strings(v) for v in data]
    return data


def filter_tool_result(
    function_name: str,
    result: Any,
    tool_arguments: Optional[Dict[str, Any]] = None,
    booleans_as_strings: bool = False,
    faction_state_spec: Optional[FactionStateFilterSpec] = None,
) -> Any:
    """Route a tool result to the filter matching the action it performed."""
    if not isinstance(result, dict):
        return result

    spec = faction_state_spec
    data = copy.deepcopy(result)
    if function_name == "perform_action":
        action = (tool_arguments or {}).get("action")
        action = action.strip().lower() if isinstance(action, str) else None
        if action == "get_faction_state":
            if spec is None:
                raise TypeError(
                    "get_faction_state requires a FILTER_PROFILES spec; "
                    "pass faction_state_spec so data and decoder stay paired"
                )
            data = filter_faction_state_result(data, spec)
        else:
            handler = ACTION_FILTERS.get(action)
            if handler is not None:
                data = handler(data)

    return replace_booleans_with_strings(data) if booleans_as_strings else data


__all__ = [
    "filter_observation_result",
    "filter_faction_state_result",
    "filter_move_result",
    "filter_attack_result",
    "filter_tool_result",
    "replace_booleans_with_strings",
    "dumps_for_agent",
    "resolve_faction_state_filter",
    "FILTER_PROFILES",
    "DEFAULT_FACTION_STATE_FILTER",
    "FactionStateFilterSpec",
    "CURRENT_RESOURCE_NOTE",
    "TERRAIN_OMISSION_NOTE",
    "REACHABLE_MOVE_PROTOCOL",
    "ACTION_FILTERS",
]
