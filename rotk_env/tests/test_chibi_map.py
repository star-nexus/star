"""Chibi map file covers the board and keeps spawns on land."""

from collections import Counter

from rotk_env.components import MapData, Unit
from rotk_env.maps.map_file import MAPS_DIR, load_map
from rotk_env.prefabs.config import Faction, GameMode, PlayerType, TerrainType, UnitType
from rotk_env.prefabs.world_builder import build_skirmish_world


def test_chibi_map_is_33x33():
    doc = load_map(MAPS_DIR / "chibi.json")
    assert doc.width == 33
    assert doc.height == 33
    assert len(doc.terrain) == 1089
    assert (0, 0) in doc.terrain
    assert len(doc.formations["wei"]) == 10
    assert len(doc.formations["shu"]) == 5
    assert len(doc.formations["wu"]) == 5


def test_chibi_formations_are_not_water():
    doc = load_map(MAPS_DIR / "chibi.json")
    for cells in doc.formations.values():
        for cell in cells:
            assert doc.terrain[cell] is not TerrainType.WATER, cell


def test_chibi_world_spawns_formation_sized_armies():
    world = build_skirmish_world(
        players={
            Faction.WEI: PlayerType.AI,
            Faction.SHU: PlayerType.AI,
            Faction.WU: PlayerType.AI,
        },
        mode=GameMode.TURN_BASED,
        scenario="chibi",
        seed=1,
        hub_url=None,
        display="none",
    )
    map_data = world.get_singleton_component(MapData)
    assert map_data.width == 33
    assert map_data.height == 33
    assert len(map_data.tiles) == 1089

    counts = Counter()
    types = Counter()
    for entity in world.query().with_component(Unit).entities():
        unit = world.get_component(entity, Unit)
        counts[unit.faction] += 1
        if unit.faction is Faction.WEI:
            types[unit.unit_type] += 1
    assert counts[Faction.WEI] == 10
    assert counts[Faction.SHU] == 5
    assert counts[Faction.WU] == 5
    assert types[UnitType.INFANTRY] == 2
    assert types[UnitType.ARCHER] == 6
    assert types[UnitType.CAVALRY] == 2
