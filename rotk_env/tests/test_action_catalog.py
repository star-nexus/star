"""Prefab action catalog: ActionType views plus LLM query/meta verbs."""

from rotk_env.prefabs.action_catalog import (
    ACTIONS,
    BENCH,
    DEBUG,
    FULL,
    action_names,
    docs_for,
    is_observation,
    is_world_mutating,
)
from rotk_env.prefabs.config import ActionType
from rotk_agent.core.tools import PERFORM_ACTION_SCHEMA, perform_action_schema
from rotk_env.systems.llm_action_handler import LLMActionHandler
from framework import World


def test_bench_is_the_three_eval_verbs():
    assert action_names(BENCH) == frozenset(
        {"move", "attack", "get_faction_state"}
    )


def test_unit_catalog_names_are_action_types():
    values = {member.value for member in ActionType}
    for spec in ACTIONS:
        if spec.kind == "unit":
            assert spec.name in values


def test_agent_schema_enum_is_generated_from_bench():
    assert set(PERFORM_ACTION_SCHEMA["properties"]["action"]["enum"]) == set(
        action_names(BENCH)
    )
    full_schema = perform_action_schema(FULL)
    assert "occupy" in full_schema["properties"]["action"]["enum"]
    assert "skill" in full_schema["properties"]["action"]["enum"]
    assert "godview_observation" not in full_schema["properties"]["action"]["enum"]


def test_get_action_list_is_generated_from_the_same_catalog():
    handler = LLMActionHandler(World())
    bench = handler.handle_action_list({})
    assert bench["profile"] == BENCH
    assert set(bench["actions"]) == action_names(BENCH)
    assert bench["actions"] == docs_for(BENCH)

    full = handler.handle_action_list({"profile": "full"})
    assert set(full["actions"]) == action_names(FULL)
    assert "occupy" in full["actions"]
    assert "godview_observation" not in full["actions"]


def test_unknown_get_prefix_is_not_an_observation():
    assert not is_observation("get_map_info")
    assert not is_observation("get_foo")
    assert is_observation("limited_observation")
    assert is_observation("godview_observation")
    assert "godview_observation" not in action_names(FULL)
    assert "godview_observation" in action_names(DEBUG)


def test_guessed_observation_names_fail_closed():
    from rotk_env.systems.llm_system import ActionExecutor, ActionRequest

    class _FakeLLM:
        world = None
        system_actions = {}
        action_handler = type("H", (), {"action_handlers": {}})()

        def _create_system_error_response(self, action, msg, code):
            return {"success": False, "message": msg, "error_code": code}

        def _handle_observation_action(self, action, params):
            raise AssertionError(f"must not route {action}")

    result = ActionExecutor(_FakeLLM()).execute(
        ActionRequest(None, 1, "get_map_info", {}, 0.0)
    )
    assert result["success"] is False
    assert result["error_code"] == 2010
    god = ActionExecutor(_FakeLLM()).execute(
        ActionRequest(None, 2, "godview_observation", {}, 0.0)
    )
    assert god["success"] is False
    assert god["error_code"] == 2010


def test_catalog_mutating_vs_read():
    assert is_world_mutating("move")
    assert is_world_mutating("attack")
    assert is_world_mutating("end_turn")
    assert not is_world_mutating("get_faction_state")
    assert not is_world_mutating("get_action_list")
    assert not is_world_mutating("unit_observation")


def test_mutating_action_bumps_world_revision():
    from rotk_env.systems.llm_system import ActionExecutor, ActionRequest

    world = World()

    class _Handler:
        action_handlers = {"move": True, "get_faction_state": True}

        def execute_action(self, action, params):
            return {"success": True}

    class _FakeLLM:
        def __init__(self, world):
            self.world = world
            self.system_actions = {}
            self.action_handler = _Handler()

        def _create_system_error_response(self, action, msg, code):
            return {"success": False, "message": msg, "error_code": code}

        def _handle_observation_action(self, action, params):
            raise AssertionError("not an observation")

    executor = ActionExecutor(_FakeLLM(world))
    before = world.revision
    executor.execute(ActionRequest(None, 1, "move", {}, 0.0))
    assert world.revision == before + 1
    after_move = world.revision
    executor.execute(
        ActionRequest(None, 2, "get_faction_state", {"faction": "wei"}, 0.0)
    )
    assert world.revision == after_move
