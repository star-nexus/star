from framework.ecs.world import World

from rotk_env.components import HexPosition, MovementPoints, Unit, UnitCount
from rotk_env.prefabs.config import Faction, UnitType
from rotk_env.systems.scale_effect_render_system import EffectRenderSystem


def _add_unit(world: World, faction: Faction, col: int, row: int) -> int:
    entity = world.create_entity()
    world.add_component(
        entity,
        Unit(unit_type=UnitType.INFANTRY, faction=faction, name=f"u{entity}"),
    )
    world.add_component(entity, HexPosition(col, row))
    return entity


def test_spatial_index_is_reused_and_updates_only_changed_units():
    world = World()
    wei = _add_unit(world, Faction.WEI, 0, 0)
    shu = _add_unit(world, Faction.SHU, 1, 0)

    system = EffectRenderSystem()
    system.initialize(world)

    index_object = system._unit_position_index
    initial_revision = system._spatial_revision

    assert index_object[(0, 0)] == [(wei, Faction.WEI)]
    assert index_object[(1, 0)] == [(shu, Faction.SHU)]

    indexed, changes = system._sync_position_index()
    assert indexed == 2
    assert changes == 0
    assert system._unit_position_index is index_object
    assert system._spatial_revision == initial_revision

    position = world.get_component(wei, HexPosition)
    position.col = 2
    position.row = 1

    indexed, changes = system._sync_position_index()
    assert indexed == 2
    assert changes == 1
    assert system._unit_position_index is index_object
    assert (0, 0) not in index_object
    assert index_object[(2, 1)] == [(wei, Faction.WEI)]
    assert index_object[(1, 0)] == [(shu, Faction.SHU)]
    assert system._spatial_revision == initial_revision + 1


def test_movement_cache_key_uses_spatial_revision_not_full_occupancy_tuple():
    world = World()
    entity = _add_unit(world, Faction.WEI, 0, 0)
    system = EffectRenderSystem()
    system.initialize(world)

    position = world.get_component(entity, HexPosition)
    movement = MovementPoints(base_mp=5, current_mp=5, max_mp=5)
    unit_count = UnitCount(current_count=100, max_count=100)

    key_before = system._movement_state_key(entity, position, movement, unit_count)
    assert key_before[-1] == system._spatial_revision

    other = _add_unit(world, Faction.SHU, 3, 3)
    indexed, changes = system._sync_position_index()
    assert indexed == 2
    assert changes == 1

    key_after = system._movement_state_key(entity, position, movement, unit_count)
    assert key_after[:-1] == key_before[:-1]
    assert key_after[-1] == system._spatial_revision
    assert key_after[-1] == key_before[-1] + 1
    assert system._unit_position_index[(3, 3)] == [(other, Faction.SHU)]
