"""A* reachability and terrain movement cost. No hub, no pygame window."""

from framework.ecs.world import World
from rotk_env.components import (
    GameModeComponent,
    HexPosition,
    MapData,
    MovementPoints,
    Terrain,
    Unit,
    UnitCount,
)
from rotk_env.prefabs.config import Faction, GameConfig, GameMode, TerrainType, UnitType
from rotk_env.systems.llm_action_handler import LLMActionHandler
from rotk_env.systems.movement_system import MovementSystem
from rotk_env.utils.hex_utils import HexMath, PathFinding


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


def _spawn(world, *, col, row, mp=4, faction=Faction.WEI):
    entity = world.create_entity()
    world.add_component(
        entity, Unit(unit_type=UnitType.INFANTRY, faction=faction, name="test")
    )
    world.add_component(entity, HexPosition(col, row))
    world.add_component(entity, UnitCount(current_count=100, max_count=100))
    world.add_component(
        entity, MovementPoints(current_mp=mp, max_mp=mp, base_mp=mp)
    )
    return entity


def test_terrain_movement_costs_are_the_eval_table():
    effects = GameConfig.TERRAIN_EFFECTS
    assert effects[TerrainType.PLAIN].movement_cost == 1
    assert effects[TerrainType.FOREST].movement_cost == 2
    assert effects[TerrainType.HILL].movement_cost == 2
    assert effects[TerrainType.MOUNTAIN].movement_cost == 3
    assert effects[TerrainType.WATER].movement_cost == 999


def test_astar_walks_hex_neighbors_not_squares():
    path = PathFinding.find_path((0, 0), (2, 0), obstacles=set(), max_distance=4)
    assert path[0] == (0, 0)
    assert path[-1] == (2, 0)
    assert len(path) == HexMath.hex_distance((0, 0), (2, 0)) + 1
    for prev, nxt in zip(path, path[1:]):
        assert nxt in HexMath.hex_neighbors(*prev)


def test_astar_routes_around_occupied_hexes():
    # Both length-2 corridors from (0,0) to (2,0) on this odd-q grid.
    blocked = {(1, 0), (1, -1)}
    path = PathFinding.find_path((0, 0), (2, 0), obstacles=blocked, max_distance=6)
    assert path
    assert path[-1] == (2, 0)
    assert blocked.isdisjoint(path)
    assert len(path) > HexMath.hex_distance((0, 0), (2, 0)) + 1


def test_astar_treats_each_step_as_cost_one():
    """Reachability ignores terrain; MovementSystem applies hex cost later."""
    forest_step = PathFinding.find_path(
        (0, 0), (1, 0), obstacles=set(), max_distance=1
    )
    assert forest_step == [(0, 0), (1, 0)]
    too_far = PathFinding.find_path((0, 0), (2, 0), obstacles=set(), max_distance=1)
    assert too_far == []


def test_astar_rejects_a_blocked_goal():
    assert PathFinding.find_path((0, 0), (1, 0), obstacles={(1, 0)}) == []


def test_move_unit_spends_plain_cost_and_lands():
    world = World()
    _disc(world, radius=3)
    world.add_system(MovementSystem())
    unit = _spawn(world, col=0, row=0, mp=4)

    assert world.systems[0].move_unit(unit, (1, 0)) is True
    pos = world.get_component(unit, HexPosition)
    mp = world.get_component(unit, MovementPoints)
    assert (pos.col, pos.row) == (1, 0)
    assert mp.current_mp == 3


def test_mountain_hex_costs_three_and_can_block_a_short_move():
    def _try(mp):
        world = World()
        _disc(world, radius=3, extras={(1, 0): TerrainType.MOUNTAIN})
        movement = MovementSystem()
        world.add_system(movement)
        unit = _spawn(world, col=0, row=0, mp=mp)
        ok = movement.move_unit(unit, (1, 0))
        pos = world.get_component(unit, HexPosition)
        left = world.get_component(unit, MovementPoints).current_mp
        return ok, (pos.col, pos.row), left

    blocked, pos, mp = _try(2)
    assert blocked is False
    assert pos == (0, 0)
    assert mp == 2

    moved, pos, mp = _try(3)
    assert moved is True
    assert pos == (1, 0)
    assert mp == 0


def test_water_is_an_obstacle_not_a_walkable_999_tile():
    world = World()
    _disc(world, radius=3, extras={(1, 0): TerrainType.WATER})
    movement = MovementSystem()
    world.add_system(movement)
    unit = _spawn(world, col=0, row=0, mp=8)

    assert movement.move_unit(unit, (1, 0)) is False
    path = PathFinding.find_path((0, 0), (1, 0), movement._get_obstacles(), max_distance=8)
    assert path == []


def test_handle_move_walks_the_same_cost_table():
    world = World()
    world.add_singleton_component(GameModeComponent(mode=GameMode.REAL_TIME))
    _disc(world, radius=3, extras={(1, 0): TerrainType.FOREST})
    world.add_system(MovementSystem())
    unit = _spawn(world, col=0, row=0, mp=2)

    result = LLMActionHandler(world).handle_move_action(
        {"unit_id": unit, "target_position": {"col": 1, "row": 0}}
    )
    assert result["success"] is True
    assert world.get_component(unit, MovementPoints).current_mp == 0
    pos = world.get_component(unit, HexPosition)
    assert (pos.col, pos.row) == (1, 0)
