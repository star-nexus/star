#!/usr/bin/env python3
"""Measurement-only attribution for the Phase-5 Vision geometry cache-hit path.

This launcher leaves production runtime source untouched. It wraps only the
shared VisionSystem at process startup and decomposes `_visibility_for()` into
sampled timing buckets while preserving the current implementation exactly:

- terrain bonus lookup;
- geometry-cache dict lookup;
- LRU touch on cache hits;
- geometry calculation on misses.

Absolute frame time from this probe is not canonical because sampling has
measurement overhead. Use it only to rank the cache-hit sub-operations, then
return to the uninstrumented Phase-5 Core harness for production A/B.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Optional

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from framework.ecs import profiling as ecs_profiling


EXPECTED_BLOBS = {
    # Current best production state: Optimization A retained, B reverted.
    "rotk_env/systems/animation_system.py": "a0fea5453419cbb409287c72d5156208d280219f",
    "rotk_env/systems/vision_system.py": "6e9190ceb209e257e8f3f10bebe6eb571b8415b4",
    "rotk_env/systems/window_vision_system.py": "3df5cb1c0d5827928613600a7b58fc5163d33080",
    "rotk_env/systems/window_movement_system.py": "9dce77603b42c588357fffa0438246f7f6e62117",
    "rotk_env/utils/unit_spatial_index.py": "768200c3f5d6fc763c6bcf01c4f9711b4979e11a",
}

_SAMPLE_EVERY_ENV = "STAR_PHASE5_VISION_HIT_SAMPLE_EVERY"
_DEFAULT_SAMPLE_EVERY = 16


@dataclass
class _SampleAccumulator:
    every: int
    calls: int = 0
    sampled_calls: int = 0
    sampled_ns: int = 0

    def should_sample(self) -> bool:
        self.calls += 1
        return (self.calls - 1) % self.every == 0

    def add_sample(self, started_ns: int) -> None:
        self.sampled_calls += 1
        self.sampled_ns += max(0, time.perf_counter_ns() - started_ns)

    def call(self, fn: Callable, *args, **kwargs):
        if not self.should_sample():
            return fn(*args, **kwargs)
        started = time.perf_counter_ns()
        try:
            return fn(*args, **kwargs)
        finally:
            self.add_sample(started)

    @property
    def sample_avg_us(self) -> float:
        if not self.sampled_calls:
            return 0.0
        return self.sampled_ns / self.sampled_calls / 1_000.0

    @property
    def estimated_ms(self) -> float:
        if not self.sampled_calls:
            return 0.0
        mean_ns = self.sampled_ns / self.sampled_calls
        return mean_ns * self.calls / 1_000_000.0


@dataclass
class _FrameProbe:
    sample_every: int
    visibility_calls: int = 0
    hits: int = 0
    misses: int = 0

    def __post_init__(self) -> None:
        self.samples: Dict[str, _SampleAccumulator] = {
            "terrain_bonus": _SampleAccumulator(self.sample_every),
            "cache_get": _SampleAccumulator(self.sample_every),
            "lru_touch": _SampleAccumulator(self.sample_every),
            # Misses are rare in the formal 10K workload; measure each one.
            "miss_geometry": _SampleAccumulator(1),
        }


_ACTIVE: Optional[_FrameProbe] = None


def _sample_every() -> int:
    raw = os.environ.get(_SAMPLE_EVERY_ENV, str(_DEFAULT_SAMPLE_EVERY))
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{_SAMPLE_EVERY_ENV} must be an integer >= 1") from exc
    if value < 1:
        raise ValueError(f"{_SAMPLE_EVERY_ENV} must be >= 1")
    return value


def _git_blob(path: str) -> str:
    return subprocess.check_output(
        ["git", "hash-object", path],
        cwd=_REPO_ROOT,
        text=True,
        stderr=subprocess.STDOUT,
    ).strip()


def _verify_source_contract() -> None:
    drift = []
    for path, expected in EXPECTED_BLOBS.items():
        full = _REPO_ROOT / path
        if not full.is_file():
            drift.append(f"{path}: missing")
            continue
        actual = _git_blob(path)
        if actual != expected:
            drift.append(f"{path}: expected {expected}, got {actual}")
    if drift:
        details = "\n".join(f"  - {item}" for item in drift)
        raise RuntimeError(
            "Phase-5 Vision-hit attribution source guard failed. "
            "Do not override this guard; review and update the probe instead:\n"
            f"{details}"
        )


def _publish_sample(prefix: str, acc: _SampleAccumulator) -> None:
    metric = ecs_profiling.profiler.set_frame_metric
    metric(f"{prefix}_calls", acc.calls)
    metric(f"{prefix}_sampled_calls", acc.sampled_calls)
    metric(f"{prefix}_sample_avg_us", acc.sample_avg_us)
    metric(f"{prefix}_estimated_ms", acc.estimated_ms)


def _install_probe(sample_every: int) -> None:
    from rotk_env.systems import vision_system as vision_mod

    original_update = vision_mod.VisionSystem.update
    original_terrain_bonus = vision_mod.VisionSystem._get_vision_terrain_bonus

    def attributed_visibility_for(self, center, range_val):
        probe = _ACTIVE
        if probe is None:
            # Should only occur outside VisionSystem.update() compatibility calls.
            terrain_bonus = original_terrain_bonus(self, center)
            effective_range = int(range_val) + terrain_bonus
            key = (center, effective_range, self._terrain_revision)
            cached = self._geometry_cache.get(key)
            if cached is not None:
                self._geometry_cache.move_to_end(key)
                self._stat_geometry_hits += 1
                return cached
            visible = frozenset(
                self._calculate_vision_effective(center, effective_range)
            )
            self._geometry_cache[key] = visible
            if len(self._geometry_cache) > self._geometry_cache_max_entries:
                self._geometry_cache.popitem(last=False)
                self._stat_geometry_evictions += 1
            self._stat_geometry_misses += 1
            return visible

        probe.visibility_calls += 1
        terrain_bonus = probe.samples["terrain_bonus"].call(
            original_terrain_bonus, self, center
        )
        effective_range = int(range_val) + terrain_bonus
        key = (center, effective_range, self._terrain_revision)
        cached = probe.samples["cache_get"].call(self._geometry_cache.get, key)

        if cached is not None:
            probe.hits += 1
            probe.samples["lru_touch"].call(self._geometry_cache.move_to_end, key)
            self._stat_geometry_hits += 1
            return cached

        probe.misses += 1

        def calculate_miss():
            return frozenset(
                self._calculate_vision_effective(center, effective_range)
            )

        visible = probe.samples["miss_geometry"].call(calculate_miss)
        self._geometry_cache[key] = visible
        if len(self._geometry_cache) > self._geometry_cache_max_entries:
            self._geometry_cache.popitem(last=False)
            self._stat_geometry_evictions += 1
        self._stat_geometry_misses += 1
        return visible

    def attributed_update(self, delta_time: float) -> None:
        global _ACTIVE
        probe = _FrameProbe(sample_every)
        _ACTIVE = probe
        try:
            original_update(self, delta_time)
        finally:
            _ACTIVE = None

        metric = ecs_profiling.profiler.set_frame_metric
        metric("phase5_c1_visibility_calls", probe.visibility_calls)
        metric("phase5_c1_geometry_hits", probe.hits)
        metric("phase5_c1_geometry_misses", probe.misses)
        hit_rate = probe.hits / probe.visibility_calls if probe.visibility_calls else 0.0
        metric("phase5_c1_geometry_hit_rate", hit_rate)
        _publish_sample("phase5_c1_terrain_bonus", probe.samples["terrain_bonus"])
        _publish_sample("phase5_c1_cache_get", probe.samples["cache_get"])
        _publish_sample("phase5_c1_lru_touch", probe.samples["lru_touch"])
        _publish_sample("phase5_c1_miss_geometry", probe.samples["miss_geometry"])

    vision_mod.VisionSystem._visibility_for = attributed_visibility_for
    vision_mod.VisionSystem.update = attributed_update


def main() -> int:
    _verify_source_contract()
    sample_every = _sample_every()

    # Importing main installs STAR's concrete profiler hook before runtime starts.
    import rotk_env.main as env_main

    _install_probe(sample_every)
    ecs_profiling.profiler.set_metadata(
        phase5_vision_hit_attribution=True,
        phase5_vision_hit_sample_every=sample_every,
        phase5_vision_hit_source_guard=EXPECTED_BLOBS,
    )
    env_main.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
