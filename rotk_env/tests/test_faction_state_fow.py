"""get_faction_state matches the screen: own army plus currently visible enemies."""

from framework.ecs.world import World
from rotk_env.components import (
    FogOfWar,
    GameStats,
    HexPosition,
    Unit,
    UnitCount,
    UIState,
)
from rotk_env.prefabs.config import Faction, UnitType
from rotk_env.systems.llm_action_handler import LLMActionHandler


def _world():
    world = World()
    world.add_singleton_component(UIState())
    world.add_singleton_component(FogOfWar(enabled=True))
    world.add_singleton_component(GameStats())
    return world


def _spawn(world, *, faction, col, row, count=100, unit_type=UnitType.INFANTRY):
    entity = world.create_entity()
    world.add_component(
        entity, Unit(unit_type=unit_type, faction=faction, name="test")
    )
    world.add_component(entity, HexPosition(col, row))
    world.add_component(entity, UnitCount(current_count=count, max_count=100))
    return entity


def test_own_army_is_complete_and_enemies_use_vision_when_fog_on():
    world = _world()
    own = _spawn(world, faction=Faction.WEI, col=0, row=0)
    seen = _spawn(world, faction=Faction.SHU, col=1, row=0, unit_type=UnitType.CAVALRY)
    hidden = _spawn(world, faction=Faction.SHU, col=5, row=5, count=40)

    fog = world.get_singleton_component(FogOfWar)
    fog.faction_vision[Faction.WEI] = {(0, 0), (1, 0)}

    result = LLMActionHandler(world).handle_faction_state({"faction": "wei"})
    assert result["success"] is True
    assert result["fog"] == "active"
    assert result["alive_units"] == 1
    assert [u["unit_id"] for u in result["units"]] == [own]
    assert "capabilities" in result["units"][0]

    visible_ids = {e["unit_id"] for e in result["visible_enemy_units"]}
    assert visible_ids == {seen}
    assert hidden not in visible_ids
    enemy = result["visible_enemy_units"][0]
    assert enemy["unit_type"] == "cavalry"
    assert enemy["position"] == {"col": 1, "row": 0}
    assert enemy["unit_status"] == {"current_count": 100}
    assert "capabilities" not in enemy
    assert "commandable" not in enemy


def test_fog_off_returns_every_living_enemy():
    world = _world()
    _spawn(world, faction=Faction.WEI, col=0, row=0)
    near = _spawn(world, faction=Faction.SHU, col=1, row=0)
    far = _spawn(world, faction=Faction.SHU, col=8, row=8, count=55)
    dead = _spawn(world, faction=Faction.SHU, col=2, row=0, count=0)

    ui = world.get_singleton_component(UIState)
    fog = world.get_singleton_component(FogOfWar)
    ui.god_mode = True
    fog.enabled = False

    result = LLMActionHandler(world).handle_faction_state({"faction": "wei"})
    assert result["fog"] == "disabled"
    visible_ids = {e["unit_id"] for e in result["visible_enemy_units"]}
    assert visible_ids == {near, far}
    assert dead not in visible_ids
    by_id = {e["unit_id"]: e for e in result["visible_enemy_units"]}
    assert by_id[far]["unit_status"]["current_count"] == 55


def test_god_mode_alone_lifts_fog_for_the_query():
    world = _world()
    _spawn(world, faction=Faction.WEI, col=0, row=0)
    far = _spawn(world, faction=Faction.SHU, col=8, row=8)
    world.get_singleton_component(UIState).god_mode = True
    world.get_singleton_component(FogOfWar).enabled = True
    world.get_singleton_component(FogOfWar).faction_vision[Faction.WEI] = {(0, 0)}

    result = LLMActionHandler(world).handle_faction_state({"faction": "wei"})
    assert result["fog"] == "disabled"
    assert {e["unit_id"] for e in result["visible_enemy_units"]} == {far}


def test_registered_agent_cannot_census_the_opponent():
    world = _world()
    _spawn(world, faction=Faction.WEI, col=0, row=0)
    _spawn(world, faction=Faction.SHU, col=1, row=0)
    stats = world.get_singleton_component(GameStats)
    stats.agent_id_to_faction["agent_wei"] = Faction.WEI

    result = LLMActionHandler(world).handle_faction_state(
        {"faction": "shu", "agent_id": "agent_wei"}
    )
    assert result["success"] is False
    assert result["error_code"] == 2005
    assert "visible_enemy_units" not in result


def test_bot_query_without_agent_id_uses_requested_faction_as_observer():
    world = _world()
    shu = _spawn(world, faction=Faction.SHU, col=2, row=2)
    _spawn(world, faction=Faction.WEI, col=0, row=0)
    fog = world.get_singleton_component(FogOfWar)
    fog.faction_vision[Faction.SHU] = {(2, 2)}

    result = LLMActionHandler(world).handle_faction_state({"faction": "shu"})
    assert result["success"] is True
    assert result["faction"] == "shu"
    assert [u["unit_id"] for u in result["units"]] == [shu]
    assert result["visible_enemy_units"] == []
    assert "map" not in result
