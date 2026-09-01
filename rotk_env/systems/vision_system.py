"""
Vision system - incremental fog-of-war visibility with event-driven dirty work.

The old implementation cached each unit's ray-cast result, but still scanned every
Vision unit and rebuilt faction unions every frame. At large world scale that made
static cost proportional to resident units and synchronized movement produced
large O(N) visibility bursts.

This implementation separates four concerns:
- invalidation: movement/terrain changes enqueue only affected units;
- geometry: (center, effective_range, terrain_revision) visibility is cached;
- aggregation: per-faction tile reference counts incrementally maintain the union;
- presentation delta: faction-level visibility transitions are published to a
  revisioned journal without coupling renderers to VisionSystem internals.

Normal FogOfWar semantics are unchanged. ``FogOfWar.enabled`` remains only a
consumer-side switch; visibility/exploration continue to be maintained while fog
is disabled so re-enabling it is immediate.
"""

from __future__ import annotations

from typing import Dict, FrozenSet, Optional, Set, Tuple

from framework import System, World
from framework.ecs import profiling
from framework.engine.events import EBS

from ..components import HexPosition, Vision, Unit, FogOfWar, MapData, Terrain
from ..prefabs.config import Faction
from ..utils.fog_visibility_journal import publish_fog_visibility_delta
from ..utils.hex_utils import HexMath
from ..utils.env_events import UnitDeathEvent
from ..utils.unit_spatial_index import get_unit_spatial_index

Hex = Tuple[int, int]

_DIRTY_ATTR = "_vision_dirty_entities"


def _dirty_set(world: World) -> Set[int]:
    dirty = getattr(world, _DIRTY_ATTR, None)
    if dirty is None:
        dirty = set()
        setattr(world, _DIRTY_ATTR, dirty)
    return dirty


def mark_vision_dirty(world: World, entity: int) -> None:
    """Enqueue one entity after an authoritative vision input changes.

    This helper is intentionally tiny so movement can publish an invalidation
    without depending on VisionSystem internals. Calling it before VisionSystem
    is mounted is safe: the set lives on the World and will be drained later.
    """
    _dirty_set(world).add(entity)


class VisionSystem(System):
    """Incremental visibility geometry and faction-union maintenance."""

    # A low-rate audit protects semantics for rare direct component writes that
    # bypass the explicit invalidation helper (for example future debug tooling).
    # It is not part of steady per-frame work and is profiled independently.
    _AUDIT_EVERY_FRAMES = 60

    def __init__(self):
        super().__init__(required_components={HexPosition, Vision, Unit})
        self._dirty: Set[int] = set()
        self._unit_visibility: Dict[int, FrozenSet[Hex]] = {}
        self._unit_faction: Dict[int, Faction] = {}
        self._faction_tile_counts: Dict[Faction, Dict[Hex, int]] = {}
        self._geometry_cache: Dict[Tuple[Hex, int, int], FrozenSet[Hex]] = {}
        self._terrain_revision = 0
        self._frames = 0
        self._bootstrapped = False
        self._last_fog_enabled: Optional[bool] = None
        self._frame_fog_delta: Dict[Faction, Set[Hex]] = {}

        # Cumulative diagnostics retained for compatibility with get_stats().
        self._stat_recomputes = 0
        self._stat_cache_hits = 0
        self._stat_geometry_hits = 0
        self._stat_geometry_misses = 0

    def initialize(self, world: World) -> None:
        self.world = world
        self._dirty = _dirty_set(world)

    def subscribe_events(self):
        EBS.subscribe(UnitDeathEvent, self._handle_unit_death)

    def cleanup(self) -> None:
        EBS.unsubscribe(UnitDeathEvent, self._handle_unit_death)

    def _handle_unit_death(self, event: UnitDeathEvent) -> None:
        # Combat publishes before destroy_entity(), so defer ref-count cleanup to
        # the next Vision tick when the entity has actually disappeared.
        self._dirty.add(event.entity)

    def update(self, delta_time: float) -> None:
        self._frames += 1
        self._frame_fog_delta = {}
        fog = self._ensure_fog()
        fog_toggled = (
            self._last_fog_enabled is not None
            and self._last_fog_enabled != bool(fog.enabled)
        )
        self._last_fog_enabled = bool(fog.enabled)
        profiling.profiler.set_frame_metric("fog_enabled", int(bool(fog.enabled)))
        profiling.profiler.set_frame_metric(
            "fog_toggle_this_frame", int(fog_toggled)
        )

        audit_scanned = 0
        if not self._bootstrapped:
            audit_scanned = self._audit_all_units(force_all=True)
            self._bootstrapped = True
        else:
            # Indexed scale worlds publish position invalidations explicitly and
            # need only a low-rate safety audit. Legacy/base worlds keep the old
            # immediate semantics by auditing every tick.
            audit_interval = (
                self._AUDIT_EVERY_FRAMES
                if get_unit_spatial_index(self.world) is not None
                else 1
            )
            if self._frames % audit_interval == 0:
                with profiling.profiler.time_system(
                    "vision_audit_scan", category="vision"
                ):
                    audit_scanned = self._audit_all_units(force_all=False)

        dirty = tuple(self._dirty)
        self._dirty.clear()

        changed = 0
        tile_updates = 0
        unit_tiles_added = 0
        unit_tiles_removed = 0
        faction_tiles_added = 0
        faction_tiles_removed = 0
        geometry_hits_before = self._stat_geometry_hits
        geometry_misses_before = self._stat_geometry_misses

        for entity in dirty:
            position = self.world.get_component(entity, HexPosition)
            vision = self.world.get_component(entity, Vision)
            unit = self.world.get_component(entity, Unit)

            if position is None or vision is None or unit is None:
                removed = self._remove_unit_contribution(entity, fog)
                faction_tiles_removed += removed
                continue

            current_pos = (position.col, position.row)
            current_range = int(vision.range)
            current_faction = unit.faction

            unchanged = (
                not vision.dirty
                and vision._last_observed_pos == current_pos
                and vision._last_range == current_range
                and entity in self._unit_visibility
                and self._unit_faction.get(entity) == current_faction
            )
            if unchanged:
                self._stat_cache_hits += 1
                continue

            visible_tiles = self._visibility_for(current_pos, current_range)
            tile_updates += len(visible_tiles)
            old_tiles = self._unit_visibility.get(entity, frozenset())
            old_faction = self._unit_faction.get(entity)

            if old_faction is not None and old_faction != current_faction:
                removed, union_removed = self._remove_tiles(
                    fog, old_faction, old_tiles
                )
                unit_tiles_removed += removed
                faction_tiles_removed += union_removed
                old_tiles = frozenset()

            removed_tiles = old_tiles.difference(visible_tiles)
            added_tiles = visible_tiles.difference(old_tiles)

            if removed_tiles:
                removed, union_removed = self._remove_tiles(
                    fog, current_faction, removed_tiles
                )
                unit_tiles_removed += removed
                faction_tiles_removed += union_removed

            if added_tiles:
                added, union_added = self._add_tiles(
                    fog, current_faction, added_tiles
                )
                unit_tiles_added += added
                faction_tiles_added += union_added

            self._unit_visibility[entity] = visible_tiles
            self._unit_faction[entity] = current_faction
            vision.visible_tiles = set(visible_tiles)
            vision._last_observed_pos = current_pos
            vision._last_range = current_range
            vision.dirty = False

            explored = fog.explored_tiles.setdefault(current_faction, set())
            explored.update(visible_tiles)

            self._stat_recomputes += 1
            changed += 1

        fog_delta_tiles = sum(len(tiles) for tiles in self._frame_fog_delta.values())
        fog_journal_revision = publish_fog_visibility_delta(
            self.world, self._frame_fog_delta
        )
        self._publish_metrics(
            dirty_seen=len(dirty),
            changed=changed,
            tile_updates=tile_updates,
            unit_tiles_added=unit_tiles_added,
            unit_tiles_removed=unit_tiles_removed,
            faction_tiles_added=faction_tiles_added,
            faction_tiles_removed=faction_tiles_removed,
            audit_scanned=audit_scanned,
            geometry_hits=self._stat_geometry_hits - geometry_hits_before,
            geometry_misses=self._stat_geometry_misses - geometry_misses_before,
            fog_delta_tiles=fog_delta_tiles,
            fog_journal_revision=fog_journal_revision,
        )

    def invalidate_all(self) -> None:
        """Invalidate all visibility after LOS-affecting terrain changes.

        Terrain invalidation also bumps the geometry-cache revision. The actual
        recompute stays on the normal VisionSystem tick so callers never mutate
        the faction union out-of-band.
        """
        self._terrain_revision += 1
        self._geometry_cache.clear()
        for entity in self.world.query().with_component(Vision).entities():
            vision = self.world.get_component(entity, Vision)
            if vision is not None:
                vision.dirty = True
            self._dirty.add(entity)

    def get_stats(self) -> dict:
        total = self._stat_recomputes + self._stat_cache_hits
        geometry_total = self._stat_geometry_hits + self._stat_geometry_misses
        return {
            "recomputes": self._stat_recomputes,
            "cache_hits": self._stat_cache_hits,
            "hit_rate": (self._stat_cache_hits / total) if total else 0.0,
            "geometry_cache_hits": self._stat_geometry_hits,
            "geometry_cache_misses": self._stat_geometry_misses,
            "geometry_hit_rate": (
                self._stat_geometry_hits / geometry_total if geometry_total else 0.0
            ),
            "geometry_cache_size": len(self._geometry_cache),
        }

    # ------------------------------------------------------------------
    # Dirty discovery / lifecycle reconciliation
    # ------------------------------------------------------------------
    def _audit_all_units(self, *, force_all: bool) -> int:
        """Reconcile membership and catch direct component writes.

        Normal scale movement is event-driven through ``mark_vision_dirty``. This
        audit is a semantic safety net: low-rate in indexed scale worlds and
        every tick in legacy/base worlds that may mutate HexPosition directly.
        """
        current_entities: Set[int] = set()
        for entity in self.world.query().with_all(HexPosition, Vision, Unit).entities():
            current_entities.add(entity)
            position = self.world.get_component(entity, HexPosition)
            vision = self.world.get_component(entity, Vision)
            unit = self.world.get_component(entity, Unit)
            if position is None or vision is None or unit is None:
                continue
            current_pos = (position.col, position.row)
            changed = (
                force_all
                or entity not in self._unit_visibility
                or vision.dirty
                or vision._last_observed_pos != current_pos
                or vision._last_range != vision.range
                or self._unit_faction.get(entity) != unit.faction
            )
            if changed:
                self._dirty.add(entity)

        stale = set(self._unit_visibility).difference(current_entities)
        self._dirty.update(stale)
        return len(current_entities)

    def _remove_unit_contribution(self, entity: int, fog: FogOfWar) -> int:
        old_tiles = self._unit_visibility.pop(entity, frozenset())
        old_faction = self._unit_faction.pop(entity, None)
        if old_faction is None or not old_tiles:
            return 0
        _removed, union_removed = self._remove_tiles(fog, old_faction, old_tiles)
        return union_removed

    # ------------------------------------------------------------------
    # Incremental faction union + presentation delta
    # ------------------------------------------------------------------
    def _counts_for(self, faction: Faction) -> Dict[Hex, int]:
        counts = self._faction_tile_counts.get(faction)
        if counts is None:
            counts = {}
            self._faction_tile_counts[faction] = counts
        return counts

    def _record_fog_delta(self, faction: Faction, tile: Hex) -> None:
        self._frame_fog_delta.setdefault(faction, set()).add(tile)

    def _add_tiles(
        self, fog: FogOfWar, faction: Faction, tiles
    ) -> Tuple[int, int]:
        counts = self._counts_for(faction)
        visible = fog.faction_vision.setdefault(faction, set())
        union_added = 0
        added = 0
        for tile in tiles:
            old = counts.get(tile, 0)
            counts[tile] = old + 1
            if old == 0:
                visible.add(tile)
                self._record_fog_delta(faction, tile)
                union_added += 1
            added += 1
        return added, union_added

    def _remove_tiles(
        self, fog: FogOfWar, faction: Faction, tiles
    ) -> Tuple[int, int]:
        counts = self._counts_for(faction)
        visible = fog.faction_vision.setdefault(faction, set())
        union_removed = 0
        removed = 0
        for tile in tiles:
            old = counts.get(tile, 0)
            if old <= 1:
                if old:
                    counts.pop(tile, None)
                    visible.discard(tile)
                    self._record_fog_delta(faction, tile)
                    union_removed += 1
            else:
                counts[tile] = old - 1
            removed += 1
        return removed, union_removed

    # ------------------------------------------------------------------
    # Geometry cache
    # ------------------------------------------------------------------
    def _visibility_for(self, center: Hex, range_val: int) -> FrozenSet[Hex]:
        terrain_bonus = self._get_vision_terrain_bonus(center)
        effective_range = int(range_val) + terrain_bonus
        key = (center, effective_range, self._terrain_revision)
        cached = self._geometry_cache.get(key)
        if cached is not None:
            self._stat_geometry_hits += 1
            return cached

        visible = frozenset(
            self._calculate_vision_effective(center, effective_range)
        )
        self._geometry_cache[key] = visible
        self._stat_geometry_misses += 1
        return visible

    def _calculate_vision(
        self, center: Hex, range_val: int, observer_entity: int
    ) -> Set[Hex]:
        """Compatibility helper: calculate visibility using the geometry cache."""
        return set(self._visibility_for(center, range_val))

    def _calculate_vision_effective(
        self, center: Hex, effective_range: int
    ) -> Set[Hex]:
        visible: Set[Hex] = set()
        q, r = center
        for target_q in range(q - effective_range, q + effective_range + 1):
            for target_r in range(r - effective_range, r + effective_range + 1):
                target_pos = (target_q, target_r)
                if HexMath.hex_distance(center, target_pos) <= effective_range:
                    if self._has_line_of_sight(center, target_pos):
                        visible.add(target_pos)
        return visible

    def _has_line_of_sight(self, start: Hex, end: Hex) -> bool:
        line = HexMath.line_of_sight(start, end)
        map_data = self.world.get_singleton_component(MapData)
        if not map_data:
            return True

        from ..components.terrain import effect_for

        for pos in line[1:-1]:
            tile_entity = map_data.tiles.get(pos)
            if tile_entity:
                terrain = self.world.get_component(tile_entity, Terrain)
                if terrain and effect_for(terrain.terrain_type).blocks_line_of_sight:
                    return False
        return True

    def _get_vision_terrain_bonus(self, position: Hex) -> int:
        map_data = self.world.get_singleton_component(MapData)
        if not map_data:
            return 0

        tile_entity = map_data.tiles.get(position)
        if not tile_entity:
            return 0

        from ..components.terrain import effect_for

        terrain = self.world.get_component(tile_entity, Terrain)
        if not terrain:
            return 0
        return int(effect_for(terrain.terrain_type).vision_bonus)

    # ------------------------------------------------------------------
    # Profiler
    # ------------------------------------------------------------------
    def _publish_metrics(
        self,
        *,
        dirty_seen: int,
        changed: int,
        tile_updates: int,
        unit_tiles_added: int,
        unit_tiles_removed: int,
        faction_tiles_added: int,
        faction_tiles_removed: int,
        audit_scanned: int,
        geometry_hits: int,
        geometry_misses: int,
        fog_delta_tiles: int,
        fog_journal_revision: int,
    ) -> None:
        metric = profiling.profiler.set_frame_metric
        metric("vision_mode", "dirty_refcount")
        metric("vision_dirty_units", dirty_seen)
        metric("vision_units_changed", changed)
        metric("vision_units_scanned", changed)
        metric("vision_tile_updates", tile_updates)
        metric("vision_unit_tiles_added", unit_tiles_added)
        metric("vision_unit_tiles_removed", unit_tiles_removed)
        metric("vision_faction_tiles_added", faction_tiles_added)
        metric("vision_faction_tiles_removed", faction_tiles_removed)
        metric("vision_geometry_cache_hits", geometry_hits)
        metric("vision_geometry_cache_misses", geometry_misses)
        metric("vision_geometry_cache_size", len(self._geometry_cache))
        metric("vision_audit_scanned", audit_scanned)
        metric("vision_fog_delta_tiles", fog_delta_tiles)
        metric("vision_fog_journal_revision", fog_journal_revision)

    def _ensure_fog(self) -> FogOfWar:
        fog = self.world.get_singleton_component(FogOfWar)
        if fog is None:
            fog = FogOfWar()
            self.world.add_singleton_component(fog)
        return fog
