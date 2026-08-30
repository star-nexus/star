"""Own-unit reachable / attackable on get_faction_state. Mask ≡ execute."""

from framework.ecs.world import World
from rotk_env.components import (
    ActionPoints,
    Combat,
    FogOfWar,
    GameModeComponent,
    GameStats,
    GameState,
    HexPosition,
    MapData,
    MovementAnimation,
    MovementPoints,
    Terrain,
    UIState,
    Unit,
    UnitCount,
    UnitStatus,
)
from rotk_env.prefabs.config import (
    Faction,
    GameMode,
    TerrainType,
    UnitState,
    UnitType,
)
from rotk_env.systems.combat_system import CombatSystem
from rotk_env.systems.llm_action_handler import LLMActionHandler
from rotk_env.systems.movement_system import MovementSystem
from rotk_env.utils.hex_utils import HexMath


def _disc(world: World, radius: int, extras=None) -> MapData:
    extras = extras or {}
    map_data = MapData(width=radius * 2 + 1, height=radius * 2 + 1)
    world.add_singleton_component(map_data)
    for col in range(-radius, radius + 1):
        for row in range(-radius, radius + 1):
            if HexMath.hex_distance((0, 0), (col, row)) > radius:
                continue
            tile = world.create_entity()
            kind = extras.get((col, row), TerrainType.PLAIN)
            world.add_component(tile, HexPosition(col, row))
            world.add_component(tile, Terrain(kind))
            map_data.tiles[(col, row)] = tile
    return map_data


def _spawn(
    world,
    *,
    faction,
    col,
    row,
    unit_type=UnitType.INFANTRY,
    mp=4,
    base_mp=None,
    ap=2,
    attack_range=None,
    count=100,
):
    cap = mp if base_mp is None else base_mp
    stats_range = 1 if unit_type != UnitType.ARCHER else 3
    entity = world.create_entity()
    world.add_component(
        entity, Unit(unit_type=unit_type, faction=faction, name="test")
    )
    world.add_component(entity, HexPosition(col, row))
    world.add_component(entity, UnitCount(current_count=count, max_count=100))
    world.add_component(
        entity, MovementPoints(current_mp=mp, max_mp=cap, base_mp=cap)
    )
    world.add_component(entity, ActionPoints(current_ap=ap, max_ap=2))
    world.add_component(
        entity,
        Combat(
            base_attack=10,
            base_defense=10,
            attack_range=attack_range if attack_range is not None else stats_range,
        ),
    )
    world.add_component(entity, UnitStatus(current_status=UnitState.NORMAL))
    return entity


def _world(extras=None):
    world = World()
    world.add_singleton_component(UIState())
    world.add_singleton_component(FogOfWar(enabled=True))
    world.add_singleton_component(GameStats())
    world.add_singleton_component(
        GameState(current_player=Faction.WEI, game_mode=GameMode.REAL_TIME)
    )
    world.add_singleton_component(GameModeComponent(mode=GameMode.REAL_TIME))
    _disc(world, radius=3, extras=extras)
    world.add_system(MovementSystem())
    world.add_system(CombatSystem())
    return world


def _query(world, faction="wei"):
    return LLMActionHandler(world).handle_faction_state({"faction": faction})


def _own(result, unit_id):
    return next(u for u in result["units"] if u["unit_id"] == unit_id)


def _hexes(tiles):
    return {(t["col"], t["row"]) for t in tiles}


def test_reachable_is_legal_move_set_not_mp_radius():
    world = _world(
        extras={(1, 0): TerrainType.FOREST, (0, 1): TerrainType.WATER}
    )
    own = _spawn(world, faction=Faction.WEI, col=0, row=0, mp=2)
    blocker = _spawn(world, faction=Faction.WEI, col=-1, row=0, mp=0)
    fog = world.get_singleton_component(FogOfWar)
    fog.faction_vision[Faction.WEI] = {(0, 0), (1, 0), (0, 1), (-1, 0)}

    result = _query(world)
    reachable = _hexes(_own(result, own)["reachable"])

    assert (0, 0) not in reachable
    assert (0, 1) not in reachable
    assert (-1, 0) not in reachable
    assert (1, 0) in reachable
    assert _own(result, blocker)["reachable"] == []

    handler = LLMActionHandler(world)
    rejected = handler.handle_move_action(
        {"unit_id": own, "target_position": {"col": 0, "row": 1}}
    )
    assert rejected.get("success") is not True

    accepted = handler.handle_move_action(
        {"unit_id": own, "target_position": {"col": 1, "row": 0}}
    )
    assert accepted["success"] is True


def test_mountain_over_mp_is_not_reachable_and_move_rejects():
    world = _world(extras={(1, 0): TerrainType.MOUNTAIN})
    own = _spawn(world, faction=Faction.WEI, col=0, row=0, mp=2, base_mp=4)
    fog = world.get_singleton_component(FogOfWar)
    fog.faction_vision[Faction.WEI] = {(0, 0), (1, 0)}

    reachable = _hexes(_own(_query(world), own)["reachable"])
    assert (1, 0) not in reachable

    result = LLMActionHandler(world).handle_move_action(
        {"unit_id": own, "target_position": {"col": 1, "row": 0}}
    )
    assert result.get("success") is not True


def test_attackable_is_visible_in_range_ids_not_tiles():
    world = _world()
    own = _spawn(world, faction=Faction.WEI, col=0, row=0, mp=2)
    near = _spawn(world, faction=Faction.SHU, col=1, row=0, mp=2)
    far = _spawn(world, faction=Faction.SHU, col=3, row=0, mp=2)
    fog = world.get_singleton_component(FogOfWar)
    fog.faction_vision[Faction.WEI] = {(0, 0), (1, 0)}

    result = _query(world)
    own_row = _own(result, own)
    assert own_row["attackable"] == [near]
    enemy_ids = {e["unit_id"] for e in result["visible_enemy_units"]}
    assert enemy_ids == {near}
    assert far not in own_row["attackable"]
    for enemy in result["visible_enemy_units"]:
        assert "reachable" not in enemy
        assert "attackable" not in enemy

    accepted = LLMActionHandler(world).handle_attack_action(
        {"unit_id": own, "target_id": near}
    )
    assert accepted.get("success") is True or accepted.get("result") is True


def test_same_hex_enemy_is_attackable():
    world = _world()
    own = _spawn(world, faction=Faction.WEI, col=0, row=0, mp=2)
    stacked = _spawn(world, faction=Faction.SHU, col=0, row=0, mp=2)
    fog = world.get_singleton_component(FogOfWar)
    fog.faction_vision[Faction.WEI] = {(0, 0)}

    assert _own(_query(world), own)["attackable"] == [stacked]
    accepted = LLMActionHandler(world).handle_attack_action(
        {"unit_id": own, "target_id": stacked}
    )
    assert accepted.get("success") is True or accepted.get("result") is True


def test_zero_ap_and_confusion_clear_masks():
    world = _world()
    tired = _spawn(world, faction=Faction.WEI, col=0, row=0, mp=4, ap=0)
    confused = _spawn(world, faction=Faction.WEI, col=-1, row=0, mp=4, ap=2)
    world.get_component(confused, UnitStatus).current_status = UnitState.CONFUSION
    enemy = _spawn(world, faction=Faction.SHU, col=1, row=0, mp=2)
    fog = world.get_singleton_component(FogOfWar)
    fog.faction_vision[Faction.WEI] = {(0, 0), (1, 0), (-1, 0)}

    result = _query(world)
    assert _own(result, tired)["attackable"] == []
    assert _hexes(_own(result, tired)["reachable"])
    assert _own(result, confused)["reachable"] == []
    assert enemy not in _own(result, tired)["attackable"]


def test_already_moving_has_empty_reachable():
    world = _world()
    own = _spawn(world, faction=Faction.WEI, col=0, row=0, mp=4)
    world.add_component(own, MovementAnimation(is_moving=True))
    fog = world.get_singleton_component(FogOfWar)
    fog.faction_vision[Faction.WEI] = {(0, 0)}

    assert _own(_query(world), own)["reachable"] == []


def test_archer_attackable_uses_combat_range_not_a_tile_ring():
    world = _world()
    archer = _spawn(
        world,
        faction=Faction.WEI,
        col=0,
        row=0,
        unit_type=UnitType.ARCHER,
        mp=2,
        attack_range=3,
    )
    mid = _spawn(world, faction=Faction.SHU, col=2, row=0, mp=2)
    fog = world.get_singleton_component(FogOfWar)
    fog.faction_vision[Faction.WEI] = {(0, 0), (2, 0)}

    assert _own(_query(world), archer)["attackable"] == [mid]


def test_opening_skirmish_own_units_carry_masks_enemies_do_not():
    from rotk_env.prefabs.config import PlayerType
    from rotk_env.prefabs.world_builder import build_skirmish_world

    world = build_skirmish_world(
        players={Faction.WEI: PlayerType.AI, Faction.SHU: PlayerType.AI},
        mode=GameMode.TURN_BASED,
        seed=1,
        hub_url=None,
        display="none",
    )
    result = _query(world, "wei")
    assert result["units"]
    for unit in result["units"]:
        assert isinstance(unit["reachable"], list)
        assert isinstance(unit["attackable"], list)
        here = (unit["position"]["col"], unit["position"]["row"])
        assert here not in _hexes(unit["reachable"])
    assert any(unit["reachable"] for unit in result["units"])
    for enemy in result["visible_enemy_units"]:
        assert "reachable" not in enemy
        assert "attackable" not in enemy
