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

For scale experiments only, the bounded geometry-cache capacity can be selected
at fresh-process startup with ``STAR_SCALE_VISION_GEOMETRY_CACHE_MAX_ENTRIES``.
Keeping this in the window adapter leaves canonical/headless semantics and their
default constructor unchanged while allowing clean working-set ablations.
"""

from __future__ import annotations

import os

from .vision_system import (
    VisionSystem as _BaseVisionSystem,
    _DEFAULT_GEOMETRY_CACHE_MAX_ENTRIES,
)

_SCALE_VISION_CACHE_ENV = "STAR_SCALE_VISION_GEOMETRY_CACHE_MAX_ENTRIES"


def _geometry_cache_capacity_from_env() -> int:
    raw = os.environ.get(_SCALE_VISION_CACHE_ENV)
    if raw is None or not raw.strip():
        return _DEFAULT_GEOMETRY_CACHE_MAX_ENTRIES
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(
            f"{_SCALE_VISION_CACHE_ENV} must be a positive integer, got {raw!r}"
        ) from exc
    if value <= 0:
        raise ValueError(
            f"{_SCALE_VISION_CACHE_ENV} must be > 0, got {value}"
        )
    return value


class VisionSystem(_BaseVisionSystem):
    """Compatibility name used by WorldBuilder for display='window'."""

    def __init__(self):
        super().__init__(
            geometry_cache_max_entries=_geometry_cache_capacity_from_env()
        )
