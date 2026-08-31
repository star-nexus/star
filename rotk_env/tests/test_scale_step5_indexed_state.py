from framework.ecs.world import World

from rotk_env.components import (
    ActionPoints,
    GameTime,
    HexPosition,
    MovementPoints,
    Unit,
    UnitCount,
)
from rotk_env.prefabs.config import Faction, GameMode, UnitType
from rotk_env.systems.scale_movement_system import MovementSystem
from rotk_env.systems.scale_realtime_system import _IndexedGameOverPolicy
from rotk_env.systems.scale_resource_recovery_system import ResourceRecoverySystem
from rotk_env.utils.unit_spatial_index import (
    rebuild_unit_spatial_index,
    remove_unit_from_spatial_index,
)


def _add_unit(world, faction, col, row, *, count=100, ap=1, mp=3):
    entity = world.create_entity()
    world.add_component(
        entity,
        Unit(unit_type=UnitType.INFANTRY, faction=faction, name=str(entity)),
    )
    world.add_component(entity, HexPosition(col, row))
    world.add_component(entity, UnitCount(current_count=count, max_count=100))
    world.add_component(entity, ActionPoints(current_ap=ap, max_ap=1))
    world.add_component(
        entity,
        MovementPoints(current_mp=mp, max_mp=3, base_mp=3),
    )
    return entity


def test_spatial_index_excludes_only_mover_and_tracks_living_factions():
    world = World()
    wei = _add_unit(world, Faction.WEI, 0, 0)
    wei_same_hex = _add_unit(world, Faction.WEI, 0, 0)
    shu = _add_unit(world, Faction.SHU, 1, 0)

    index = rebuild_unit_spatial_index(world)
    occupied, enemy = index.occupancy_for_mover(wei, Faction.WEI)

    assert (0, 0) in occupied  # the co-located Wei still occupies the start cell
    assert (1, 0) in occupied
    assert (0, 0) not in enemy
    assert (1, 0) in enemy
    assert index.living_factions() == {Faction.WEI, Faction.SHU}

    remove_unit_from_spatial_index(world, shu)
    assert index.living_factions() == {Faction.WEI}
    assert wei_same_hex in index.by_entity


def test_scale_movement_commit_updates_spatial_bucket_and_revision():
    world = World()
    wei = _add_unit(world, Faction.WEI, 0, 0)
    index = rebuild_unit_spatial_index(world)
    revision = index.revision

    movement = MovementSystem()
    movement.world = world
    movement.commit_hex_position(wei, 4, -2)

    assert (world.get_component(wei, HexPosition).col, world.get_component(wei, HexPosition).row) == (4, -2)
    assert (index.by_entity[wei].col, index.by_entity[wei].row) == (4, -2)
    assert index.revision == revision + 1


def test_indexed_realtime_policy_reads_living_counts_without_world_scan():
    world = World()
    wei = _add_unit(world, Faction.WEI, 0, 0)
    shu = _add_unit(world, Faction.SHU, 1, 0)
    rebuild_unit_spatial_index(world)

    policy = _IndexedGameOverPolicy(world)
    assert policy.living_factions() == {Faction.WEI, Faction.SHU}

    remove_unit_from_spatial_index(world, shu)
    world.destroy_entity(shu)
    assert policy.living_factions() == {Faction.WEI}
    assert wei in rebuild_unit_spatial_index(world).by_entity


def test_scale_recovery_keeps_ap_and_mp_board_time_semantics():
    world = World()
    entity = _add_unit(world, Faction.WEI, 0, 0, ap=0, mp=1)
    game_time = GameTime(current_mode=GameMode.REAL_TIME, game_elapsed_time=0.0)
    world.add_singleton_component(game_time)
    rebuild_unit_spatial_index(world)

    recovery = ResourceRecoverySystem()
    recovery.initialize(world)

    # First 0.5 s: AP accrues; MP spend is first observed and resets its timer.
    game_time.game_elapsed_time = 0.5
    recovery.update(0.5)
    assert world.get_component(entity, ActionPoints).current_ap == 0
    assert recovery.mp_elapsed[entity] == 0.0

    # AP reaches its 1 s recovery boundary exactly as in the base system.
    game_time.game_elapsed_time = 1.0
    recovery.update(0.5)
    assert world.get_component(entity, ActionPoints).current_ap == 1
    assert world.get_component(entity, MovementPoints).current_mp == 1

    # MP restores three board seconds after the spend-detection frame.
    game_time.game_elapsed_time = 3.5
    recovery.update(2.5)
    assert world.get_component(entity, MovementPoints).current_mp == 3
