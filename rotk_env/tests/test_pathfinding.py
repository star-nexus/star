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


def _spawn(world, *, col, row, mp=4, faction=Faction.WEI, base_mp=None):
    entity = world.create_entity()
    world.add_component(
        entity, Unit(unit_type=UnitType.INFANTRY, faction=faction, name="test")
    )
    world.add_component(entity, HexPosition(col, row))
    world.add_component(entity, UnitCount(current_count=100, max_count=100))
    cap = mp if base_mp is None else base_mp
    world.add_component(
        entity, MovementPoints(current_mp=mp, max_mp=cap, base_mp=cap)
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
    """Without step_cost, reachability is hex count."""
    forest_step = PathFinding.find_path(
        (0, 0), (1, 0), obstacles=set(), max_distance=1
    )
    assert forest_step == [(0, 0), (1, 0)]
    too_far = PathFinding.find_path((0, 0), (2, 0), obstacles=set(), max_distance=1)
    assert too_far == []


def test_astar_rejects_a_blocked_goal():
    assert PathFinding.find_path((0, 0), (1, 0), obstacles={(1, 0)}) == []


def test_astar_does_not_leave_walkable_set():
    walkable = {(0, 0), (1, 0)}
    assert PathFinding.find_path(
        (0, 0), (2, 0), obstacles=set(), max_distance=8, walkable=walkable
    ) == []
    assert PathFinding.find_path(
        (0, 0), (1, 0), obstacles=set(), max_distance=2, walkable=walkable
    ) == [(0, 0), (1, 0)]


def test_move_unit_spends_plain_cost_and_lands():
    world = World()
    _disc(world, radius=3)
    world.add_system(MovementSystem())
    unit = _spawn(world, col=0, row=0, mp=4)

    result = world.systems[0].move_unit(unit, (1, 0))
    assert result["success"] is True
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
        result = movement.move_unit(unit, (1, 0))
        pos = world.get_component(unit, HexPosition)
        left = world.get_component(unit, MovementPoints).current_mp
        return result["success"], (pos.col, pos.row), left

    blocked, pos, mp = _try(2)
    assert blocked is False
    assert pos == (0, 0)
    assert mp == 2

    moved, pos, mp = _try(3)
    assert moved is True
    assert pos == (1, 0)
    assert mp == 0


def test_path_over_budget_is_insufficient_mp_not_no_path():
    """A* capped at current MP used to return no_path when terrain made the
    cheapest route cost more than hex-distance. Report that route instead."""
    world = World()
    _disc(world, radius=3, extras={(1, 0): TerrainType.MOUNTAIN})
    movement = MovementSystem()
    world.add_system(movement)
    unit = _spawn(world, col=0, row=0, mp=2)

    result = movement.move_unit(unit, (1, 0))
    assert result["success"] is False
    assert result["reason"] == "insufficient_mp"
    assert result["required_movement_points"] == 3
    assert result["current_movement_points"] == 2
    assert result["path"] == [[0, 0], [1, 0]]
    assert result["farthest_reachable_on_path"] == {"col": 0, "row": 0}
    assert "Shortest path costs 3 MP" in result["message"]
    suggested = result.get("suggested_action")
    if suggested:
        dest = suggested["params"]["target_position"]
        assert (dest["col"], dest["row"]) != (0, 0)


def test_farthest_reachable_stops_before_an_unaffordable_step():
    """Corridor: plains then mountain. 3 MP reaches the plains hex only."""
    extras = {
        (2, 0): TerrainType.MOUNTAIN,
        (3, -1): TerrainType.MOUNTAIN,
        (2, -1): TerrainType.MOUNTAIN,
        (1, -1): TerrainType.MOUNTAIN,
        (2, 1): TerrainType.MOUNTAIN,
        (3, 0): TerrainType.MOUNTAIN,
    }
    world = World()
    _disc(world, radius=3, extras=extras)
    movement = MovementSystem()
    world.add_system(movement)
    unit = _spawn(world, col=0, row=0, mp=3)

    result = movement.move_unit(unit, (2, 0))
    assert result["success"] is False
    assert result["reason"] == "insufficient_mp"
    assert result["required_movement_points"] == 4
    assert result["path"][0] == [0, 0]
    assert result["path"][-1] == [2, 0]
    assert result["farthest_reachable_on_path"] == {"col": 1, "row": 0}


def test_opening_wei_march_to_plain_reports_path_when_hills_inflate_cost():
    """Filter-A opening: hex distance 4, MP 4, but hills make the route cost 5."""
    from rotk_env.prefabs.config import PlayerType
    from rotk_env.prefabs.world_builder import build_skirmish_world

    world = build_skirmish_world(
        players={Faction.WEI: PlayerType.AI, Faction.SHU: PlayerType.AI},
        mode=GameMode.REAL_TIME,
        seed=1,
        hub_url=None,
        display="none",
    )
    mover = None
    for entity in world.query().with_all(HexPosition, Unit).entities():
        pos = world.get_component(entity, HexPosition)
        if (pos.col, pos.row) == (1, 4):
            mover = entity
            break
    assert mover is not None
    movement = next(s for s in world.systems if isinstance(s, MovementSystem))
    result = movement.move_unit(mover, (0, 1))
    assert result["success"] is False
    assert result["reason"] == "insufficient_mp"
    assert result["required_movement_points"] == 5
    assert result["current_movement_points"] == 4
    assert result["path"][-1] == [0, 1]
    assert result["farthest_reachable_on_path"] == {"col": 0, "row": 2}
    assert HexMath.hex_distance((1, 4), (0, 1)) == 4


def test_effective_cap_below_current_mp_does_not_report_no_path():
    """Capped A* used effective_movement; if that is below path cost but
    current_mp is above it, the old fallback returned no_path instead of
    insufficient_mp or success. Uncapped plan + spendable budget fixes it."""
    world = World()
    _disc(world, radius=3, extras={(1, 0): TerrainType.MOUNTAIN})
    movement = MovementSystem()
    world.add_system(movement)
    # current_mp=4 would afford a 3-cost mountain if we only checked current_mp,
    # but effective_movement follows base_mp=2 so spendable is 2.
    unit = _spawn(world, col=0, row=0, mp=4, base_mp=2)

    result = movement.move_unit(unit, (1, 0))
    assert result["success"] is False
    assert result["reason"] == "insufficient_mp"
    assert result["required_movement_points"] == 3
    assert result["current_movement_points"] == 4
    assert "unit has 2 MP" in result["message"]
    pos = world.get_component(unit, HexPosition)
    assert (pos.col, pos.row) == (0, 0)


def test_move_cannot_leave_the_map_disc():
    world = World()
    _disc(world, radius=2)
    world.add_system(MovementSystem())
    unit = _spawn(world, col=0, row=0, mp=8)
    # (4, 0) is hex-distance 4, outside a radius-2 disc.
    result = world.systems[0].move_unit(unit, (4, 0))
    assert result["success"] is False
    assert result["reason"] == "no_path"
    pos = world.get_component(unit, HexPosition)
    assert (pos.col, pos.row) == (0, 0)


def test_astar_prefers_cheap_plains_over_a_mountain_step():
    extras = {(1, 0): TerrainType.MOUNTAIN}
    world = World()
    _disc(world, radius=3, extras=extras)
    map_data = world.get_singleton_component(MapData)
    from rotk_env.components.terrain import movement_cost_at

    path = PathFinding.find_path(
        (0, 0),
        (2, 0),
        obstacles=set(),
        max_distance=8,
        walkable=set(map_data.tiles),
        step_cost=lambda p: movement_cost_at(world, p),
    )
    assert path
    assert (1, 0) not in path
    assert path[-1] == (2, 0)


def test_water_is_an_obstacle_not_a_walkable_999_tile():
    world = World()
    _disc(world, radius=3, extras={(1, 0): TerrainType.WATER})
    movement = MovementSystem()
    world.add_system(movement)
    unit = _spawn(world, col=0, row=0, mp=8)

    result = movement.move_unit(unit, (1, 0))
    assert result["success"] is False
    assert result["reason"] == "no_path"
    path = PathFinding.find_path(
        (0, 0), (1, 0), movement._get_obstacles(exclude_entity=unit), max_distance=8
    )
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


def test_handle_move_translates_insufficient_mp_from_the_system():
    world = World()
    world.add_singleton_component(GameModeComponent(mode=GameMode.REAL_TIME))
    _disc(world, radius=3, extras={(1, 0): TerrainType.MOUNTAIN})
    world.add_system(MovementSystem())
    unit = _spawn(world, col=0, row=0, mp=2, base_mp=4)

    result = LLMActionHandler(world).handle_move_action(
        {"unit_id": unit, "target_position": {"col": 1, "row": 0}}
    )
    assert result["success"] is False
    assert result["reason"] == "insufficient_mp"
    assert result["failure_reason"] == "insufficient_movement_points"
    assert result["required_movement_points"] == 3
    assert result["path"] == [[0, 0], [1, 0]]
    assert result["farthest_reachable_on_path"] == {"col": 0, "row": 0}
    assert "Shortest path costs 3 MP" in result["details"]
    pos = world.get_component(unit, HexPosition)
    assert (pos.col, pos.row) == (0, 0)


def _tile_at(world, pos):
    from rotk_env.components import Tile

    map_data = world.get_singleton_component(MapData)
    return world.get_component(map_data.tiles[pos], Tile)


def test_occupancy_commits_with_hex_position_on_instant_move():
    from rotk_env.components import Tile

    world = World()
    _disc(world, radius=3)
    map_data = world.get_singleton_component(MapData)
    for pos, tile_entity in map_data.tiles.items():
        world.add_component(tile_entity, Tile(pos))
    world.add_system(MovementSystem())
    unit = _spawn(world, col=0, row=0, mp=4)
    world.get_component(map_data.tiles[(0, 0)], Tile).occupied_by = unit

    result = world.systems[0].move_unit(unit, (1, 0))
    assert result["success"] is True
    assert result["animated"] is False
    pos = world.get_component(unit, HexPosition)
    assert (pos.col, pos.row) == (1, 0)
    assert _tile_at(world, (0, 0)).occupied_by is None
    assert _tile_at(world, (1, 0)).occupied_by == unit


def test_animation_defers_occupancy_until_hex_commits():
    from framework import System
    from rotk_env.components import Tile

    class AnimationSystem(System):
        def initialize(self, world):
            self.world = world

        def subscribe_events(self):
            pass

        def update(self, delta_time: float):
            pass

        def start_unit_movement(self, entity, path):
            self.path = path
            self.entity = entity

    world = World()
    _disc(world, radius=3)
    map_data = world.get_singleton_component(MapData)
    for pos, tile_entity in map_data.tiles.items():
        world.add_component(tile_entity, Tile(pos))
    movement = MovementSystem()
    world.add_system(movement)
    world.add_system(AnimationSystem())
    unit = _spawn(world, col=0, row=0, mp=4)
    world.get_component(map_data.tiles[(0, 0)], Tile).occupied_by = unit

    result = movement.move_unit(unit, (1, 0))
    assert result["success"] is True
    assert result["animated"] is True
    pos = world.get_component(unit, HexPosition)
    assert (pos.col, pos.row) == (0, 0)
    assert _tile_at(world, (0, 0)).occupied_by == unit
    assert _tile_at(world, (1, 0)).occupied_by is None

    movement.commit_hex_position(unit, 1, 0, arrived=True)
    pos = world.get_component(unit, HexPosition)
    assert (pos.col, pos.row) == (1, 0)
    assert _tile_at(world, (0, 0)).occupied_by is None
    assert _tile_at(world, (1, 0)).occupied_by == unit
