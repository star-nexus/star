"""Turn rotation and end_turn fanout. No hub, no pygame window."""

from framework.ecs.world import World
from framework.engine.events import EBS
from rotk_env.components import (
    ActionPoints,
    GameModeComponent,
    GameState,
    HexPosition,
    MovementPoints,
    Player,
    Unit,
    UnitCount,
)
from rotk_env.components.gamemode import MatchRules
from rotk_env.prefabs.action_catalog import skirmish_actions
from rotk_env.prefabs.config import Faction, GameMode, PlayerType, UnitType
from rotk_env.systems.llm_action_handler import LLMActionHandler
from rotk_env.systems.turn_system import TurnSystem
from rotk_env.utils.env_events import TurnStartEvent


def _add_player(world, faction, color):
    entity = world.create_entity()
    world.add_component(
        entity,
        Player(faction=faction, player_type=PlayerType.AI, color=color),
    )
    return entity


def _spawn_unit(world, faction, col, row, ap=0, mp=0):
    entity = world.create_entity()
    world.add_component(
        entity, Unit(unit_type=UnitType.INFANTRY, faction=faction, name="test")
    )
    world.add_component(entity, HexPosition(col, row))
    world.add_component(entity, UnitCount(current_count=100, max_count=100))
    world.add_component(entity, ActionPoints(current_ap=ap, max_ap=2))
    world.add_component(
        entity, MovementPoints(current_mp=mp, max_mp=4, base_mp=4)
    )
    return entity


def _turn_world():
    world = World()
    world.add_singleton_component(
        GameState(current_player=Faction.WEI, turn_number=1, game_mode=GameMode.TURN_BASED)
    )
    world.add_singleton_component(GameModeComponent(mode=GameMode.TURN_BASED))
    world.add_singleton_component(
        MatchRules(game_actions=skirmish_actions(turn_based=True))
    )
    _add_player(world, Faction.WEI, (0, 0, 255))
    _add_player(world, Faction.SHU, (0, 255, 0))
    wei = _spawn_unit(world, Faction.WEI, 0, 0)
    shu = _spawn_unit(world, Faction.SHU, 1, 0)
    world.add_system(TurnSystem())
    # initialize() advances once (WEI → SHU). Restore WEI as the acting side
    # so rotation tests pin the cycle, not that startup skip.
    world.get_singleton_component(GameState).current_player = Faction.WEI
    world.get_singleton_component(GameState).turn_number = 1
    return world, wei, shu


def test_agent_end_turn_hands_off_to_the_next_faction():
    world, _, _ = _turn_world()
    turn_system = world.systems[0]
    turn_system.agent_end_turn()
    state = world.get_singleton_component(GameState)
    assert state.current_player == Faction.SHU
    assert state.turn_number == 1


def test_full_cycle_increments_round_and_resets_ap_mp():
    world, wei, shu = _turn_world()
    turn_system = world.systems[0]
    world.get_component(wei, ActionPoints).current_ap = 0
    world.get_component(shu, MovementPoints).current_mp = 1

    turn_system.agent_end_turn()
    turn_system.agent_end_turn()

    state = world.get_singleton_component(GameState)
    assert state.current_player == Faction.WEI
    assert state.turn_number == 2
    assert world.get_component(wei, ActionPoints).current_ap == 2
    assert world.get_component(shu, ActionPoints).current_ap == 2
    assert world.get_component(wei, MovementPoints).current_mp == 4
    assert world.get_component(shu, MovementPoints).current_mp == 4


def test_end_turn_publishes_turn_start_for_the_next_faction():
    world, _, _ = _turn_world()
    seen = []

    def _capture(event):
        seen.append(event.faction)

    EBS.subscribe(TurnStartEvent, _capture)
    try:
        seen.clear()
        world.systems[0].agent_end_turn()
        assert seen == [Faction.SHU]
    finally:
        EBS.unsubscribe(TurnStartEvent, _capture)


def test_handle_end_turn_rejects_the_waiting_faction():
    world, _, _ = _turn_world()
    result = LLMActionHandler(world).handle_end_turn({"faction": "shu"})
    assert result["success"] is False
    assert world.get_singleton_component(GameState).current_player == Faction.WEI


def test_handle_end_turn_advances_and_names_the_next_faction():
    world, _, _ = _turn_world()
    result = LLMActionHandler(world).handle_end_turn({"faction": "wei"})
    assert result["success"] is True
    assert result["turn_summary"]["ended_faction"] == "wei"
    assert result["turn_summary"]["next_faction"] == "shu"
    assert result["turn_summary"]["turn_number"] == 1
    assert world.get_singleton_component(GameState).current_player == Faction.SHU


def test_end_turn_is_closed_in_realtime_skirmish():
    world = World()
    world.add_singleton_component(GameModeComponent(mode=GameMode.REAL_TIME))
    result = LLMActionHandler(world).execute_action("end_turn", {"faction": "wei"})
    assert result["success"] is False
    assert result["error_code"] == 2003
