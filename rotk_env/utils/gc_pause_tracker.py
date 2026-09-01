"""Low-overhead Python GC pause accounting for render-tail diagnostics."""

from __future__ import annotations

import gc
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Callable, Dict, Optional, Tuple


@dataclass(frozen=True)
class GCPauseSnapshot:
    collections: int
    pause_ns: int
    generation_collections: Tuple[int, int, int]
    generation_pause_ns: Tuple[int, int, int]
    phase_collections: Dict[str, int]
    phase_pause_ns: Dict[str, int]
    collected_objects: int
    uncollectable_objects: int
    gc_counts: Tuple[int, int, int]


@dataclass(frozen=True)
class GCPauseDelta:
    collections: int
    pause_ms: float
    generation_collections: Tuple[int, int, int]
    generation_pause_ms: Tuple[float, float, float]
    phase_collections: Dict[str, int]
    phase_pause_ms: Dict[str, float]
    collected_objects: int
    uncollectable_objects: int
    gc_counts_end: Tuple[int, int, int]


class GCPauseTracker:
    """Accumulate GC pauses and attribute them to a coarse caller phase."""

    def __init__(
        self,
        *,
        clock_ns: Callable[[], int] = time.perf_counter_ns,
        gc_count_fn: Callable[[], Tuple[int, int, int]] = gc.get_count,
    ):
        self._clock_ns = clock_ns
        self._gc_count_fn = gc_count_fn
        self._phase = "other"
        self._active_start_ns: Optional[int] = None
        self._active_generation = 0
        self._active_phase = "other"

        self._collections = 0
        self._pause_ns = 0
        self._generation_collections = [0, 0, 0]
        self._generation_pause_ns = [0, 0, 0]
        self._phase_collections = defaultdict(int)
        self._phase_pause_ns = defaultdict(int)
        self._collected_objects = 0
        self._uncollectable_objects = 0

    def set_phase(self, phase: str) -> None:
        self._phase = str(phase or "other")

    def callback(self, event: str, info: dict) -> None:
        """Python ``gc.callbacks`` entrypoint."""
        if event == "start":
            self._active_start_ns = self._clock_ns()
            generation = int(info.get("generation", 0) or 0)
            self._active_generation = max(0, min(2, generation))
            self._active_phase = self._phase
            return

        if event != "stop" or self._active_start_ns is None:
            return

        elapsed = max(0, self._clock_ns() - self._active_start_ns)
        generation = self._active_generation
        phase = self._active_phase or "other"

        self._collections += 1
        self._pause_ns += elapsed
        self._generation_collections[generation] += 1
        self._generation_pause_ns[generation] += elapsed
        self._phase_collections[phase] += 1
        self._phase_pause_ns[phase] += elapsed
        self._collected_objects += int(info.get("collected", 0) or 0)
        self._uncollectable_objects += int(info.get("uncollectable", 0) or 0)

        self._active_start_ns = None
        self._active_phase = "other"

    def snapshot(self) -> GCPauseSnapshot:
        return GCPauseSnapshot(
            collections=self._collections,
            pause_ns=self._pause_ns,
            generation_collections=tuple(self._generation_collections),
            generation_pause_ns=tuple(self._generation_pause_ns),
            phase_collections=dict(self._phase_collections),
            phase_pause_ns=dict(self._phase_pause_ns),
            collected_objects=self._collected_objects,
            uncollectable_objects=self._uncollectable_objects,
            gc_counts=tuple(int(value) for value in self._gc_count_fn()),
        )

    def delta_since(self, before: GCPauseSnapshot) -> GCPauseDelta:
        phase_keys = set(before.phase_collections) | set(self._phase_collections)
        phase_collections = {
            key: self._phase_collections.get(key, 0)
            - before.phase_collections.get(key, 0)
            for key in phase_keys
        }
        phase_keys = set(before.phase_pause_ns) | set(self._phase_pause_ns)
        phase_pause_ms = {
            key: (
                self._phase_pause_ns.get(key, 0)
                - before.phase_pause_ns.get(key, 0)
            )
            / 1_000_000.0
            for key in phase_keys
        }

        generation_collections = tuple(
            self._generation_collections[index]
            - before.generation_collections[index]
            for index in range(3)
        )
        generation_pause_ms = tuple(
            (
                self._generation_pause_ns[index]
                - before.generation_pause_ns[index]
            )
            / 1_000_000.0
            for index in range(3)
        )
        return GCPauseDelta(
            collections=self._collections - before.collections,
            pause_ms=(self._pause_ns - before.pause_ns) / 1_000_000.0,
            generation_collections=generation_collections,
            generation_pause_ms=generation_pause_ms,
            phase_collections=phase_collections,
            phase_pause_ms=phase_pause_ms,
            collected_objects=self._collected_objects - before.collected_objects,
            uncollectable_objects=(
                self._uncollectable_objects - before.uncollectable_objects
            ),
            gc_counts_end=tuple(int(value) for value in self._gc_count_fn()),
        )
