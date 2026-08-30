"""The four movement invariants from `rotk_env/utils/map_query.py`.

1. destination must be unoccupied, either faction
2. path traversal is faction-relative: enemies block, friendlies are transparent
   and cost the terrain underneath
3. legality is checked once, at order acceptance; never revalidated
4. moves do not reserve their destination, so co-location is legal

No hub, no pygame window.
"""

from framework import System
from framework.ecs.world import World
from rotk_env.components import (
    ActionPoints,
    GameModeComponent,
    HexPosition,
    MapData,
    MovementPoints,
    Terrain,
    Tile,
    Unit,
    UnitCount,
)
from rotk_env.prefabs.config import Faction, GameMode, TerrainType, UnitType
from rotk_env.systems.llm_action_handler import LLMActionHandler
from rotk_env.systems.movement_system import MovementSystem
from rotk_env.utils.hex_utils import HexMath
from rotk_env.utils.map_query import occupied_cells, path_blockers, reachable_hexes


class AnimationSystem(System):
    """Stands in for the real AnimationSystem so moves take time.

    Named exactly `AnimationSystem` on purpose: `MovementSystem` looks the
    animation system up by class name, and without it every move commits
    instantly, which is the one thing these tests must not do.
    """

    def __init__(self):
        super().__init__(priority=15)
        self.jobs = []

    def initialize(self, world):
        self.world = world

    def subscribe_events(self):
        pass

    def update(self, delta_time: float):
        pass

    def start_unit_movement(self, entity, path):
        self.jobs.append((entity, list(path)))


def _board(world, cells, terrain=None):
    terrain = terrain or {}
    map_data = MapData(width=64, height=64)
    world.add_singleton_component(map_data)
    for cell in cells:
        tile = world.create_entity()
        world.add_component(tile, HexPosition(*cell))
        world.add_component(tile, Terrain(terrain.get(cell, TerrainType.PLAIN)))
        world.add_component(tile, Tile(cell))
        map_data.tiles[cell] = tile
    return map_data


def _corridor(world, length, terrain=None):
    """A 1-wide straight line of hexes: no detour exists around anything on it."""
    return _board(world, [(col, 0) for col in range(length)], terrain)


def _disc(world, radius, terrain=None):
    cells = [
        (col, row)
        for col in range(-radius, radius + 1)
        for row in range(-radius, radius + 1)
        if HexMath.hex_distance((0, 0), (col, row)) <= radius
    ]
    return _board(world, cells, terrain)


def _spawn(world, col, row, *, faction=Faction.WEI, mp=4, unit_type=UnitType.INFANTRY):
    entity = world.create_entity()
    world.add_component(entity, Unit(unit_type=unit_type, faction=faction, name="u"))
    world.add_component(entity, HexPosition(col, row))
    world.add_component(entity, UnitCount(current_count=100, max_count=100))
    world.add_component(entity, MovementPoints(current_mp=mp, max_mp=mp, base_mp=mp))
    world.add_component(entity, ActionPoints(current_ap=2, max_ap=2))
    return entity


def _hex_of(world, entity):
    pos = world.get_component(entity, HexPosition)
    return (pos.col, pos.row)


def _realtime_world():
    world = World()
    world.add_singleton_component(GameModeComponent(mode=GameMode.REAL_TIME))
    return world


# ---------------------------------------------------------------- invariant 2


def test_friendly_unit_on_the_route_is_walked_through():
    """Corridor with a friendly parked mid-way: the mover still gets past it."""
    world = _realtime_world()
    _corridor(world, 4)
    movement = MovementSystem()
    world.add_system(movement)
    mover = _spawn(world, 0, 0, mp=4)
    _spawn(world, 1, 0, faction=Faction.WEI)

    result = movement.move_unit(mover, (2, 0))
    assert result["success"] is True
    assert result["path"] == [(0, 0), (1, 0), (2, 0)]
    assert _hex_of(world, mover) == (2, 0)


def test_friendly_unit_costs_the_terrain_underneath_not_zero_and_not_blocked():
    """A friendly standing on forest still charges the forest enter-cost."""

    def _cost(with_friendly):
        world = _realtime_world()
        _corridor(world, 4, {(1, 0): TerrainType.FOREST})
        movement = MovementSystem()
        world.add_system(movement)
        mover = _spawn(world, 0, 0, mp=4)
        if with_friendly:
            _spawn(world, 1, 0, faction=Faction.WEI)
        result = movement.move_unit(mover, (2, 0))
        assert result["success"] is True
        return result["cost"]

    empty_forest = _cost(with_friendly=False)
    occupied_forest = _cost(with_friendly=True)
    assert empty_forest == 3  # forest 2 + plain 1
    assert occupied_forest == empty_forest


def test_enemy_unit_is_impassable():
    world = _realtime_world()
    _corridor(world, 4)
    movement = MovementSystem()
    world.add_system(movement)
    mover = _spawn(world, 0, 0, mp=4)
    _spawn(world, 1, 0, faction=Faction.SHU)

    result = movement.move_unit(mover, (2, 0))
    assert result["success"] is False
    assert result["reason"] == "no_path"
    assert _hex_of(world, mover) == (0, 0)


def test_enemy_blocks_but_friendly_does_not_on_the_same_board():
    """Same corridor, same hex, only the occupant's faction differs."""

    def _try(faction):
        world = _realtime_world()
        _corridor(world, 4)
        movement = MovementSystem()
        world.add_system(movement)
        mover = _spawn(world, 0, 0, mp=4)
        _spawn(world, 1, 0, faction=faction)
        return movement.move_unit(mover, (2, 0))["success"]

    assert _try(Faction.WEI) is True
    assert _try(Faction.SHU) is False


def test_path_blockers_hold_enemies_and_terrain_but_not_friendlies():
    world = _realtime_world()
    _disc(world, 2, {(0, 1): TerrainType.WATER})
    mover = _spawn(world, 0, 0)
    _spawn(world, 1, 0, faction=Faction.WEI)
    _spawn(world, -1, 0, faction=Faction.SHU)

    blockers = path_blockers(world, Faction.WEI, exclude_entity=mover)
    assert (-1, 0) in blockers  # enemy
    assert (0, 1) in blockers  # water
    assert (1, 0) not in blockers  # friendly is transparent

    # Destination occupancy does not care about faction.
    occupied = occupied_cells(world, exclude_entity=mover)
    assert {(1, 0), (-1, 0)} <= occupied
    assert (0, 1) not in occupied


# ---------------------------------------------------------------- invariant 1


def test_destination_occupied_by_friendly_is_rejected():
    world = _realtime_world()
    _corridor(world, 4)
    movement = MovementSystem()
    world.add_system(movement)
    mover = _spawn(world, 0, 0, mp=4)
    _spawn(world, 1, 0, faction=Faction.WEI)

    result = movement.move_unit(mover, (1, 0))
    assert result["success"] is False
    assert result["reason"] == "destination_occupied"
    assert _hex_of(world, mover) == (0, 0)


def test_destination_occupied_by_enemy_is_rejected_the_same_way():
    world = _realtime_world()
    _corridor(world, 4)
    movement = MovementSystem()
    world.add_system(movement)
    mover = _spawn(world, 0, 0, mp=4)
    _spawn(world, 1, 0, faction=Faction.SHU)

    result = movement.move_unit(mover, (1, 0))
    assert result["success"] is False
    assert result["reason"] == "destination_occupied"


def test_destination_occupied_payload_does_not_name_the_occupant():
    """The occupant may be a unit this faction cannot see."""
    world = _realtime_world()
    _corridor(world, 4)
    movement = MovementSystem()
    world.add_system(movement)
    mover = _spawn(world, 0, 0, mp=4)
    blocker = _spawn(world, 1, 0, faction=Faction.SHU)

    result = movement.move_unit(mover, (1, 0))
    flat = repr(result)
    assert str(blocker) not in flat
    assert "shu" not in flat.lower()
    assert "faction" not in flat.lower()


def test_reachable_excludes_occupied_hexes_but_keeps_what_lies_beyond():
    world = _realtime_world()
    _corridor(world, 4)
    mover = _spawn(world, 0, 0, mp=4)
    _spawn(world, 1, 0, faction=Faction.WEI)

    reachable = reachable_hexes(world, (0, 0), 4, mover=mover)
    assert (1, 0) not in reachable  # friendly stands there
    assert {(2, 0), (3, 0)} <= reachable  # but the corridor stays open


def test_archer_boxed_in_by_friendlies_still_has_a_move_range():
    """Regression for the opening report: archer 234 had 5 reachable hexes
    because its own infantry ringed it. Friendly transparency reopens the fan;
    the hexes they stand on are still not legal destinations."""
    world = _realtime_world()
    _disc(world, 3)
    mover = _spawn(world, 0, 0, mp=4, unit_type=UnitType.ARCHER)
    ring = HexMath.hex_neighbors(0, 0)
    for col, row in ring:
        _spawn(world, col, row, faction=Faction.WEI)

    reachable = reachable_hexes(world, (0, 0), 4, mover=mover)
    reachable.discard((0, 0))

    assert not reachable.intersection(ring)
    assert reachable, "a fully ringed unit must still be able to move past its own line"
    assert any(HexMath.hex_distance((0, 0), cell) >= 2 for cell in reachable)


def test_enemy_ring_really_does_pin_the_unit():
    """The mirror of the regression: enemies are the blockers, so they pin."""
    world = _realtime_world()
    _disc(world, 3)
    mover = _spawn(world, 0, 0, mp=4)
    for col, row in HexMath.hex_neighbors(0, 0):
        _spawn(world, col, row, faction=Faction.SHU)

    reachable = reachable_hexes(world, (0, 0), 4, mover=mover)
    reachable.discard((0, 0))
    assert reachable == set()


# ------------------------------------------------------------ invariants 3, 4


def test_two_factions_may_be_accepted_for_the_same_empty_hex():
    """Invariant 4: no reservation. Both orders were legal when processed."""
    world = _realtime_world()
    _corridor(world, 5)
    movement = MovementSystem()
    world.add_system(movement)
    anim = AnimationSystem()
    world.add_system(anim)
    wei = _spawn(world, 0, 0, mp=4, faction=Faction.WEI)
    shu = _spawn(world, 4, 0, mp=4, faction=Faction.SHU)

    assert movement.move_unit(wei, (2, 0))["success"] is True
    assert movement.move_unit(shu, (2, 0))["success"] is True

    for entity, path in anim.jobs:
        for step in path[1:]:
            movement.commit_hex_position(
                entity, step[0], step[1], arrived=step == path[-1]
            )

    assert _hex_of(world, wei) == (2, 0)
    assert _hex_of(world, shu) == (2, 0)


def test_an_accepted_move_is_not_revalidated_mid_route():
    """Invariant 3: the route is checked once. A unit that parks on the route
    after acceptance does not stop the mover, and does not get displaced."""
    world = _realtime_world()
    _corridor(world, 5)
    movement = MovementSystem()
    world.add_system(movement)
    anim = AnimationSystem()
    world.add_system(anim)
    mover = _spawn(world, 0, 0, mp=4, faction=Faction.WEI)
    intruder = _spawn(world, 4, 0, mp=4, faction=Faction.SHU)

    assert movement.move_unit(mover, (3, 0))["success"] is True
    mover_path = anim.jobs[0][1]
    assert mover_path == [(0, 0), (1, 0), (2, 0), (3, 0)]

    # The intruder takes a hex in the middle of the accepted route.
    assert movement.move_unit(intruder, (2, 0))["success"] is True
    intruder_path = anim.jobs[1][1]
    for step in intruder_path[1:]:
        movement.commit_hex_position(intruder, step[0], step[1], arrived=True)
    assert _hex_of(world, intruder) == (2, 0)

    # The mover walks its accepted route regardless, co-locating in passing.
    movement.commit_hex_position(mover, 1, 0)
    movement.commit_hex_position(mover, 2, 0)
    assert _hex_of(world, mover) == _hex_of(world, intruder) == (2, 0)
    movement.commit_hex_position(mover, 3, 0, arrived=True)
    assert _hex_of(world, mover) == (3, 0)
    assert _hex_of(world, intruder) == (2, 0)


def test_a_hex_holding_two_factions_blocks_and_is_not_a_destination():
    """Co-location is transient but must read consistently while it lasts."""
    world = _realtime_world()
    _disc(world, 2)
    mover = _spawn(world, 0, 0, faction=Faction.WEI)
    _spawn(world, 1, 0, faction=Faction.WEI)
    _spawn(world, 1, 0, faction=Faction.SHU)

    assert (1, 0) in path_blockers(world, Faction.WEI, exclude_entity=mover)
    assert (1, 0) in occupied_cells(world, exclude_entity=mover)


# ------------------------------------------------------------ mask == execute


def _mixed_board(world):
    terrain = {
        (1, 0): TerrainType.MOUNTAIN,
        (0, 1): TerrainType.FOREST,
        (1, 1): TerrainType.HILL,
        (-1, 0): TerrainType.WATER,
        (2, -1): TerrainType.WATER,
        (0, -1): TerrainType.URBAN,
    }
    map_data = _disc(world, 3, terrain)
    mover = _spawn(world, 0, 0, mp=4, faction=Faction.WEI)
    _spawn(world, 1, -1, faction=Faction.WEI)
    _spawn(world, 0, 2, faction=Faction.WEI)
    _spawn(world, 2, 0, faction=Faction.SHU)
    return map_data, mover


def test_reachable_mask_matches_execute_hex_by_hex():
    world = _realtime_world()
    world.add_system(MovementSystem())
    map_data, mover = _mixed_board(world)
    mask = {
        (cell["col"], cell["row"])
        for cell in LLMActionHandler(world)._unit_reachable(mover)
    }

    for cell in sorted(map_data.tiles):
        probe = _realtime_world()
        probe.add_system(MovementSystem())
        _, probe_mover = _mixed_board(probe)
        accepted = (
            LLMActionHandler(probe)
            .handle_move_action(
                {"unit_id": probe_mover, "target_position": {"col": cell[0], "row": cell[1]}}
            )
            .get("success", False)
        )
        assert bool(accepted) == (cell in mask), cell

    assert mask, "the mixed board should leave the mover somewhere to go"


def test_observation_channel_agrees_with_the_mask():
    """The per-tile `observation` reachability reads the same oracle."""
    world = _realtime_world()
    world.add_system(MovementSystem())
    map_data, mover = _mixed_board(world)
    handler = LLMActionHandler(world)
    movement_points = world.get_component(mover, MovementPoints)
    unit_count = world.get_component(mover, UnitCount)
    mask = {
        (cell["col"], cell["row"]) for cell in handler._unit_reachable(mover)
    }

    for cell in sorted(map_data.tiles):
        if cell == (0, 0):
            continue
        info = handler._get_movement_accessibility_info(
            mover, (0, 0), cell, movement_points, unit_count
        )
        assert bool(info["reachable"]) == (cell in mask), (cell, info)
        if cell in occupied_cells(world, exclude_entity=mover):
            assert info.get("reason") == "destination_occupied"
        elif not info["reachable"] and info.get("reason") not in (
            "no_path",
            "insufficient_mp",
        ):
            raise AssertionError((cell, info))


def test_insufficient_mp_does_not_suggest_an_occupied_hex():
    """The cheapest route may walk through a friendly. Stopping there is illegal."""
    world = _realtime_world()
    _corridor(world, 4)
    movement = MovementSystem()
    world.add_system(movement)
    mover = _spawn(world, 0, 0, mp=1)
    _spawn(world, 1, 0, faction=Faction.WEI)

    result = movement.move_unit(mover, (3, 0))
    assert result["success"] is False
    assert result["reason"] == "insufficient_mp"
    farthest = result["farthest_reachable_on_path"]
    assert (farthest["col"], farthest["row"]) != (1, 0)
    suggested = result.get("suggested_action")
    if suggested:
        dest = suggested["params"]["target_position"]
        assert (dest["col"], dest["row"]) != (1, 0)


def test_ui_overlay_and_wire_share_one_budget():
    """The blue overlay used current_mp while the wire used the effective cap."""
    world = _realtime_world()
    world.add_system(MovementSystem())
    _, mover = _mixed_board(world)
    movement_points = world.get_component(mover, MovementPoints)
    unit_count = world.get_component(mover, UnitCount)
    movement_points.current_mp = 4
    movement_points.base_mp = 2

    assert movement_points.spendable(unit_count) == 2

    overlay = reachable_hexes(
        world, (0, 0), movement_points.spendable(unit_count), mover=mover
    )
    overlay.discard((0, 0))
    mask = {
        (cell["col"], cell["row"])
        for cell in LLMActionHandler(world)._unit_reachable(mover)
    }
    assert overlay == mask
