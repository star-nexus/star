from rotk_env.prefabs.config import Faction
from rotk_env.utils.unit_spatial_index import UnitSpatialIndex
from tools.phase5_unitrender_e6_geometry_reuse import (
    _CACHE_ATTR,
    _install_geometry_reuse_patch,
)


def test_geometry_reuse_preserves_fresh_records_and_reuses_only_derived_payload():
    original_record_for_hex = UnitSpatialIndex._record_for_hex
    original_move = UnitSpatialIndex.move_entity
    original_upsert = UnitSpatialIndex.upsert_from_world
    try:
        _install_geometry_reuse_patch()

        # E6 must not reopen E5-2 or change generic/movement APIs.
        assert UnitSpatialIndex.move_entity is original_move
        assert UnitSpatialIndex.upsert_from_world is original_upsert

        index = UnitSpatialIndex()
        first = index._record_for_hex(4, -2, Faction.WEI)
        second = index._record_for_hex(4, -2, Faction.SHU)

        # Fresh record identity is deliberately preserved.
        assert first is not second
        assert first.faction is Faction.WEI
        assert second.faction is Faction.SHU

        # Only the pure derived geometry payload is canonicalized per hex.
        assert first.world_x is second.world_x
        assert first.world_y is second.world_y
        assert first.bucket is second.bucket
        assert (first.col, first.row) == (4, -2)
        assert (second.col, second.row) == (4, -2)

        expected_x, expected_y = index.hex_converter.hex_to_pixel(4, -2)
        assert (first.world_x, first.world_y) == (
            float(expected_x),
            float(expected_y),
        )
        assert first.bucket == index._bucket_for_hex(4, -2)

        cache = getattr(index, _CACHE_ATTR)
        assert len(cache) == 1
        assert cache[(4, -2)] == (first.world_x, first.world_y, first.bucket)

        # A different hex gets a different canonical geometry entry.
        third = index._record_for_hex(5, -2, Faction.WEI)
        assert third is not first
        assert len(cache) == 2
        assert cache[(5, -2)] == (third.world_x, third.world_y, third.bucket)
    finally:
        UnitSpatialIndex._record_for_hex = original_record_for_hex


def test_geometry_reuse_keeps_move_semantics_but_refreshes_record_identity():
    original_record_for_hex = UnitSpatialIndex._record_for_hex
    try:
        _install_geometry_reuse_patch()
        index = UnitSpatialIndex()
        entity = 101
        initial = index._record_for_hex(0, 0, Faction.WEI)
        index._index_record(entity, initial)
        living_before = dict(index.living_counts)

        assert index.move_entity(entity, 4, -2) is True
        moved_once = index.by_entity[entity]
        assert moved_once is not initial
        assert (moved_once.col, moved_once.row) == (4, -2)
        geometry_once = (moved_once.world_x, moved_once.world_y, moved_once.bucket)

        assert index.move_entity(entity, 0, 0) is True
        returned = index.by_entity[entity]
        assert returned is not moved_once
        assert returned is not initial

        assert index.move_entity(entity, 4, -2) is True
        moved_twice = index.by_entity[entity]
        assert moved_twice is not moved_once
        assert moved_twice.world_x is geometry_once[0]
        assert moved_twice.world_y is geometry_once[1]
        assert moved_twice.bucket is geometry_once[2]
        assert index.living_counts == living_before
    finally:
        UnitSpatialIndex._record_for_hex = original_record_for_hex
