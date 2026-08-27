"""Standing-tile vision_bonus is applied by VisionSystem."""

from framework.ecs.world import World
from rotk_env.components import HexPosition, MapData, Unit, Vision, Terrain
from rotk_env.prefabs.config import Faction, GameConfig, TerrainType, UnitType
from rotk_env.systems.vision_system import VisionSystem
from rotk_env.utils.hex_utils import HexMath


def _disc(world: World, radius: int, stand: TerrainType) -> MapData:
    map_data = MapData(width=radius * 2 + 1, height=radius * 2 + 1)
    world.add_singleton_component(map_data)
    for col in range(-radius, radius + 1):
        for row in range(-radius, radius + 1):
            if HexMath.hex_distance((0, 0), (col, row)) > radius:
                continue
            tile = world.create_entity()
            kind = stand if (col, row) == (0, 0) else TerrainType.PLAIN
            world.add_component(tile, HexPosition(col, row))
            world.add_component(tile, Terrain(kind))
            map_data.tiles[(col, row)] = tile
    return map_data


def _observer(world: World, vision_range: int) -> int:
    entity = world.create_entity()
    world.add_component(
        entity, Unit(unit_type=UnitType.INFANTRY, faction=Faction.WEI, name="v")
    )
    world.add_component(entity, HexPosition(0, 0))
    world.add_component(entity, Vision(range=vision_range))
    return entity


def _max_visible_distance(world: World, entity: int) -> int:
    vision = world.get_component(entity, Vision)
    return max(HexMath.hex_distance((0, 0), tile) for tile in vision.visible_tiles)


def test_config_hill_and_mountain_have_vision_bonus():
    assert GameConfig.TERRAIN_EFFECTS[TerrainType.PLAIN].vision_bonus == 0
    assert GameConfig.TERRAIN_EFFECTS[TerrainType.HILL].vision_bonus == 1
    assert GameConfig.TERRAIN_EFFECTS[TerrainType.MOUNTAIN].vision_bonus == 2


def test_plain_does_not_extend_vision():
    world = World()
    _disc(world, radius=5, stand=TerrainType.PLAIN)
    unit = _observer(world, vision_range=2)
    world.add_system(VisionSystem())
    world.update(0)
    assert _max_visible_distance(world, unit) == 2


def test_hill_adds_one_to_vision_range():
    world = World()
    _disc(world, radius=5, stand=TerrainType.HILL)
    unit = _observer(world, vision_range=2)
    world.add_system(VisionSystem())
    world.update(0)
    assert _max_visible_distance(world, unit) == 3


def test_mountain_adds_two_to_vision_range():
    world = World()
    _disc(world, radius=6, stand=TerrainType.MOUNTAIN)
    unit = _observer(world, vision_range=2)
    world.add_system(VisionSystem())
    world.update(0)
    assert _max_visible_distance(world, unit) == 4
