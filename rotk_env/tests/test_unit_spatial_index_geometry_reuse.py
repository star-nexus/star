from framework.ecs.world import World

from rotk_env.components import HexPosition, MapData, Unit, UnitCount
from rotk_env.prefabs.config import Faction, UnitType
from rotk_env.utils.map_query import invalidate_static_map_cache
from rotk_env.utils.unit_spatial_index import rebuild_unit_spatial_index


def _add_unit(world, col=0, row=0, faction=Faction.WEI):
    entity = world.create_entity()
    world.add_component(
        entity,
        Unit(unit_type=UnitType.INFANTRY, faction=faction, name=str(entity)),
    )
    world.add_component(entity, HexPosition(col, row))
    world.add_component(entity, UnitCount(current_count=100, max_count=100))
    return entity


def _add_board(world, cells):
    tiles = {cell: index + 1 for index, cell in enumerate(cells)}
    world.add_singleton_component(
        MapData(width=max(1, len(cells)), height=max(1, len(cells)), tiles=tiles)
    )
    return world.get_singleton_component(MapData)


def test_board_hex_reuses_geometry_payload_but_not_record_identity():
    world = World()
    _add_board(world, [(0, 0), (1, 0)])
    _add_unit(world, 0, 0)
    index = rebuild_unit_spatial_index(world)

    first = index._record_for_hex(1, 0, Faction.WEI)
    second = index._record_for_hex(1, 0, Faction.WEI)

    assert first is not second
    assert first == second
    assert first.world_x is second.world_x
    assert first.world_y is second.world_y
    assert first.bucket is second.bucket
    assert index._geometry_by_hex[(1, 0)] == (
        first.world_x,
        first.world_y,
        first.bucket,
    )
    assert len(index._geometry_by_hex) <= len(index._geometry_board_hexes)


def test_off_board_geometry_never_grows_bounded_cache():
    world = World()
    _add_board(world, [(0, 0), (1, 0)])
    _add_unit(world, 0, 0)
    index = rebuild_unit_spatial_index(world)
    size_before = len(index._geometry_by_hex)

    for _ in range(5):
        record = index._record_for_hex(99, -77, Faction.WEI)
        assert (record.col, record.row) == (99, -77)

    assert len(index._geometry_by_hex) == size_before
    assert (99, -77) not in index._geometry_by_hex


def test_world_without_mapdata_keeps_geometry_cache_disabled():
    world = World()
    _add_unit(world, 0, 0)
    index = rebuild_unit_spatial_index(world)

    assert index._geometry_board_hexes is None
    assert index._geometry_by_hex == {}

    index._record_for_hex(1, 0, Faction.WEI)
    index._bucket_for_hex(2, -1)
    assert index._geometry_by_hex == {}


def test_rebuild_clears_geometry_and_rebinds_current_board_snapshot():
    world = World()
    map_data = _add_board(world, [(0, 0), (1, 0)])
    _add_unit(world, 0, 0)
    index = rebuild_unit_spatial_index(world)

    index._record_for_hex(1, 0, Faction.WEI)
    assert (1, 0) in index._geometry_by_hex

    map_data.tiles = {(5, 5): 101, (6, 5): 102}
    invalidate_static_map_cache(world)
    index.rebuild(world)

    assert index._geometry_board_hexes == frozenset({(5, 5), (6, 5)})
    # The existing unit is now off-board, so rebuilding its record must not
    # repopulate the board-bounded geometry cache.
    assert index._geometry_by_hex == {}

    first = index._record_for_hex(5, 5, Faction.WEI)
    second = index._record_for_hex(5, 5, Faction.SHU)
    assert first.world_x is second.world_x
    assert first.world_y is second.world_y
    assert first.bucket is second.bucket
    assert set(index._geometry_by_hex) == {(5, 5)}


def test_bucket_lookup_shares_the_same_canonical_geometry_payload():
    world = World()
    _add_board(world, [(0, 0), (1, 0)])
    _add_unit(world, 0, 0)
    index = rebuild_unit_spatial_index(world)

    record = index._record_for_hex(1, 0, Faction.WEI)
    bucket = index._bucket_for_hex(1, 0)

    assert bucket is record.bucket
    assert len(index._geometry_by_hex) <= len(index._geometry_board_hexes)
