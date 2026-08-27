"""Agent–ENV protocol contract: validators, MUST sequence, no ENV/agent imports."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, Optional

import pytest

from protocol.conformance import (
    ConformanceError,
    expected_game_action_names,
    forbidden_imports,
    register_parameters,
    run_must_sequence,
    validate_join_reply,
    validate_stats_payload,
    zero_llm_stats,
)

ROOT = Path(__file__).resolve().parents[2]
CLIENT_PATHS = (
    ROOT / "protocol" / "conformance.py",
    ROOT / "examples" / "protocol_conformance.py",
)

SAMPLE_DOCS = {
    "move": {
        "description": "Move a unit",
        "parameters": {
            "unit_id": {"type": "int", "required": True},
            "target_position": {
                "type": "object",
                "required": True,
                "properties": {"col": {"type": "int"}, "row": {"type": "int"}},
            },
        },
    },
    "attack": {"description": "Attack", "parameters": {}},
    "get_faction_state": {"description": "Observe", "parameters": {}},
    "end_turn": {"description": "End turn", "parameters": {}},
}


def _join(*, turn_based: bool, **overrides: Any) -> dict[str, Any]:
    names = list(expected_game_action_names(turn_based=turn_based))
    payload: dict[str, Any] = {
        "success": True,
        "map": {
            "width": 15,
            "height": 15,
            "col_min": -7,
            "col_max": 7,
            "row_min": -7,
            "row_max": 7,
            "map_id": "chibi",
            "home_bases": {"wei": {"col": 0, "row": 6, "kind": "home_base"}},
        },
        "game_actions": {
            "names": names,
            "docs": {name: SAMPLE_DOCS[name] for name in names},
        },
    }
    payload.update(overrides)
    return payload


def _imported_modules(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    return names


class FakeSession:
    def __init__(self, *, turn_based: bool = True, join: Optional[dict] = None):
        self.turn_based = turn_based
        self.join = join if join is not None else _join(turn_based=turn_based)
        self.calls: list[tuple[str, dict]] = []

    async def call(self, action: str, parameters: Optional[dict] = None) -> Any:
        params = dict(parameters or {})
        self.calls.append((action, params))
        if action == "register_agent_info":
            return self.join
        if action == "get_faction_state":
            return {
                "success": True,
                "faction": params.get("faction"),
                "units": [],
                "visible_enemy_units": [],
            }
        if action in ("turn_start_ack", "end_turn", "report_llm_stats"):
            return {"success": True}
        raise ConformanceError(f"unexpected action {action}")

    async def wait_push(self, event_type: str, timeout: float = 30.0) -> dict:
        if event_type != "turn_start":
            raise ConformanceError(f"no push {event_type}")
        return {
            "type": "turn_start",
            "faction": "wei",
            "turn_number": 1,
            "timestamp": 0.0,
            "message": "Your turn starts.",
        }


class TestNoEnvOrAgentImport:
    def test_protocol_clients_do_not_import_agent_or_env(self):
        offenders: list[str] = []
        for path in CLIENT_PATHS:
            bad = forbidden_imports(_imported_modules(path))
            offenders.extend(f"{path.relative_to(ROOT)}: {name}" for name in bad)
        assert offenders == []


class TestJoinReply:
    def test_skirmish_realtime_join_is_accepted(self):
        validate_join_reply(_join(turn_based=False), turn_based=False)

    def test_turn_based_join_requires_end_turn(self):
        with pytest.raises(ConformanceError, match="end_turn"):
            validate_join_reply(_join(turn_based=False), turn_based=True)

    def test_realtime_join_rejects_end_turn(self):
        with pytest.raises(ConformanceError, match="end_turn"):
            validate_join_reply(_join(turn_based=True), turn_based=False)

    def test_missing_col_min_is_rejected(self):
        join = _join(turn_based=False)
        del join["map"]["col_min"]
        with pytest.raises(ConformanceError, match="col_min"):
            validate_join_reply(join, turn_based=False)

    def test_missing_move_is_rejected(self):
        join = _join(turn_based=False)
        join["game_actions"]["names"] = ["attack", "get_faction_state"]
        with pytest.raises(ConformanceError, match="move"):
            validate_join_reply(join, turn_based=False)


class TestStatsPayload:
    def test_zero_stats_are_legal(self):
        payload = zero_llm_stats("wei")
        validate_stats_payload(payload, "wei")

    def test_register_parameters_include_env_required_fields(self):
        params = register_parameters("wei", "agent_1")
        assert params["faction"] == "wei"
        assert params["agent_id"] == "agent_1"
        for key in ("provider", "model_id", "base_url"):
            assert params[key]


class TestMustSequence:
    @pytest.mark.asyncio
    async def test_turn_based_full_sequence(self):
        session = FakeSession(turn_based=True)
        passed = await run_must_sequence(
            session,
            faction="wei",
            agent_id="agent_1",
            turn_based=True,
        )
        assert passed == [
            "register_agent_info",
            "get_faction_state",
            "turn_start",
            "turn_start_ack",
            "end_turn",
            "report_llm_stats",
        ]
        assert session.calls[0][0] == "register_agent_info"
        assert session.calls[0][1]["agent_id"] == "agent_1"

    @pytest.mark.asyncio
    async def test_realtime_skips_turn_gate(self):
        session = FakeSession(turn_based=False)
        passed = await run_must_sequence(
            session,
            faction="wei",
            agent_id="agent_1",
            turn_based=False,
        )
        assert passed == [
            "register_agent_info",
            "get_faction_state",
            "report_llm_stats",
        ]
        assert all(name != "end_turn" for name, _ in session.calls)

    @pytest.mark.asyncio
    async def test_live_probe_can_skip_end_turn_and_stats(self):
        session = FakeSession(turn_based=True)
        passed = await run_must_sequence(
            session,
            faction="wei",
            agent_id="agent_1",
            turn_based=True,
            end_turn=False,
            report_stats=False,
        )
        assert passed == [
            "register_agent_info",
            "get_faction_state",
            "turn_start",
            "turn_start_ack",
        ]
