"""Regression tests for dirty-driven incremental fog-of-war visibility."""

from framework.ecs.world import World

from rotk_env.components import FogOfWar, HexPosition, Unit, Vision
from rotk_env.prefabs.config import Faction, UnitType
from rotk_env.systems.vision_system import VisionSystem, mark_vision_dirty


def _spawn(world, *, faction=Faction.WEI, col=0, row=0, vision_range=1):
    entity = world.create_entity()
    world.add_component(
        entity,
        Unit(unit_type=UnitType.INFANTRY, faction=faction, name="vision-test"),
    )
    world.add_component(entity, HexPosition(col, row))
    world.add_component(entity, Vision(range=vision_range))
    return entity


def _system(world):
    fog = FogOfWar(enabled=True)
    world.add_singleton_component(fog)
    system = VisionSystem()
    system.initialize(world)
    return system, fog


def test_incremental_refcounts_preserve_overlap_until_last_observer_leaves():
    world = World()
    a = _spawn(world, col=0, row=0)
    b = _spawn(world, col=0, row=0)
    system, fog = _system(world)

    system.update(0.0)
    original = set(fog.faction_vision[Faction.WEI])
    assert (0, 0) in original
    assert system._faction_tile_counts[Faction.WEI][(0, 0)] == 2

    pos_a = world.get_component(a, HexPosition)
    pos_a.col, pos_a.row = 4, 0
    mark_vision_dirty(world, a)
    system.update(0.0)

    # B still observes the original disk, so A leaving must not remove it.
    assert original <= fog.faction_vision[Faction.WEI]
    assert system._faction_tile_counts[Faction.WEI][(0, 0)] == 1

    pos_b = world.get_component(b, HexPosition)
    pos_b.col, pos_b.row = 4, 0
    mark_vision_dirty(world, b)
    system.update(0.0)

    # No observer remains at the old location; current visibility drops it,
    # while explored history deliberately keeps it.
    assert (0, 0) not in fog.faction_vision[Faction.WEI]
    assert (0, 0) in fog.explored_tiles[Faction.WEI]


def test_geometry_cache_is_shared_by_units_with_same_center_and_range():
    world = World()
    _spawn(world, col=2, row=3, vision_range=2)
    _spawn(world, col=2, row=3, vision_range=2)
    system, _fog = _system(world)

    system.update(0.0)
    stats = system.get_stats()

    assert stats["geometry_cache_misses"] == 1
    assert stats["geometry_cache_hits"] == 1
    assert stats["geometry_cache_size"] == 1


def test_mark_dirty_updates_only_changed_unit_and_keeps_explored_history():
    world = World()
    mover = _spawn(world, col=0, row=0, vision_range=1)
    static = _spawn(world, col=10, row=10, vision_range=1)
    system, fog = _system(world)

    system.update(0.0)
    static_vision = set(world.get_component(static, Vision).visible_tiles)
    old_mover_vision = set(world.get_component(mover, Vision).visible_tiles)
    recomputes_before = system.get_stats()["recomputes"]

    pos = world.get_component(mover, HexPosition)
    pos.col, pos.row = 3, 0
    mark_vision_dirty(world, mover)
    system.update(0.0)

    assert system.get_stats()["recomputes"] == recomputes_before + 1
    assert world.get_component(static, Vision).visible_tiles == static_vision
    assert old_mover_vision <= fog.explored_tiles[Faction.WEI]


def test_legacy_world_direct_position_write_is_detected_next_tick_without_mark():
    """Non-indexed worlds retain the old immediate direct-write semantics."""
    world = World()
    entity = _spawn(world, col=0, row=0, vision_range=1)
    system, _fog = _system(world)

    system.update(0.0)
    before = set(world.get_component(entity, Vision).visible_tiles)

    pos = world.get_component(entity, HexPosition)
    pos.col, pos.row = 5, 0
    # Intentionally do not call mark_vision_dirty: base/test worlds have no
    # UnitSpatialIndex, so the compatibility audit runs every tick.
    system.update(0.0)

    after = set(world.get_component(entity, Vision).visible_tiles)
    assert after != before
    assert (5, 0) in after
    assert (0, 0) not in after


def test_invalidate_all_bumps_geometry_revision_and_recomputes_every_observer():
    world = World()
    a = _spawn(world, col=0, row=0, vision_range=1)
    b = _spawn(world, col=3, row=0, vision_range=1)
    system, _fog = _system(world)

    system.update(0.0)
    old_revision = system._terrain_revision
    assert system._geometry_cache
    recomputes_before = system.get_stats()["recomputes"]

    system.invalidate_all()
    assert system._terrain_revision == old_revision + 1
    assert system._geometry_cache == {}
    assert world.get_component(a, Vision).dirty is True
    assert world.get_component(b, Vision).dirty is True

    system.update(0.0)
    assert system.get_stats()["recomputes"] == recomputes_before + 2
    assert world.get_component(a, Vision).dirty is False
    assert world.get_component(b, Vision).dirty is False
