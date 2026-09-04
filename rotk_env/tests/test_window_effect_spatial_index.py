from framework.ecs.world import World

from rotk_env.components import (
    HexPosition,
    MapData,
    MovementPoints,
    Terrain,
    Tile,
    Unit,
    UnitCount,
)
from rotk_env.prefabs.config import Faction, TerrainType, UnitType
from rotk_env.systems.window_effect_render_system import EffectRenderSystem
from rotk_env.utils.hex_utils import HexMath
from rotk_env.utils.map_query import reachable_hexes
from rotk_env.utils.unit_spatial_index import (
    rebuild_unit_spatial_index,
    update_unit_spatial_index,
)


def _add_unit(
    world: World,
    faction: Faction,
    col: int,
    row: int,
    *,
    mp: int = 4,
) -> int:
    entity = world.create_entity()
    world.add_component(
        entity,
        Unit(unit_type=UnitType.INFANTRY, faction=faction, name=f"u{entity}"),
    )
    world.add_component(entity, HexPosition(col, row))
    world.add_component(entity, UnitCount(current_count=100, max_count=100))
    world.add_component(
        entity,
        MovementPoints(base_mp=mp, current_mp=mp, max_mp=mp),
    )
    return entity


def _disc(world: World, radius: int, terrain=None) -> MapData:
    terrain = terrain or {}
    map_data = MapData(width=radius * 2 + 1, height=radius * 2 + 1)
    world.add_singleton_component(map_data)
    for col in range(-radius, radius + 1):
        for row in range(-radius, radius + 1):
            if HexMath.hex_distance((0, 0), (col, row)) > radius:
                continue
            entity = world.create_entity()
            world.add_component(entity, HexPosition(col, row))
            world.add_component(
                entity,
                Terrain(terrain.get((col, row), TerrainType.PLAIN)),
            )
            world.add_component(entity, Tile((col, row)))
            map_data.tiles[(col, row)] = entity
    return map_data


def test_effect_enemy_lookup_reads_the_shared_index():
    world = World()
    wei = _add_unit(world, Faction.WEI, 0, 0)
    shu = _add_unit(world, Faction.SHU, 1, 0)
    index = rebuild_unit_spatial_index(world)

    system = EffectRenderSystem()
    system.initialize(world)

    assert system._get_enemy_unit_at_position((1, 0), Faction.WEI) == shu
    assert system._get_enemy_unit_at_position((0, 0), Faction.WEI) is None
    assert index.entities_at_cell((1, 0)) == {shu}

    pos = world.get_component(shu, HexPosition)
    pos.col, pos.row = 2, 0
    assert update_unit_spatial_index(world, shu) is True

    assert system._get_enemy_unit_at_position((1, 0), Faction.WEI) is None
    assert system._get_enemy_unit_at_position((2, 0), Faction.WEI) == shu
    assert wei in index.by_entity


def test_effect_movement_key_ignores_far_changes_but_invalidates_near_changes():
    world = World()
    mover = _add_unit(world, Faction.WEI, 0, 0, mp=4)
    near = _add_unit(world, Faction.SHU, 2, 0)
    far = _add_unit(world, Faction.SHU, 30, 30)
    rebuild_unit_spatial_index(world)

    system = EffectRenderSystem()
    system.initialize(world)
    position = world.get_component(mover, HexPosition)
    movement = world.get_component(mover, MovementPoints)
    unit_count = world.get_component(mover, UnitCount)

    key_before = system._movement_state_key(mover, position, movement, unit_count)

    far_pos = world.get_component(far, HexPosition)
    far_pos.col, far_pos.row = 31, 30
    assert update_unit_spatial_index(world, far) is True
    key_after_far_move = system._movement_state_key(
        mover, position, movement, unit_count
    )
    assert key_after_far_move == key_before

    near_pos = world.get_component(near, HexPosition)
    near_pos.col, near_pos.row = 3, 0
    assert update_unit_spatial_index(world, near) is True
    key_after_near_move = system._movement_state_key(
        mover, position, movement, unit_count
    )
    assert key_after_near_move != key_before


def test_indexed_effect_reachable_matches_the_canonical_move_oracle():
    world = World()
    _disc(
        world,
        3,
        {
            (-1, 0): TerrainType.WATER,
            (0, 1): TerrainType.FOREST,
            (1, 0): TerrainType.MOUNTAIN,
        },
    )
    mover = _add_unit(world, Faction.WEI, 0, 0, mp=4)
    _add_unit(world, Faction.WEI, 1, -1)
    _add_unit(world, Faction.SHU, 2, 0)
    rebuild_unit_spatial_index(world)

    system = EffectRenderSystem()
    system.initialize(world)
    position = world.get_component(mover, HexPosition)
    movement = world.get_component(mover, MovementPoints)
    unit = world.get_component(mover, Unit)
    unit_count = world.get_component(mover, UnitCount)

    indexed = system._indexed_reachable_hexes(
        mover,
        position,
        movement,
        unit,
        unit_count,
    )
    canonical = reachable_hexes(
        world,
        (position.col, position.row),
        movement.spendable(unit_count),
        mover=mover,
    )

    assert indexed == canonical
