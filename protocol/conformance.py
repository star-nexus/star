"""Agent–ENV protocol contract helpers.

Custom agents implement ``docs/agent-protocol.md`` with ``protocol.AgentClient``.
This module does not import ``rotk_agent`` or ``rotk_env``.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional, Protocol, Sequence, runtime_checkable

SKIRMISH_ACTION_NAMES: tuple[str, ...] = ("move", "attack", "get_faction_state")
TURN_BASED_EXTRA: tuple[str, ...] = ("end_turn",)
REGISTER_REQUIRED: tuple[str, ...] = ("faction", "provider", "model_id", "base_url")
MAP_BOUND_KEYS: tuple[str, ...] = ("col_min", "col_max", "row_min", "row_max")
API_STATS_KEYS: tuple[str, ...] = (
    "total_calls",
    "successful_calls",
    "failed_calls",
    "success_rate",
    "prompt_tokens",
    "completion_tokens",
    "reasoning_tokens",
    "prompt_cache_hit_tokens",
    "prompt_cache_miss_tokens",
    "cache_hit_rate",
)
STATS_TOP_KEYS: tuple[str, ...] = (
    "faction",
    "api_stats",
    "toolcall_error_total",
    "http_error_total",
    "spatial_awareness_error",
    "provider",
    "model_id",
)


class ConformanceError(Exception):
    """The agent–ENV contract was violated."""


@runtime_checkable
class AgentSession(Protocol):
    """Minimal session the MUST sequence needs: request/reply plus ENV pushes."""

    async def call(
        self, action: str, parameters: Optional[Mapping[str, Any]] = None
    ) -> Any: ...

    async def wait_push(self, event_type: str, timeout: float = 30.0) -> dict: ...


def register_parameters(
    faction: str,
    agent_id: str,
    *,
    provider: str = "custom",
    model_id: str = "custom",
    base_url: str = "http://localhost",
) -> dict[str, Any]:
    """Join payload. ``base_url`` is required by ENV even for non-LLM agents."""
    return {
        "faction": faction,
        "provider": provider,
        "model_id": model_id,
        "base_url": base_url,
        "agent_id": agent_id,
        "note": "protocol conformance",
    }


def zero_llm_stats(
    faction: str,
    *,
    provider: str = "custom",
    model_id: str = "custom",
) -> dict[str, Any]:
    """Legal ``report_llm_stats`` body for a non-LLM agent."""
    return {
        "faction": faction,
        "api_stats": {key: 0.0 if "rate" in key else 0 for key in API_STATS_KEYS},
        "toolcall_error_total": 0,
        "http_error_total": 0,
        "spatial_awareness_error": 0,
        "provider": provider,
        "model_id": model_id,
    }


def require_success(result: Any, step: str) -> dict[str, Any]:
    if not isinstance(result, dict):
        raise ConformanceError(f"{step}: expected an object outcome, got {type(result).__name__}")
    if result.get("success") is not True:
        raise ConformanceError(
            f"{step}: expected success=true, got {result.get('message') or result}"
        )
    return result


def _require_int(container: Mapping[str, Any], key: str, where: str) -> int:
    value = container.get(key)
    if type(value) is not int:
        raise ConformanceError(f"{where}: {key} must be an int, got {value!r}")
    return value


def expected_game_action_names(*, turn_based: bool) -> tuple[str, ...]:
    if turn_based:
        return SKIRMISH_ACTION_NAMES + TURN_BASED_EXTRA
    return SKIRMISH_ACTION_NAMES


def validate_join_reply(result: Any, *, turn_based: bool) -> dict[str, Any]:
    """Join reply MUST carry map bounds and this match's ``game_actions``."""
    payload = require_success(result, "register_agent_info")
    map_sheet = payload.get("map")
    if not isinstance(map_sheet, dict):
        raise ConformanceError("register_agent_info: missing map object")
    for key in MAP_BOUND_KEYS:
        _require_int(map_sheet, key, "register_agent_info.map")
    if map_sheet["col_min"] > map_sheet["col_max"]:
        raise ConformanceError("register_agent_info.map: col_min > col_max")
    if map_sheet["row_min"] > map_sheet["row_max"]:
        raise ConformanceError("register_agent_info.map: row_min > row_max")

    game_actions = payload.get("game_actions")
    if not isinstance(game_actions, dict):
        raise ConformanceError("register_agent_info: missing game_actions object")
    names = game_actions.get("names")
    if not isinstance(names, list) or not all(isinstance(n, str) for n in names):
        raise ConformanceError("register_agent_info.game_actions.names must be a list of strings")
    name_set = set(names)
    missing = [n for n in SKIRMISH_ACTION_NAMES if n not in name_set]
    if missing:
        raise ConformanceError(
            f"register_agent_info.game_actions.names missing skirmish verbs: {missing}"
        )
    if turn_based and "end_turn" not in name_set:
        raise ConformanceError("turn-based join must list end_turn in game_actions.names")
    if not turn_based and "end_turn" in name_set:
        raise ConformanceError("real-time join must not list end_turn")
    docs = game_actions.get("docs")
    if not isinstance(docs, dict):
        raise ConformanceError("register_agent_info.game_actions.docs must be an object")
    return payload


def validate_faction_state(result: Any, faction: str) -> dict[str, Any]:
    payload = require_success(result, "get_faction_state")
    if payload.get("faction") != faction:
        raise ConformanceError(
            f"get_faction_state: faction {payload.get('faction')!r} != {faction!r}"
        )
    if not isinstance(payload.get("units"), list):
        raise ConformanceError("get_faction_state: units must be a list")
    return payload


def validate_turn_start(event: Any, faction: str) -> dict[str, Any]:
    if not isinstance(event, dict) or event.get("type") != "turn_start":
        raise ConformanceError(f"expected turn_start push, got {event!r}")
    if event.get("faction") != faction:
        raise ConformanceError(
            f"turn_start faction {event.get('faction')!r} != {faction!r}"
        )
    return event


def validate_stats_payload(params: Mapping[str, Any], faction: str) -> None:
    missing = [key for key in STATS_TOP_KEYS if key not in params]
    if missing:
        raise ConformanceError(f"report_llm_stats missing fields: {missing}")
    if params.get("faction") != faction:
        raise ConformanceError("report_llm_stats faction does not match the session")
    api_stats = params.get("api_stats")
    if not isinstance(api_stats, dict):
        raise ConformanceError("report_llm_stats.api_stats must be an object")
    for key in API_STATS_KEYS:
        if key not in api_stats:
            raise ConformanceError(f"report_llm_stats.api_stats missing {key}")


async def run_must_sequence(
    session: AgentSession,
    *,
    faction: str,
    agent_id: str,
    turn_based: bool,
    wait_turn_timeout: float = 30.0,
    end_turn: bool = True,
    report_stats: bool = True,
) -> list[str]:
    """Drive the MUST sequence against any ``AgentSession``.

    Live probes may set ``end_turn`` / ``report_stats`` false so they do not
    steal a faction's turn or trip settlement on a running evaluation.
    """
    passed: list[str] = []
    join = await session.call(
        "register_agent_info",
        register_parameters(faction, agent_id),
    )
    validate_join_reply(join, turn_based=turn_based)
    passed.append("register_agent_info")

    state = await session.call("get_faction_state", {"faction": faction})
    validate_faction_state(state, faction)
    passed.append("get_faction_state")

    if turn_based:
        event = await session.wait_push("turn_start", timeout=wait_turn_timeout)
        validate_turn_start(event, faction)
        passed.append("turn_start")
        ack = await session.call("turn_start_ack", {})
        require_success(ack, "turn_start_ack")
        passed.append("turn_start_ack")
        if end_turn:
            ended = await session.call("end_turn", {"faction": faction})
            require_success(ended, "end_turn")
            passed.append("end_turn")

    if report_stats:
        stats = zero_llm_stats(faction)
        validate_stats_payload(stats, faction)
        reported = await session.call("report_llm_stats", stats)
        require_success(reported, "report_llm_stats")
        passed.append("report_llm_stats")

    return passed


def forbidden_imports(tree_names: Sequence[str]) -> list[str]:
    """Return import names that a protocol client must not use."""
    bad: list[str] = []
    for name in tree_names:
        if name == "rotk_agent" or name.startswith("rotk_agent."):
            bad.append(name)
        elif name == "rotk_env" or name.startswith("rotk_env."):
            bad.append(name)
    return bad
