from framework.ecs.world import World

from rotk_env.components import HexPosition, Unit, UnitCount
from rotk_env.prefabs.config import Faction, UnitType
from rotk_env.systems.window_movement_system import MovementSystem
from rotk_env.utils.unit_spatial_index import (
    move_unit_spatial_index,
    rebuild_unit_spatial_index,
)


def _add_unit(world, faction, col, row, *, count=100):
    entity = world.create_entity()
    world.add_component(
        entity,
        Unit(unit_type=UnitType.INFANTRY, faction=faction, name=str(entity)),
    )
    world.add_component(entity, HexPosition(col, row))
    world.add_component(entity, UnitCount(current_count=count, max_count=100))
    return entity


def test_specialized_move_uses_index_record_without_world_component_reads(monkeypatch):
    world = World()
    entity = _add_unit(world, Faction.WEI, 0, 0)
    index = rebuild_unit_spatial_index(world)
    living_before = dict(index.living_counts)

    def unexpected_get_component(*_args, **_kwargs):
        raise AssertionError("specialized indexed move must not re-read ECS components")

    monkeypatch.setattr(world, "get_component", unexpected_get_component)

    assert move_unit_spatial_index(world, entity, 1, 0) is True
    record = index.by_entity[entity]
    assert (record.col, record.row) == (1, 0)
    assert entity not in index.by_cell_entities.get((0, 0), set())
    assert entity in index.by_cell_entities[(1, 0)]
    assert index.living_counts == living_before


def test_specialized_move_preserves_stacked_cell_counts_and_living_counts():
    world = World()
    mover = _add_unit(world, Faction.WEI, 0, 0)
    stationary = _add_unit(world, Faction.WEI, 0, 0)
    index = rebuild_unit_spatial_index(world)
    living_before = dict(index.living_counts)

    assert move_unit_spatial_index(world, mover, 1, 0) is True

    assert index.by_cell[(0, 0)][Faction.WEI] == 1
    assert index.by_cell[(1, 0)][Faction.WEI] == 1
    assert index.by_cell_entities[(0, 0)] == {stationary}
    assert index.by_cell_entities[(1, 0)] == {mover}
    assert index.living_counts == living_before


def test_window_movement_commit_avoids_generic_upsert_for_indexed_unit(monkeypatch):
    world = World()
    entity = _add_unit(world, Faction.WEI, 0, 0)
    index = rebuild_unit_spatial_index(world)

    def unexpected_upsert(*_args, **_kwargs):
        raise AssertionError("normal movement commit must use specialized index move")

    monkeypatch.setattr(index, "upsert_from_world", unexpected_upsert)

    movement = MovementSystem()
    movement.world = world
    movement.commit_hex_position(entity, 2, -1)

    position = world.get_component(entity, HexPosition)
    assert position is not None
    assert (position.col, position.row) == (2, -1)
    record = index.by_entity[entity]
    assert (record.col, record.row) == (2, -1)


def test_specialized_move_falls_back_to_generic_upsert_when_entry_is_missing(monkeypatch):
    world = World()
    entity = _add_unit(world, Faction.WEI, 0, 0)
    index = rebuild_unit_spatial_index(world)
    index.remove(entity)

    position = world.get_component(entity, HexPosition)
    assert position is not None
    position.col, position.row = 3, 1

    calls = 0
    original = index.upsert_from_world

    def counted_upsert(target_world, target_entity):
        nonlocal calls
        calls += 1
        return original(target_world, target_entity)

    monkeypatch.setattr(index, "upsert_from_world", counted_upsert)

    assert move_unit_spatial_index(world, entity, 3, 1) is True
    assert calls == 1
    assert (index.by_entity[entity].col, index.by_entity[entity].row) == (3, 1)
