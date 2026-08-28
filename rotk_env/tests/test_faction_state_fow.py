"""get_faction_state follows FogOfWar.enabled: own Units plus currently visible enemies.

Run the assertions:

    uv run pytest rotk_env/tests/test_faction_state_fow.py -s

Or print the fog-switch cycle (same world, key 1 off then on):

    uv run python rotk_env/tests/test_faction_state_fow.py
"""

import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from framework.ecs.world import World
from rotk_env.components import (
    FogOfWar,
    GameStats,
    HexPosition,
    Unit,
    UnitCount,
    UIState,
    Vision,
    set_fog_enabled,
)
from rotk_env.prefabs.config import Faction, UnitType
from rotk_env.systems.llm_action_handler import LLMActionHandler
from rotk_env.systems.vision_system import VisionSystem


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


def _query(world, faction="wei"):
    return LLMActionHandler(world).handle_faction_state({"faction": faction})


def _enemy_ids(result):
    return {e["unit_id"] for e in result["visible_enemy_units"]}


def _press_key_1(world):
    import pygame

    from rotk_env.systems.input_system import InputHandlingSystem

    system = InputHandlingSystem()
    system.world = world
    system._handle_key_down(pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_1}))


def _fog_switch_setup():
    """Wei at (0,0); Shu next door; Shu far away, outside stubbed vision."""
    world = _world()
    own = _spawn(world, faction=Faction.WEI, col=0, row=0)
    near = _spawn(world, faction=Faction.SHU, col=1, row=0, unit_type=UnitType.CAVALRY)
    far = _spawn(world, faction=Faction.SHU, col=8, row=8, count=55)
    fog = world.get_singleton_component(FogOfWar)
    fog.faction_vision[Faction.WEI] = {(0, 0), (1, 0)}
    return world, own, near, far, fog


def test_own_units_is_complete_and_enemies_use_vision_when_fog_on():
    world, own, near, far, _fog = _fog_switch_setup()
    hidden = far

    result = _query(world)
    assert result["success"] is True
    assert result["fog"] == "active"
    assert result["alive_units"] == 1
    assert [u["unit_id"] for u in result["units"]] == [own]
    assert "capabilities" in result["units"][0]
    assert result["units"][0]["reachable"] == []
    assert result["units"][0]["attackable"] == []

    visible_ids = _enemy_ids(result)
    assert visible_ids == {near}
    assert hidden not in visible_ids
    enemy = result["visible_enemy_units"][0]
    assert enemy["unit_type"] == "cavalry"
    assert enemy["position"] == {"col": 1, "row": 0}
    assert enemy["unit_status"] == {"current_count": 100}
    assert "capabilities" not in enemy
    assert "commandable" not in enemy
    assert result["visible_terrain"] == []


def test_fog_off_returns_every_living_enemy():
    world, _own, near, far, fog = _fog_switch_setup()
    dead = _spawn(world, faction=Faction.SHU, col=2, row=0, count=0)
    set_fog_enabled(fog, False)

    result = _query(world)
    assert result["fog"] == "disabled"
    assert fog.enabled is False
    visible_ids = _enemy_ids(result)
    assert visible_ids == {near, far}
    assert dead not in visible_ids
    by_id = {e["unit_id"]: e for e in result["visible_enemy_units"]}
    assert by_id[far]["unit_status"]["current_count"] == 55


def test_key_1_toggles_fog_for_get_faction_state():
    """Same world: fog on → key 1 off → key 1 on. Own Units never shrink."""
    world, own, near, far, fog = _fog_switch_setup()

    on = _query(world)
    assert fog.enabled is True
    assert on["fog"] == "active"
    assert [u["unit_id"] for u in on["units"]] == [own]
    assert _enemy_ids(on) == {near}

    _press_key_1(world)
    off = _query(world)
    assert fog.enabled is False
    assert off["fog"] == "disabled"
    assert [u["unit_id"] for u in off["units"]] == [own]
    assert _enemy_ids(off) == {near, far}

    _press_key_1(world)
    back = _query(world)
    assert fog.enabled is True
    assert back["fog"] == "active"
    assert [u["unit_id"] for u in back["units"]] == [own]
    assert _enemy_ids(back) == {near}


def test_set_fog_enabled_is_the_same_switch():
    world, _own, near, far, fog = _fog_switch_setup()

    set_fog_enabled(fog, False)
    assert _query(world)["fog"] == "disabled"
    assert _enemy_ids(_query(world)) == {near, far}

    set_fog_enabled(fog, True)
    assert fog.enabled is True
    result = _query(world)
    assert result["fog"] == "active"
    assert _enemy_ids(result) == {near}


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

    result = _query(world, "shu")
    assert result["success"] is True
    assert result["faction"] == "shu"
    assert [u["unit_id"] for u in result["units"]] == [shu]
    assert result["visible_enemy_units"] == []
    assert "map" not in result


def test_vision_system_feeds_faction_state_fog():
    world = _world()
    observer = _spawn(world, faction=Faction.WEI, col=0, row=0)
    world.add_component(observer, Vision(range=2))
    seen = _spawn(world, faction=Faction.SHU, col=1, row=0)
    hidden = _spawn(world, faction=Faction.SHU, col=5, row=5)

    world.add_system(VisionSystem())
    world.update(0)
    fog = world.get_singleton_component(FogOfWar)

    on = _query(world)
    assert on["fog"] == "active"
    assert _enemy_ids(on) == {seen}
    assert hidden not in _enemy_ids(on)

    _press_key_1(world)
    off = _query(world)
    assert fog.enabled is False
    assert off["fog"] == "disabled"
    assert _enemy_ids(off) == {seen, hidden}

    _press_key_1(world)
    back = _query(world)
    assert fog.enabled is True
    assert back["fog"] == "active"
    assert _enemy_ids(back) == {seen}


def test_visible_terrain_follows_fog_and_reports_table_cost():
    from rotk_env.components import MapData, Terrain
    from rotk_env.prefabs.config import TerrainType

    world, _own, _near, _far, fog = _fog_switch_setup()
    map_data = MapData(width=3, height=3, tiles={})
    world.add_singleton_component(map_data)
    for pos, kind in [((0, 0), TerrainType.PLAIN), ((1, 0), TerrainType.FOREST)]:
        tile = world.create_entity()
        world.add_component(tile, HexPosition(*pos))
        world.add_component(tile, Terrain(kind))
        map_data.tiles[pos] = tile
    fog.faction_vision[Faction.WEI] = {(0, 0)}

    on = _query(world)
    assert {(t["col"], t["row"]) for t in on["visible_terrain"]} == {(0, 0)}
    assert on["visible_terrain"][0]["type"] == "plain"
    assert on["visible_terrain"][0]["movement_cost"] == 1

    set_fog_enabled(fog, False)
    off = _query(world)
    by_pos = {(t["col"], t["row"]): t for t in off["visible_terrain"]}
    assert set(by_pos) == {(0, 0), (1, 0)}
    assert by_pos[(1, 0)]["type"] == "forest"
    assert by_pos[(1, 0)]["movement_cost"] == 2
    assert by_pos[(1, 0)]["passable"] is True


def test_opening_skirmish_faction_state_has_visible_terrain():
    """Fog is on at assemble; vision must already be computed without a game tick."""
    from rotk_env.prefabs.config import GameMode, PlayerType
    from rotk_env.prefabs.world_builder import build_skirmish_world

    world = build_skirmish_world(
        players={Faction.WEI: PlayerType.AI, Faction.SHU: PlayerType.AI},
        mode=GameMode.TURN_BASED,
        seed=1,
        hub_url=None,
        display="none",
    )
    result = _query(world, "wei")
    assert result["fog"] == "active"
    terrain = result["visible_terrain"]
    assert terrain, "opening vision should reveal tiles around own units"
    own = {(u["position"]["col"], u["position"]["row"]) for u in result["units"]}
    vis = {(t["col"], t["row"]) for t in terrain}
    assert own <= vis


def _print_step(label, fog, result):
    own = [u["unit_id"] for u in result["units"]]
    enemies = sorted(_enemy_ids(result))
    print(
        f"  {label:18} enabled={str(fog.enabled):5}  "
        f"fog={result.get('fog', '?'):8}  "
        f"own={own}  visible_enemies={enemies}"
    )


def main():
    print("get_faction_state fog switch  (key 1 = FogOfWar.enabled)")
    print("Wei (0,0) sees Shu at (1,0); Shu at (8,8) is outside vision.\n")

    world, own, near, far, fog = _fog_switch_setup()
    print(f"  own={own}  near(visible)={near}  far(hidden)={far}\n")

    _print_step("fog on", fog, _query(world))
    _press_key_1(world)
    _print_step("key 1 → off", fog, _query(world))
    _press_key_1(world)
    _print_step("key 1 → on", fog, _query(world))

    test_key_1_toggles_fog_for_get_faction_state()
    test_set_fog_enabled_is_the_same_switch()
    test_vision_system_feeds_faction_state_fog()
    print("\nAssertions passed.")


if __name__ == "__main__":
    main()
