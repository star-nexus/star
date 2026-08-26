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
from typing import Any, Dict, Optional

NOISE_CAPABILITIES = ("attack_points", "construction_points", "skill_points")
NOISE_UNIT_STATE = ("morale", "fatigue")
UNIT_STATE_KEYS = ("unit_status", "status")


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


def _trim_faction_units(units: Any) -> Any:
    if not isinstance(units, list):
        return units
    trimmed = []
    for unit in units:
        if not isinstance(unit, dict):
            continue
        entry = copy.deepcopy(unit)
        _strip_unit_state(entry)
        _strip_capabilities(entry, "long_rest_resources")
        entry.pop("available_skills", None)
        trimmed.append(entry)
    return trimmed


def filter_faction_state_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """Keep own units and visible enemies, minus unimplemented fields."""
    filtered = copy.deepcopy(result)
    filtered.pop("success", None)

    if "units" in filtered:
        filtered["units"] = _trim_faction_units(filtered.get("units"))
    if "visible_enemy_units" in filtered:
        filtered["visible_enemy_units"] = _trim_faction_units(
            filtered.get("visible_enemy_units")
        )

    return filtered


def filter_move_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """On failure keep the diagnosis; on success drop the animation narration."""
    if not result.get("result", True) and "suggested_action" in result:
        essential = {
            "result",
            "details",
            "failure_reason",
            "current_movement_points",
            "required_movement_points",
            "closest_reachable_position",
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
    "get_faction_state": filter_faction_state_result,
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
) -> Any:
    """Route a tool result to the filter matching the action it performed."""
    if not isinstance(result, dict):
        return result

    data = copy.deepcopy(result)
    if function_name == "perform_action":
        action = (tool_arguments or {}).get("action")
        action = action.strip().lower() if isinstance(action, str) else None
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
    "ACTION_FILTERS",
]
