#!/usr/bin/env python3
"""Measurement-only attribution for Phase-5 C2 Vision union/refcount work.

This launcher preserves the current production Vision update/geometry paths and
replaces only `_add_tiles()` / `_remove_tiles()` in-process with semantically
identical attribution implementations. It decomposes faction-union maintenance
into:

- per-faction container lookup/setup;
- refcount dict lookup;
- refcount dict mutation;
- faction-visible set mutation on 0<->1 transitions;
- fog-delta journal staging on those same transitions.

Per-tile micro timings are sampled to keep probe overhead bounded. Exact call,
tile, and transition counts are still published every frame. Aggregate frame
latency from this probe is diagnostic only; use the normal Phase-5 Core runner
for any production acceptance A/B.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, Optional

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from framework.ecs import profiling as ecs_profiling


EXPECTED_BLOBS = {
    # Current production baseline: Optimization A + retained C1.
    "rotk_env/systems/animation_system.py": "a0fea5453419cbb409287c72d5156208d280219f",
    "rotk_env/systems/vision_system.py": "6e9190ceb209e257e8f3f10bebe6eb571b8415b4",
    "rotk_env/systems/window_vision_system.py": "b54c523be1288467815961038c3ee18e7333ef4a",
    "rotk_env/systems/window_movement_system.py": "9dce77603b42c588357fffa0438246f7f6e62117",
    "rotk_env/utils/unit_spatial_index.py": "768200c3f5d6fc763c6bcf01c4f9711b4979e11a",
}

_SAMPLE_EVERY_ENV = "STAR_PHASE5_VISION_UNION_SAMPLE_EVERY"
_DEFAULT_SAMPLE_EVERY = 64


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
class _FrameAttribution:
    sample_every: int
    counters: Dict[str, int] = field(default_factory=dict)
    samples: Dict[str, _SampleAccumulator] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "add_container",
            "add_count_lookup",
            "add_count_mutation",
            "add_visible_mutation",
            "add_fog_delta",
            "remove_container",
            "remove_count_lookup",
            "remove_count_mutation",
            "remove_visible_mutation",
            "remove_fog_delta",
        ):
            self.samples[name] = _SampleAccumulator(self.sample_every)

    def inc(self, key: str, amount: int = 1) -> None:
        self.counters[key] = self.counters.get(key, 0) + amount


_ACTIVE_FRAME: Optional[_FrameAttribution] = None


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
        if not (_REPO_ROOT / path).is_file():
            drift.append(f"{path}: missing")
            continue
        actual = _git_blob(path)
        if actual != expected:
            drift.append(f"{path}: expected {expected}, got {actual}")

    if drift:
        details = "\n".join(f"  - {item}" for item in drift)
        raise RuntimeError(
            "Phase-5 C2 Vision union attribution source guard failed. "
            "These probes are valid only for the retained C1 production tree:\n"
            f"{details}\n"
            "Do not override this guard; review and update the probe instead."
        )


def _publish_sample(prefix: str, acc: _SampleAccumulator) -> None:
    metric = ecs_profiling.profiler.set_frame_metric
    metric(f"{prefix}_calls", acc.calls)
    metric(f"{prefix}_sampled_calls", acc.sampled_calls)
    metric(f"{prefix}_sample_avg_us", acc.sample_avg_us)
    metric(f"{prefix}_estimated_ms", acc.estimated_ms)


def _install_union_probe(sample_every: int) -> None:
    from rotk_env.systems import vision_system as vision_mod
    from rotk_env.systems import window_vision_system as window_vision_mod

    original_update = window_vision_mod.VisionSystem.update

    def attributed_add_tiles(self, fog, faction, tiles):
        frame = _ACTIVE_FRAME
        if frame is None:
            return vision_mod.VisionSystem._phase5_c2_original_add_tiles(
                self, fog, faction, tiles
            )

        frame.inc("add_calls")

        container = frame.samples["add_container"]
        if container.should_sample():
            started = time.perf_counter_ns()
            counts = self._counts_for(faction)
            visible = fog.faction_vision.setdefault(faction, set())
            container.add_sample(started)
        else:
            counts = self._counts_for(faction)
            visible = fog.faction_vision.setdefault(faction, set())

        union_added = 0
        added = 0
        for tile in tiles:
            frame.inc("add_tiles")

            lookup = frame.samples["add_count_lookup"]
            if lookup.should_sample():
                started = time.perf_counter_ns()
                old = counts.get(tile, 0)
                lookup.add_sample(started)
            else:
                old = counts.get(tile, 0)

            mutation = frame.samples["add_count_mutation"]
            if mutation.should_sample():
                started = time.perf_counter_ns()
                counts[tile] = old + 1
                mutation.add_sample(started)
            else:
                counts[tile] = old + 1

            if old == 0:
                frame.inc("add_union_transitions")

                visible_mutation = frame.samples["add_visible_mutation"]
                if visible_mutation.should_sample():
                    started = time.perf_counter_ns()
                    visible.add(tile)
                    visible_mutation.add_sample(started)
                else:
                    visible.add(tile)

                fog_delta = frame.samples["add_fog_delta"]
                if fog_delta.should_sample():
                    started = time.perf_counter_ns()
                    self._record_fog_delta(faction, tile)
                    fog_delta.add_sample(started)
                else:
                    self._record_fog_delta(faction, tile)

                union_added += 1
            else:
                frame.inc("add_shared_refcount_updates")

            added += 1

        return added, union_added

    def attributed_remove_tiles(self, fog, faction, tiles):
        frame = _ACTIVE_FRAME
        if frame is None:
            return vision_mod.VisionSystem._phase5_c2_original_remove_tiles(
                self, fog, faction, tiles
            )

        frame.inc("remove_calls")

        container = frame.samples["remove_container"]
        if container.should_sample():
            started = time.perf_counter_ns()
            counts = self._counts_for(faction)
            visible = fog.faction_vision.setdefault(faction, set())
            container.add_sample(started)
        else:
            counts = self._counts_for(faction)
            visible = fog.faction_vision.setdefault(faction, set())

        union_removed = 0
        removed = 0
        for tile in tiles:
            frame.inc("remove_tiles")

            lookup = frame.samples["remove_count_lookup"]
            if lookup.should_sample():
                started = time.perf_counter_ns()
                old = counts.get(tile, 0)
                lookup.add_sample(started)
            else:
                old = counts.get(tile, 0)

            if old <= 1:
                if old:
                    frame.inc("remove_union_transitions")

                    mutation = frame.samples["remove_count_mutation"]
                    if mutation.should_sample():
                        started = time.perf_counter_ns()
                        counts.pop(tile, None)
                        mutation.add_sample(started)
                    else:
                        counts.pop(tile, None)

                    visible_mutation = frame.samples["remove_visible_mutation"]
                    if visible_mutation.should_sample():
                        started = time.perf_counter_ns()
                        visible.discard(tile)
                        visible_mutation.add_sample(started)
                    else:
                        visible.discard(tile)

                    fog_delta = frame.samples["remove_fog_delta"]
                    if fog_delta.should_sample():
                        started = time.perf_counter_ns()
                        self._record_fog_delta(faction, tile)
                        fog_delta.add_sample(started)
                    else:
                        self._record_fog_delta(faction, tile)

                    union_removed += 1
                else:
                    frame.inc("remove_missing_refcounts")
            else:
                frame.inc("remove_shared_refcount_updates")

                mutation = frame.samples["remove_count_mutation"]
                if mutation.should_sample():
                    started = time.perf_counter_ns()
                    counts[tile] = old - 1
                    mutation.add_sample(started)
                else:
                    counts[tile] = old - 1

            removed += 1

        return removed, union_removed

    # Preserve originals for defensive calls outside the active measured update.
    vision_mod.VisionSystem._phase5_c2_original_add_tiles = vision_mod.VisionSystem._add_tiles
    vision_mod.VisionSystem._phase5_c2_original_remove_tiles = vision_mod.VisionSystem._remove_tiles
    vision_mod.VisionSystem._add_tiles = attributed_add_tiles
    vision_mod.VisionSystem._remove_tiles = attributed_remove_tiles

    def attributed_update(self, delta_time: float):
        global _ACTIVE_FRAME

        frame = _FrameAttribution(sample_every)
        _ACTIVE_FRAME = frame
        try:
            return original_update(self, delta_time)
        finally:
            _ACTIVE_FRAME = None
            metric = ecs_profiling.profiler.set_frame_metric

            for name in (
                "add_calls",
                "add_tiles",
                "add_union_transitions",
                "add_shared_refcount_updates",
                "remove_calls",
                "remove_tiles",
                "remove_union_transitions",
                "remove_shared_refcount_updates",
                "remove_missing_refcounts",
            ):
                metric(f"phase5_c2_{name}", frame.counters.get(name, 0))

            for name, acc in frame.samples.items():
                _publish_sample(f"phase5_c2_{name}", acc)

            add_tiles = frame.counters.get("add_tiles", 0)
            remove_tiles = frame.counters.get("remove_tiles", 0)
            add_transitions = frame.counters.get("add_union_transitions", 0)
            remove_transitions = frame.counters.get("remove_union_transitions", 0)
            total_tiles = add_tiles + remove_tiles
            total_transitions = add_transitions + remove_transitions
            metric("phase5_c2_total_refcount_tile_ops", total_tiles)
            metric("phase5_c2_total_union_transitions", total_transitions)
            metric(
                "phase5_c2_union_transition_rate",
                (total_transitions / total_tiles) if total_tiles else 0.0,
            )

    window_vision_mod.VisionSystem.update = attributed_update


def _install_probes() -> None:
    sample_every = _sample_every()
    _verify_source_contract()

    # Install STAR's concrete profiler before mounting process-local probes.
    import rotk_env.main as env_main

    _install_union_probe(sample_every)

    ecs_profiling.profiler.set_metadata(
        phase5_vision_union_attribution=True,
        phase5_vision_union_sample_every=sample_every,
        phase5_vision_union_source_guard=EXPECTED_BLOBS,
        phase5_vision_union_scope="faction_union_refcount_only",
    )

    env_main.main()


def main() -> int:
    _install_probes()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
