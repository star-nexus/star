from framework.ecs.world import World

from rotk_env.components import HexPosition, MapData, Terrain, Tile
from rotk_env.components.terrain import effect_for, movement_cost_at, terrain_at
from rotk_env.prefabs.config import TerrainType


def test_first_tile_entity_zero_is_not_treated_as_missing():
    world = World()
    map_data = MapData(width=1, height=1)
    world.add_singleton_component(map_data)

    tile = world.create_entity()
    assert tile == 0
    world.add_component(tile, HexPosition(0, 0))
    world.add_component(tile, Terrain(TerrainType.WATER))
    world.add_component(tile, Tile((0, 0)))
    map_data.tiles[(0, 0)] = tile

    terrain = terrain_at(world, (0, 0))
    assert terrain is not None
    assert terrain.terrain_type == TerrainType.WATER
    assert movement_cost_at(world, (0, 0)) == int(
        effect_for(TerrainType.WATER).movement_cost
    )
