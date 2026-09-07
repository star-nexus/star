from dataclasses import fields

from framework.ecs.world import World

from rotk_env.components import HexPosition, MapData, Unit, UnitCount
from rotk_env.prefabs.config import Faction, UnitType
from rotk_env.utils.unit_spatial_index import rebuild_unit_spatial_index
from tools.phase5_unitrender_e6_2_slotted_composition import (
    _install_slotted_record_patch,
    _verify_source_contract,
)


def _add_unit(world, col=0, row=0, faction=Faction.WEI):
    entity = world.create_entity()
    world.add_component(
        entity,
        Unit(unit_type=UnitType.INFANTRY, faction=faction, name=str(entity)),
    )
    world.add_component(entity, HexPosition(col, row))
    world.add_component(entity, UnitCount(current_count=100, max_count=100))
    return entity


def _add_board(world, cells):
    world.add_singleton_component(
        MapData(
            width=max(1, len(cells)),
            height=max(1, len(cells)),
            tiles={cell: index + 1 for index, cell in enumerate(cells)},
        )
    )


def test_source_contract_is_exact_retained_e6_1():
    _verify_source_contract()


def test_slotted_patch_changes_representation_only():
    import rotk_env.utils.unit_spatial_index as spatial

    original = spatial.UnitSpatialRecord
    original_field_names = tuple(field.name for field in fields(original))
    _install_slotted_record_patch()
    patched = spatial.UnitSpatialRecord

    assert patched is not original
    assert tuple(field.name for field in fields(patched)) == original_field_names
    assert patched.__dataclass_params__.frozen is True
    assert hasattr(patched, "__slots__")
    assert tuple(patched.__slots__) == original_field_names

    record = patched(1, 2, Faction.WEI, 3.0, 4.0, (0, 0))
    assert not hasattr(record, "__dict__")
    assert (record.col, record.row, record.faction) == (1, 2, Faction.WEI)
    assert (record.world_x, record.world_y, record.bucket) == (3.0, 4.0, (0, 0))


def test_e6_1_geometry_reuse_and_fresh_record_identity_survive_slots():
    import rotk_env.utils.unit_spatial_index as spatial

    _install_slotted_record_patch()
    world = World()
    _add_board(world, [(0, 0), (1, 0)])
    _add_unit(world, 0, 0)
    index = rebuild_unit_spatial_index(world)

    first = index._record_for_hex(1, 0, Faction.WEI)
    second = index._record_for_hex(1, 0, Faction.WEI)

    assert isinstance(first, spatial.UnitSpatialRecord)
    assert first is not second
    assert first == second
    assert first.world_x is second.world_x
    assert first.world_y is second.world_y
    assert first.bucket is second.bucket
    assert len(index._geometry_by_hex) <= len(index._geometry_board_hexes)


def test_movement_update_preserves_index_semantics_with_slots():
    _install_slotted_record_patch()
    world = World()
    _add_board(world, [(0, 0), (1, 0), (2, 0)])
    entity = _add_unit(world, 0, 0)
    index = rebuild_unit_spatial_index(world)

    old = index.by_entity[entity]
    assert index.move_entity(entity, 1, 0) is True
    new = index.by_entity[entity]

    assert new is not old
    assert (new.col, new.row, new.faction) == (1, 0, Faction.WEI)
    assert entity not in index.by_cell_entities.get((0, 0), set())
    assert entity in index.by_cell_entities[(1, 0)]
    assert index.living_counts[Faction.WEI] == 1
