"""Master table + match subset; ActionExecutor firewall."""

from rotk_env.prefabs.action_catalog import (
    ACTIONS,
    GAME_ACTION_NAMES,
    GAME_ACTIONS,
    SKIRMISH_ACTIONS,
    allowed_game_actions,
    docs_for_names,
    game_actions_payload,
    is_world_mutating,
    match_game_actions,
    skirmish_actions,
)
from rotk_env.prefabs.config import ActionType, GameMode
from rotk_env.components.gamemode import GameModeComponent, MatchRules
from rotk_env.systems.llm_action_handler import LLMActionHandler
from rotk_env.systems.llm_system import ActionExecutor, ActionRequest, LLMSystem
from framework import World


def test_skirmish_is_the_three_eval_verbs():
    assert SKIRMISH_ACTIONS == ("move", "attack", "get_faction_state")
    assert skirmish_actions(turn_based=False) == SKIRMISH_ACTIONS
    assert skirmish_actions(turn_based=True) == SKIRMISH_ACTIONS + ("end_turn",)


def test_unit_catalog_names_are_action_types():
    values = {member.value for member in ActionType}
    for spec in ACTIONS:
        if spec.kind == "unit":
            assert spec.name in values


def test_unimplemented_enums_are_not_on_the_master_table():
    for name in ("defend", "scout", "retreat"):
        assert name not in GAME_ACTION_NAMES


def test_get_action_list_is_not_a_game_verb():
    assert "get_action_list" not in GAME_ACTION_NAMES


def test_get_action_list_returns_this_match_only():
    world = World()
    world.add_singleton_component(
        MatchRules(game_actions=skirmish_actions(turn_based=True))
    )
    gate = LLMSystem(server_url=None)
    world.add_system(gate)
    result = gate.handle_action_list({})
    assert result["success"] is True
    assert "profile" not in result
    assert result["names"] == list(skirmish_actions(turn_based=True))
    assert set(result["actions"]) == set(result["names"])
    assert "occupy" not in result["actions"]
    assert "godview_observation" not in result["actions"]
    assert result["actions"] == docs_for_names(result["names"])


def test_profile_upgrade_does_not_widen_the_subset():
    world = World()
    world.add_singleton_component(MatchRules(game_actions=SKIRMISH_ACTIONS))
    gate = LLMSystem(server_url=None)
    world.add_system(gate)
    result = gate.handle_action_list({"profile": "full"})
    assert "occupy" not in result["actions"]
    assert set(result["names"]) == set(SKIRMISH_ACTIONS)


def test_guessed_names_are_unknown():
    class _FakeLLM:
        world = None
        system_actions = {}
        action_handler = type("H", (), {"action_handlers": {}})()

        def _create_system_error_response(self, action, msg, code):
            return {"success": False, "message": msg, "error_code": code}

    result = ActionExecutor(_FakeLLM()).execute(
        ActionRequest(None, 1, "get_map_info", {}, 0.0)
    )
    assert result["success"] is False
    assert result["error_code"] == 2010
    defend = ActionExecutor(_FakeLLM()).execute(
        ActionRequest(None, 2, "defend", {}, 0.0)
    )
    assert defend["error_code"] == 2010


def test_master_but_not_in_match_is_2003():
    class _FakeLLM:
        world = None
        system_actions = {}
        action_handler = type("H", (), {"action_handlers": {"occupy": True}})()

        def _create_system_error_response(self, action, msg, code):
            return {"success": False, "message": msg, "error_code": code}

        def execute_action(self, action, params):
            raise AssertionError(f"must not run {action}")

    fake = _FakeLLM()
    fake.action_handler.execute_action = fake.execute_action
    occupy = ActionExecutor(fake).execute(ActionRequest(None, 1, "occupy", {}, 0.0))
    assert occupy["error_code"] == 2003
    god = ActionExecutor(fake).execute(
        ActionRequest(None, 2, "godview_observation", {}, 0.0)
    )
    assert god["error_code"] == 2003


def test_catalog_mutating_vs_read():
    assert is_world_mutating("move")
    assert is_world_mutating("attack")
    assert is_world_mutating("end_turn")
    assert not is_world_mutating("get_faction_state")
    assert not is_world_mutating("get_action_list")
    assert not is_world_mutating("unit_observation")
    assert not is_world_mutating("godview_observation")


def test_mutating_action_bumps_world_revision():
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

    executor = ActionExecutor(_FakeLLM(world))
    before = world.revision
    executor.execute(ActionRequest(None, 1, "move", {}, 0.0))
    assert world.revision == before + 1
    after_move = world.revision
    executor.execute(
        ActionRequest(None, 2, "get_faction_state", {"faction": "wei"}, 0.0)
    )
    assert world.revision == after_move


def test_2003_does_not_bump_revision():
    world = World()

    class _FakeLLM:
        def __init__(self, world):
            self.world = world
            self.system_actions = {}
            self.action_handler = type("H", (), {"action_handlers": {"occupy": True}})()

        def _create_system_error_response(self, action, msg, code):
            return {"success": False, "message": msg, "error_code": code}

    executor = ActionExecutor(_FakeLLM(world))
    before = world.revision
    result = executor.execute(ActionRequest(None, 1, "occupy", {}, 0.0))
    assert result["error_code"] == 2003
    assert world.revision == before


def test_every_game_action_has_a_handler():
    handler = LLMActionHandler(World())
    for spec in GAME_ACTIONS:
        assert spec.name in handler.action_handlers, spec.name
    assert "defend" not in handler.action_handlers
    assert "get_action_list" not in handler.action_handlers


def test_missing_match_rules_follow_game_mode():
    assert allowed_game_actions(None) == SKIRMISH_ACTIONS
    assert allowed_game_actions(World()) == SKIRMISH_ACTIONS
    payload = game_actions_payload(World())
    assert payload["names"] == list(SKIRMISH_ACTIONS)
    assert "occupy" not in payload["docs"]

    turn_world = World()
    turn_world.add_singleton_component(GameModeComponent(mode=GameMode.TURN_BASED))
    assert allowed_game_actions(turn_world) == SKIRMISH_ACTIONS + ("end_turn",)

    realtime_world = World()
    realtime_world.add_singleton_component(GameModeComponent(mode=GameMode.REAL_TIME))
    assert allowed_game_actions(realtime_world) == SKIRMISH_ACTIONS


def test_match_rules_drop_names_off_the_master_table():
    world = World()
    world.add_singleton_component(MatchRules(game_actions=("move", "defend", "occupy")))
    assert allowed_game_actions(world) == ("move", "occupy")


def test_execute_action_does_not_leak_the_master_table():
    result = LLMActionHandler(World()).execute_action("defend", {})
    assert result["success"] is False
    assert result["error_code"] == 2010
    assert "supported_actions" not in result
    blob = str(result)
    assert "occupy" not in blob
    assert "godview_observation" not in blob


def test_execute_action_enforces_the_match_subset():
    result = LLMActionHandler(World()).execute_action("occupy", {})
    assert result["error_code"] == 2003


def test_match_game_actions_can_opt_in_implemented_verbs():
    names = match_game_actions(turn_based=False, extra=("occupy",))
    assert names == SKIRMISH_ACTIONS + ("occupy",)


def test_move_docs_spend_mp_not_ap():
    docs = docs_for_names(("move", "attack", "get_faction_state"))
    move = docs["move"]["description"]
    assert "MP" in move
    assert "does not spend action points" in move
    assert "until AP is exhausted" not in move
    assert "until AP is exhausted" in docs["attack"]["description"]
    faction_state = docs["get_faction_state"]["description"]
    assert "fog off (key 1)" in faction_state
    assert "visible_terrain" in faction_state
    assert "overlay" not in faction_state
    assert docs["get_faction_state"]["parameters"]["faction"]["enum"] == [
        "wei",
        "shu",
        "wu",
    ]


def test_occupy_and_fortify_docs_include_col_row():
    docs = docs_for_names(("occupy", "fortify"))
    for name in ("occupy", "fortify"):
        position = docs[name]["parameters"]["position"]
        assert position["properties"]["col"]["type"] == "int"
        assert position["properties"]["row"]["type"] == "int"
