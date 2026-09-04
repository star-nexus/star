"""Shared unit spatial state for interactive window worlds.

Window rendering, input, and movement share one derived index
of authoritative ``HexPosition`` state and updates it only when movement commits
or combat removes a unit.

The index is deliberately a cache, not a second source of truth:
``HexPosition``/``Unit``/``UnitCount`` remain authoritative.  Worlds that do not
install the index retain scan-based fallbacks in their callers.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import floor
from typing import Dict, Iterable, Optional, Set, Tuple

from ..components import HexPosition, Unit, UnitCount
from ..prefabs.config import Faction, GameConfig
from .hex_utils import HexConverter, HexMath

Hex = Tuple[int, int]
Bucket = Tuple[int, int]
_INDEX_ATTR = "_unit_spatial_index"


@dataclass(frozen=True)
class UnitSpatialRecord:
    col: int
    row: int
    faction: Faction
    world_x: float
    world_y: float
    bucket: Bucket


class UnitSpatialIndex:
    """Event-driven occupancy, coarse spatial buckets, and living counts."""

    def __init__(self, bucket_size: Optional[int] = None):
        self.bucket_size = max(
            64, int(bucket_size or (GameConfig.HEX_SIZE * 6))
        )
        self.hex_converter = HexConverter(
            GameConfig.HEX_SIZE, GameConfig.HEX_ORIENTATION
        )
        self.by_entity: Dict[int, UnitSpatialRecord] = {}
        self.by_cell: Dict[Hex, Dict[Faction, int]] = {}
        self.by_cell_entities: Dict[Hex, Set[int]] = {}
        self.by_bucket: Dict[Bucket, Set[int]] = {}
        # Bucket revisions let local consumers invalidate only when occupancy
        # changed near the region they actually depend on.  Revisions remain
        # even after a bucket becomes empty so an empty -> occupied transition
        # is observable by an existing cache key.
        self.bucket_revisions: Dict[Bucket, int] = {}
        self.living_counts: Dict[Faction, int] = {}
        self.revision = 0

    def _record_for_hex(
        self, col: int, row: int, faction: Faction
    ) -> UnitSpatialRecord:
        """Build one derived record, including the render-space center once."""
        world_x, world_y = self.hex_converter.hex_to_pixel(col, row)
        bucket = (
            floor(world_x / self.bucket_size),
            floor(world_y / self.bucket_size),
        )
        return UnitSpatialRecord(
            col=col,
            row=row,
            faction=faction,
            world_x=float(world_x),
            world_y=float(world_y),
            bucket=bucket,
        )

    def _bucket_for_hex(self, col: int, row: int) -> Bucket:
        world_x, world_y = self.hex_converter.hex_to_pixel(col, row)
        return (
            floor(world_x / self.bucket_size),
            floor(world_y / self.bucket_size),
        )

    def _bump_bucket(self, bucket: Bucket) -> None:
        self.bucket_revisions[bucket] = self.bucket_revisions.get(bucket, 0) + 1

    def _index_record(self, entity: int, record: UnitSpatialRecord) -> None:
        self.by_entity[entity] = record

        cell_key = (record.col, record.row)
        cell = self.by_cell.setdefault(cell_key, {})
        cell[record.faction] = cell.get(record.faction, 0) + 1
        self.by_cell_entities.setdefault(cell_key, set()).add(entity)
        self.by_bucket.setdefault(record.bucket, set()).add(entity)
        self.living_counts[record.faction] = self.living_counts.get(record.faction, 0) + 1
        self._bump_bucket(record.bucket)

    def _add_record(self, entity: int, col: int, row: int, faction: Faction) -> None:
        self._index_record(entity, self._record_for_hex(col, row, faction))

    def _drop_record(self, entity: int, record: UnitSpatialRecord) -> None:
        cell_key = (record.col, record.row)
        cell = self.by_cell.get(cell_key)
        if cell is not None:
            remaining = cell.get(record.faction, 0) - 1
            if remaining > 0:
                cell[record.faction] = remaining
            else:
                cell.pop(record.faction, None)
            if not cell:
                self.by_cell.pop(cell_key, None)

        cell_entities = self.by_cell_entities.get(cell_key)
        if cell_entities is not None:
            cell_entities.discard(entity)
            if not cell_entities:
                self.by_cell_entities.pop(cell_key, None)

        bucket = self.by_bucket.get(record.bucket)
        if bucket is not None:
            bucket.discard(entity)
            if not bucket:
                self.by_bucket.pop(record.bucket, None)

        remaining = self.living_counts.get(record.faction, 0) - 1
        if remaining > 0:
            self.living_counts[record.faction] = remaining
        else:
            self.living_counts.pop(record.faction, None)
        self._bump_bucket(record.bucket)

    def rebuild(self, world) -> None:
        self.by_entity.clear()
        self.by_cell.clear()
        self.by_cell_entities.clear()
        self.by_bucket.clear()
        self.bucket_revisions.clear()
        self.living_counts.clear()

        for entity in world.query().with_all(Unit, HexPosition, UnitCount).entities():
            unit = world.get_component(entity, Unit)
            pos = world.get_component(entity, HexPosition)
            count = world.get_component(entity, UnitCount)
            if unit is None or pos is None or count is None or count.current_count <= 0:
                continue
            self._add_record(entity, pos.col, pos.row, unit.faction)
        self.revision += 1

    def upsert_from_world(self, world, entity: int) -> bool:
        """Refresh one entity after an authoritative position/state mutation."""
        old = self.by_entity.get(entity)
        unit = world.get_component(entity, Unit)
        pos = world.get_component(entity, HexPosition)
        count = world.get_component(entity, UnitCount)

        if unit is None or pos is None or count is None or count.current_count <= 0:
            return self.remove(entity)

        new_record = self._record_for_hex(pos.col, pos.row, unit.faction)
        if old == new_record:
            return False

        if old is not None:
            self._drop_record(entity, old)
        self._index_record(entity, new_record)
        self.revision += 1
        return True

    def remove(self, entity: int) -> bool:
        old = self.by_entity.pop(entity, None)
        if old is None:
            return False
        self._drop_record(entity, old)
        self.revision += 1
        return True

    def living_factions(self) -> Set[Faction]:
        return {faction for faction, count in self.living_counts.items() if count > 0}

    def entities_at_cell(self, cell: Hex) -> Set[int]:
        """Snapshot of living entity ids currently committed to ``cell``."""
        return set(self.by_cell_entities.get(cell, ()))

    def enemy_at_cell(
        self, cell: Hex, friendly_faction: Optional[Faction]
    ) -> Optional[int]:
        """Return one enemy entity at ``cell`` without an ECS/world scan."""
        for entity in self.by_cell_entities.get(cell, ()):
            record = self.by_entity.get(entity)
            if record is not None and record.faction != friendly_faction:
                return entity
        return None

    def occupancy_for_mover(
        self, mover: Optional[int], mover_faction: Optional[Faction]
    ) -> tuple[Set[Hex], Set[Hex]]:
        """Return (occupied destinations, enemy-held traversal blockers).

        Both sets are derived in one pass over occupied cells.  ``mover`` is
        removed from its own cell while preserving any co-located units.
        """
        excluded = self.by_entity.get(mover) if mover is not None else None
        occupied: Set[Hex] = set()
        enemy_held: Set[Hex] = set()

        for cell, faction_counts in self.by_cell.items():
            has_any = False
            has_enemy = False
            for faction, count in faction_counts.items():
                effective = count
                if (
                    excluded is not None
                    and cell == (excluded.col, excluded.row)
                    and faction == excluded.faction
                ):
                    effective -= 1
                if effective <= 0:
                    continue
                has_any = True
                if faction != mover_faction:
                    has_enemy = True
            if has_any:
                occupied.add(cell)
            if has_enemy:
                enemy_held.add(cell)

        return occupied, enemy_held

    def occupancy_for_mover_local(
        self,
        mover: Optional[int],
        mover_faction: Optional[Faction],
        center: Hex,
        hex_radius: int,
    ) -> tuple[Set[Hex], Set[Hex]]:
        """Movement occupancy restricted to the only cells a budget can reach.

        With a minimum terrain enter-cost of one, a route costing at most ``R``
        can never depend on occupancy farther than hex distance ``R`` from its
        start.  Effect overlays use this bounded view so their recomputation is
        O(R^2), not O(total units).
        """
        radius = max(0, int(hex_radius))
        excluded = self.by_entity.get(mover) if mover is not None else None
        occupied: Set[Hex] = set()
        enemy_held: Set[Hex] = set()

        for cell in HexMath.hex_in_range(center[0], center[1], radius):
            faction_counts = self.by_cell.get(cell)
            if not faction_counts:
                continue
            has_any = False
            has_enemy = False
            for faction, count in faction_counts.items():
                effective = count
                if (
                    excluded is not None
                    and cell == (excluded.col, excluded.row)
                    and faction == excluded.faction
                ):
                    effective -= 1
                if effective <= 0:
                    continue
                has_any = True
                if faction != mover_faction:
                    has_enemy = True
            if has_any:
                occupied.add(cell)
            if has_enemy:
                enemy_held.add(cell)
        return occupied, enemy_held

    def local_revision_signature(self, center: Hex, hex_radius: int) -> tuple:
        """Revision signature for buckets intersecting a local hex-radius.

        This is deliberately conservative: movement anywhere in one of the
        buckets touched by the radius invalidates the local cache, even if that
        changed unit is just outside the exact reachable cells. Movement in
        unrelated buckets does not invalidate the local cache.
        """
        radius = max(0, int(hex_radius))
        buckets = {
            self._bucket_for_hex(col, row)
            for col, row in HexMath.hex_in_range(center[0], center[1], radius)
        }
        return tuple(
            (bx, by, self.bucket_revisions.get((bx, by), 0))
            for bx, by in sorted(buckets)
        )

    def cells_snapshot(
        self, *, exclude_entity: Optional[int] = None
    ) -> Dict[Hex, Set[Faction]]:
        """Compatibility view for callers that still need Hex -> factions."""
        excluded = self.by_entity.get(exclude_entity) if exclude_entity is not None else None
        result: Dict[Hex, Set[Faction]] = {}
        for cell, faction_counts in self.by_cell.items():
            factions: Set[Faction] = set()
            for faction, count in faction_counts.items():
                effective = count
                if (
                    excluded is not None
                    and cell == (excluded.col, excluded.row)
                    and faction == excluded.faction
                ):
                    effective -= 1
                if effective > 0:
                    factions.add(faction)
            if factions:
                result[cell] = factions
        return result

    def _bucket_bounds_for_world_rect(
        self, left: float, right: float, top: float, bottom: float
    ) -> tuple[int, int, int, int]:
        if left > right:
            left, right = right, left
        if top > bottom:
            top, bottom = bottom, top
        return (
            floor(left / self.bucket_size),
            floor(right / self.bucket_size),
            floor(top / self.bucket_size),
            floor(bottom / self.bucket_size),
        )

    def nonempty_buckets_in_world_rect(
        self, left: float, right: float, top: float, bottom: float
    ) -> Iterable[tuple[Bucket, Set[int]]]:
        """Yield non-empty coarse buckets intersecting a world-pixel rect.

        Callers may inspect the returned sets during their synchronous read
        phase, but must not mutate them.  The world update loop is single-threaded,
        so an index update cannot race a renderer iteration.
        """
        min_bx, max_bx, min_by, max_by = self._bucket_bounds_for_world_rect(
            left, right, top, bottom
        )
        for bx in range(min_bx, max_bx + 1):
            for by in range(min_by, max_by + 1):
                bucket_key = (bx, by)
                bucket = self.by_bucket.get(bucket_key)
                if bucket:
                    yield bucket_key, bucket

    def candidates_in_world_rect(
        self, left: float, right: float, top: float, bottom: float
    ) -> Iterable[int]:
        """Yield entities from coarse buckets intersecting a world-pixel rect."""
        for _, bucket in self.nonempty_buckets_in_world_rect(
            left, right, top, bottom
        ):
            yield from bucket


def get_unit_spatial_index(world) -> Optional[UnitSpatialIndex]:
    return getattr(world, _INDEX_ATTR, None)


def rebuild_unit_spatial_index(world) -> UnitSpatialIndex:
    index = get_unit_spatial_index(world)
    if index is None:
        index = UnitSpatialIndex()
        setattr(world, _INDEX_ATTR, index)
    index.rebuild(world)
    return index


def update_unit_spatial_index(world, entity: int) -> bool:
    index = get_unit_spatial_index(world)
    return bool(index and index.upsert_from_world(world, entity))


def remove_unit_from_spatial_index(world, entity: int) -> bool:
    index = get_unit_spatial_index(world)
    return bool(index and index.remove(entity))
