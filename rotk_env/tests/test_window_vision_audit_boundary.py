"""Regression coverage for the indexed-window Vision audit boundary."""

from framework.ecs.world import World

from rotk_env.components import FogOfWar, HexPosition, Unit, Vision
from rotk_env.prefabs.config import Faction, UnitType
from rotk_env.systems.window_vision_system import VisionSystem


def _spawn(world: World, *, col: int = 0, row: int = 0) -> int:
    entity = world.create_entity()
    world.add_component(
        entity,
        Unit(unit_type=UnitType.INFANTRY, faction=Faction.WEI, name="audit-test"),
    )
    world.add_component(entity, HexPosition(col, row))
    world.add_component(entity, Vision(range=1))
    return entity


def _system(world: World) -> VisionSystem:
    world.add_singleton_component(FogOfWar(enabled=True))
    system = VisionSystem()
    system.initialize(world)
    return system


def test_force_all_bootstrap_audit_remains_enabled_with_spatial_index():
    world = World()
    entity = _spawn(world)
    # Vision only needs index presence to select the indexed-window policy.
    setattr(world, "_unit_spatial_index", object())
    system = _system(world)

    scanned = system._audit_all_units(force_all=True)

    assert scanned == 1
    assert entity in system._dirty


def test_nonindexed_window_audit_still_detects_direct_position_write():
    world = World()
    entity = _spawn(world)
    system = _system(world)

    system.update(0.0)
    system._dirty.clear()

    pos = world.get_component(entity, HexPosition)
    pos.col, pos.row = 5, 0

    scanned = system._audit_all_units(force_all=False)

    assert scanned == 1
    assert entity in system._dirty


def test_indexed_periodic_audit_is_noop_without_explicit_invalidation():
    world = World()
    entity = _spawn(world)
    setattr(world, "_unit_spatial_index", object())
    system = _system(world)

    # Bootstrap remains authoritative and clears through the normal update path.
    system.update(0.0)
    system._dirty.clear()

    pos = world.get_component(entity, HexPosition)
    pos.col, pos.row = 5, 0

    scanned = system._audit_all_units(force_all=False)

    assert scanned == 0
    assert entity not in system._dirty
