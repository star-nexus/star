"""Window configuration for the shared incremental VisionSystem.

The shared :mod:`vision_system` owns the visibility algorithm:
- dirty-unit work queue;
- incremental faction tile reference counts;
- geometry cache keyed by center/range/terrain revision;
- defensive audit semantics for bootstrap and non-indexed worlds.

WindowMovementSystem publishes committed-position invalidations, and the maintained
UnitSpatialIndex is the production contract for incremental window worlds. The
window specialization therefore skips the periodic O(Nresident) reconciliation
scan once that index is installed, while preserving force-all bootstrap and the
shared non-indexed direct-write safety path.

Window mode also uses a bounded geometry-cache capacity with headroom for large
interactive maps. The cache does not preallocate entries, while headless mode
keeps the shared system's smaller default.
"""

from __future__ import annotations

from typing import FrozenSet

from ..utils.unit_spatial_index import get_unit_spatial_index
from .vision_system import Hex, VisionSystem as _BaseVisionSystem

_DEFAULT_WINDOW_GEOMETRY_CACHE_MAX_ENTRIES = 16384


class VisionSystem(_BaseVisionSystem):
    """Window VisionSystem configured for incremental indexed runtime work."""

    def __init__(self):
        super().__init__(
            geometry_cache_max_entries=_DEFAULT_WINDOW_GEOMETRY_CACHE_MAX_ENTRIES
        )

    def _audit_all_units(self, *, force_all: bool) -> int:
        """Keep bootstrap/non-indexed safety without periodic indexed scans.

        The window runtime maintains a UnitSpatialIndex and publishes explicit
        Vision invalidations for authoritative movement/lifecycle transitions.
        Attribution at 10K scale found no audit-only semantic discoveries across
        the canonical indexed workload, while each periodic scan cost about 4ms.

        ``force_all`` remains the bootstrap reconciliation contract. Worlds that
        do not have a spatial index retain the shared direct-component-write
        safety behavior. Only the periodic indexed-window reconciliation becomes
        an O(1) no-op.
        """
        if force_all or get_unit_spatial_index(self.world) is None:
            return super()._audit_all_units(force_all=force_all)
        return 0

    def _visibility_for(self, center: Hex, range_val: int) -> FrozenSet[Hex]:
        """Return cached geometry before consulting terrain on the hit path.

        For one terrain revision, the terrain-derived vision bonus is a stable
        function of ``center``. Keying the window cache by the observer's base
        range therefore lets the overwhelmingly common cache-hit path avoid the
        MapData -> Terrain -> effect lookup entirely. ``invalidate_all()`` bumps
        ``_terrain_revision`` and clears the cache after terrain changes, so a
        miss in the new revision re-reads the bonus before rebuilding geometry.
        """
        base_range = int(range_val)
        key = (center, base_range, self._terrain_revision)
        cached = self._geometry_cache.get(key)
        if cached is not None:
            self._geometry_cache.move_to_end(key)
            self._stat_geometry_hits += 1
            return cached

        terrain_bonus = self._get_vision_terrain_bonus(center)
        effective_range = base_range + terrain_bonus
        visible = frozenset(
            self._calculate_vision_effective(center, effective_range)
        )
        self._geometry_cache[key] = visible
        if len(self._geometry_cache) > self._geometry_cache_max_entries:
            self._geometry_cache.popitem(last=False)
            self._stat_geometry_evictions += 1
        self._stat_geometry_misses += 1
        return visible
