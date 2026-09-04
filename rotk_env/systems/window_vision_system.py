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

from .vision_system import VisionSystem as _BaseVisionSystem

_DEFAULT_WINDOW_GEOMETRY_CACHE_MAX_ENTRIES = 16384


class VisionSystem(_BaseVisionSystem):
    """Window VisionSystem with capacity for large interactive maps."""

    def __init__(self):
        super().__init__(
            geometry_cache_max_entries=_DEFAULT_WINDOW_GEOMETRY_CACHE_MAX_ENTRIES
        )
