"""Window configuration for the shared incremental VisionSystem.

The shared :mod:`vision_system` owns the visibility algorithm:
- dirty-unit work queue;
- incremental faction tile reference counts;
- geometry cache keyed by center/range/terrain revision;
- low-rate audit when UnitSpatialIndex is available.

WindowMovementSystem publishes hex-commit invalidations, and the maintained
UnitSpatialIndex lets the shared VisionSystem use its low-rate safety audit.

Window mode uses a bounded capacity with headroom for large maps. The cache does
not preallocate entries, while headless mode keeps the shared system's smaller
default.
"""

from __future__ import annotations

from typing import FrozenSet

from .vision_system import Hex, VisionSystem as _BaseVisionSystem

_DEFAULT_WINDOW_GEOMETRY_CACHE_MAX_ENTRIES = 16384


class VisionSystem(_BaseVisionSystem):
    """Window VisionSystem with capacity for large interactive maps."""

    def __init__(self):
        super().__init__(
            geometry_cache_max_entries=_DEFAULT_WINDOW_GEOMETRY_CACHE_MAX_ENTRIES
        )

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
