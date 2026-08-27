"""Default river-split map: board clip, table-backed terrain, spawn = home_bases."""

from rotk_env.components import GameStats, MapData, Terrain, formation_center, effect_for
from rotk_env.maps.map_file import load_map, resolve_map_path
from rotk_env.prefabs.config import Faction, GameConfig, GameMode, PlayerType, TerrainType
from rotk_env.prefabs.world_builder import build_skirmish_world
from rotk_env.systems.input_system import InputHandlingSystem
from rotk_env.systems.map_system import MapSystem
from rotk_env.utils.hex_utils import HexMath


def test_default_scenario_resolves_to_river_split_file():
    path = resolve_map_path("default")
    assert path.name == "river_split.json"
    doc = load_map(path)
    assert doc.id == "river_split"
    assert len(doc.terrain) == 225
    assert len(doc.formations["wei"]) == 5


def test_unknown_scenario_has_no_map_file():
    try:
        resolve_map_path("no_such_map")
    except FileNotFoundError:
        return
    raise AssertionError("expected FileNotFoundError")


def test_river_split_dump_roundtrips_terrain():
    import json

    from rotk_env.maps.map_file import MAPS_DIR, dump_map

    path = MAPS_DIR / "river_split.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    dumped = json.loads(dump_map(load_map(path)))
    assert dumped["terrain"] == raw["terrain"]
    assert dumped["formations"] == raw["formations"]


def test_load_map_rejects_off_board_and_water_formations(tmp_path):
    from rotk_env.maps.map_file import MapDocument, dump_map
    from rotk_env.maps.map_file import load_map as read_map

    src = load_map(resolve_map_path("default"))
    plains = next(pos for pos, kind in src.terrain.items() if kind is TerrainType.PLAIN)
    water = next(pos for pos, kind in src.terrain.items() if kind is TerrainType.WATER)

    bad_off = MapDocument(
        id="t",
        name="t",
        width=src.width,
        height=src.height,
        terrain=src.terrain,
        formations={"wei": [(99, 99)]},
    )
    p = tmp_path / "off.json"
    p.write_text(dump_map(bad_off), encoding="utf-8")
    try:
        read_map(p)
        raise AssertionError("off-board formation should fail")
    except ValueError as exc:
        assert "off the board" in str(exc)

    bad_water = MapDocument(
        id="t",
        name="t",
        width=src.width,
        height=src.height,
        terrain=src.terrain,
        formations={"wei": [water]},
    )
    p = tmp_path / "water.json"
    p.write_text(dump_map(bad_water), encoding="utf-8")
    try:
        read_map(p)
        raise AssertionError("water formation should fail")
    except ValueError as exc:
        assert "water" in str(exc)

    ok = MapDocument(
        id="t",
        name="t",
        width=src.width,
        height=src.height,
        terrain=src.terrain,
        formations={"wei": [plains]},
    )
    p = tmp_path / "ok.json"
    p.write_text(dump_map(ok), encoding="utf-8")
    assert read_map(p).formations["wei"] == [plains]


def test_effect_for_reads_the_eval_table():
    mountain = effect_for(TerrainType.MOUNTAIN)
    assert mountain.movement_cost == 3
    assert mountain.vision_bonus == 2
    assert mountain.blocks_line_of_sight is True
    water = effect_for(TerrainType.WATER)
    assert water.movement_cost == 999
    assert water.blocks_line_of_sight is False


def test_default_map_is_centered_15x15_with_table_backed_terrain():
    world = build_skirmish_world(
        players={Faction.WEI: PlayerType.AI, Faction.SHU: PlayerType.AI},
        mode=GameMode.REAL_TIME,
        seed=1,
        hub_url=None,
        display="none",
    )
    map_data = world.get_singleton_component(MapData)
    half = GameConfig.MAP_WIDTH // 2
    assert len(map_data.tiles) == GameConfig.MAP_WIDTH * GameConfig.MAP_HEIGHT
    assert (0, 0) in map_data.tiles
    assert (half, half) in map_data.tiles
    assert (-half, -half) in map_data.tiles

    mountain = world.get_component(map_data.tiles[(0, 3)], Terrain)
    # (0, 3) is a designed central-axis mountain on river_split.json.
    if mountain and mountain.terrain_type is TerrainType.MOUNTAIN:
        effect = effect_for(mountain.terrain_type)
        assert effect.movement_cost == 3
        assert effect.blocks_line_of_sight is True

    for entity in map_data.tiles.values():
        terrain = world.get_component(entity, Terrain)
        expected = GameConfig.TERRAIN_EFFECTS[terrain.terrain_type]
        assert effect_for(terrain.terrain_type).movement_cost == expected.movement_cost


def test_default_map_places_the_two_cities():
    world = build_skirmish_world(
        players={Faction.WEI: PlayerType.AI, Faction.SHU: PlayerType.AI},
        mode=GameMode.REAL_TIME,
        seed=1,
        hub_url=None,
        display="none",
    )
    map_data = world.get_singleton_component(MapData)
    urban = [
        pos
        for pos, entity in map_data.tiles.items()
        if world.get_component(entity, Terrain).terrain_type is TerrainType.URBAN
    ]
    assert len(urban) == 2
    q1, r1 = HexMath.offset_to_axial(*urban[0])
    q2, r2 = HexMath.offset_to_axial(*urban[1])
    assert (q1, r1) == (-q2, -r2)


def test_formations_stand_on_land_and_stats_use_home_bases():
    world = build_skirmish_world(
        players={Faction.WEI: PlayerType.AI, Faction.SHU: PlayerType.AI},
        mode=GameMode.REAL_TIME,
        seed=1,
        hub_url=None,
        display="none",
    )
    map_data = world.get_singleton_component(MapData)
    stats = world.get_singleton_component(GameStats)
    wei = list(map_data.formations[Faction.WEI])
    shu = list(map_data.formations[Faction.SHU])
    for cell in wei + shu:
        terrain = world.get_component(map_data.tiles[cell], Terrain)
        assert terrain.terrain_type is not TerrainType.WATER, cell
        assert effect_for(terrain.terrain_type).movement_cost < 999
    assert map_data.home_bases[Faction.WEI] == formation_center(wei)
    assert stats.map_info["spawn_positions"]["wei"] == map_data.home_bases[Faction.WEI]
    assert stats.map_info["spawn_positions"]["shu"] == map_data.home_bases[Faction.SHU]
    assert map_data.map_id == "river_split"


def test_click_accepts_the_east_edge_hex():
    world = build_skirmish_world(
        players={Faction.WEI: PlayerType.AI, Faction.SHU: PlayerType.AI},
        mode=GameMode.REAL_TIME,
        seed=1,
        hub_url=None,
        display="none",
    )
    system = InputHandlingSystem()
    system.world = world
    half = GameConfig.MAP_WIDTH // 2
    assert system._hex_on_board((half, 0)) is True
    assert system._hex_on_board((half + 1, 0)) is False


def test_map_system_is_a_loader_not_a_generator():
    assert not hasattr(MapSystem, "_generate_moba_map")
    assert not hasattr(MapSystem, "_generate_river_split_terrain_axial")
    assert not hasattr(MapSystem, "get_competitive_spawn_positions")
    assert hasattr(MapSystem, "load_map")
