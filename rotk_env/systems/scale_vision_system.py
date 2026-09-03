"""Window compatibility adapter for the shared incremental VisionSystem.

Large-window mode used to carry a second fog/vision implementation here. That
made scale and canonical semantics diverge (notably fog-off maintenance and
re-enable rebuilds) and left two different O(N) invalidation paths to optimize.

The shared :mod:`vision_system` now owns the scalable algorithm itself:
- dirty-unit work queue;
- incremental faction tile reference counts;
- geometry cache keyed by center/range/terrain revision;
- low-rate audit when UnitSpatialIndex is available.

Window mode therefore needs no second algorithm. ScaleMovementSystem publishes
hex-commit invalidations and the maintained UnitSpatialIndex lets the shared
VisionSystem use the low-rate safety audit automatically.

Window mode uses a bounded capacity with headroom for large maps. The cache does
not preallocate entries, while headless mode keeps the shared system's smaller
default.
"""

from __future__ import annotations

from .vision_system import VisionSystem as _BaseVisionSystem

_DEFAULT_SCALE_GEOMETRY_CACHE_MAX_ENTRIES = 16384


class VisionSystem(_BaseVisionSystem):
    """Compatibility name used by WorldBuilder for display='window'."""

    def __init__(self):
        super().__init__(geometry_cache_max_entries=_DEFAULT_SCALE_GEOMETRY_CACHE_MAX_ENTRIES)
