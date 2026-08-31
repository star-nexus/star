"""
Performance profiler v2 for STAR.

Goals:
- separate active work from presentation / FPS-cap waiting;
- report inclusive and exclusive (self) time so nested timers do not double-count;
- use monotonic high-resolution timing;
- provide frame-time percentiles for scale-up experiments;
- keep the old ``time_system(name)`` API compatible with existing call sites.
"""

from __future__ import annotations

import json
import math
import time
from collections import defaultdict, deque
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path
from typing import Deque, Dict, List, Optional


DEFAULT_SAMPLE_WINDOW = 300


@dataclass(slots=True)
class _ActiveTimer:
    name: str
    category: str
    start_ns: int
    child_ns: int = 0


class PerformanceProfiler:
    """Low-overhead hierarchical frame profiler.

    Timers are hierarchical.  ``inclusive`` time includes nested timers while
    ``self`` / ``exclusive`` time subtracts them.  Percentages are based on
    exclusive time, so nested sections no longer make the table add up to more
    than 100% merely because both a parent and its children were measured.
    """

    def __init__(self, sample_window: int = DEFAULT_SAMPLE_WINDOW):
        self.sample_window = max(10, int(sample_window))
        self.enable_profiler = False

        self.frame_times_ns: Deque[int] = deque(maxlen=self.sample_window)
        self.section_inclusive_ns: Dict[str, Deque[int]] = defaultdict(
            lambda: deque(maxlen=self.sample_window)
        )
        self.section_self_ns: Dict[str, Deque[int]] = defaultdict(
            lambda: deque(maxlen=self.sample_window)
        )
        self.section_categories: Dict[str, str] = {}

        self._timer_stack: List[_ActiveTimer] = []
        self._frame_start_ns: Optional[int] = None
        self._last_frame_end_ns: Optional[int] = None
        self._frame_open = False
        self._metadata: Dict[str, object] = {}

    # ------------------------------------------------------------------
    # Frame lifecycle
    # ------------------------------------------------------------------
    def start_frame(self) -> None:
        """Begin timing a frame.

        ``end_frame`` should be called after the FPS limiter.  If an old call
        site forgets to end the previous frame, starting the next one closes it
        at this instant so profiling remains usable rather than silently dying.
        """
        now = time.perf_counter_ns()
        if self._frame_open and self._frame_start_ns is not None:
            self._finish_frame_at(now)
        self._frame_start_ns = now
        self._frame_open = True
        self._timer_stack.clear()

    def end_frame(self) -> None:
        """Finish the current frame and record its wall-clock duration."""
        if not self._frame_open or self._frame_start_ns is None:
            return
        self._finish_frame_at(time.perf_counter_ns())

    def _finish_frame_at(self, end_ns: int) -> None:
        if self._frame_start_ns is None:
            return
        duration = max(0, end_ns - self._frame_start_ns)
        self.frame_times_ns.append(duration)
        self._last_frame_end_ns = end_ns
        self._frame_open = False
        self._frame_start_ns = None
        self._timer_stack.clear()

    # ------------------------------------------------------------------
    # Timers
    # ------------------------------------------------------------------
    def time_system(self, system_name: str, *, category: str = "work"):
        """Return a hierarchical timer context manager.

        Existing code may keep calling ``time_system(name)``.  Engine-level
        phases can additionally tag timers as ``present`` or ``wait``.
        """
        return SystemTimer(self, system_name, category)

    def _push_timer(self, name: str, category: str) -> _ActiveTimer:
        timer = _ActiveTimer(name=name, category=category, start_ns=time.perf_counter_ns())
        self._timer_stack.append(timer)
        return timer

    def _pop_timer(self, timer: _ActiveTimer) -> None:
        end_ns = time.perf_counter_ns()
        if not self._timer_stack:
            return

        current = self._timer_stack.pop()
        # Defensive recovery for exceptional / mismatched context-manager use.
        if current is not timer:
            self._timer_stack.clear()
            current = timer

        inclusive = max(0, end_ns - current.start_ns)
        exclusive = max(0, inclusive - current.child_ns)

        self.section_categories[current.name] = current.category
        self.section_inclusive_ns[current.name].append(inclusive)
        self.section_self_ns[current.name].append(exclusive)

        if self._timer_stack:
            self._timer_stack[-1].child_ns += inclusive

    # Back-compat with v1 callers/tests that recorded an already-measured span.
    def add_system_time(
        self,
        system_name: str,
        elapsed_time: float,
        *,
        category: str = "work",
    ) -> None:
        elapsed_ns = max(0, int(elapsed_time * 1_000_000_000))
        self.section_categories[system_name] = category
        self.section_inclusive_ns[system_name].append(elapsed_ns)
        self.section_self_ns[system_name].append(elapsed_ns)

    # ------------------------------------------------------------------
    # Metadata / output
    # ------------------------------------------------------------------
    def set_metadata(self, **values: object) -> None:
        self._metadata.update(values)

    def reset(self) -> None:
        self.frame_times_ns.clear()
        self.section_inclusive_ns.clear()
        self.section_self_ns.clear()
        self.section_categories.clear()
        self._timer_stack.clear()
        self._frame_start_ns = None
        self._last_frame_end_ns = None
        self._frame_open = False

    @staticmethod
    def _percentile(values: List[float], q: float) -> float:
        if not values:
            return 0.0
        ordered = sorted(values)
        if len(ordered) == 1:
            return ordered[0]
        rank = (len(ordered) - 1) * q
        lo = math.floor(rank)
        hi = math.ceil(rank)
        if lo == hi:
            return ordered[lo]
        frac = rank - lo
        return ordered[lo] * (1.0 - frac) + ordered[hi] * frac

    @staticmethod
    def _avg_ms(samples: Deque[int]) -> float:
        return (sum(samples) / len(samples) / 1_000_000.0) if samples else 0.0

    def get_stats(self) -> Dict:
        if not self.frame_times_ns:
            return {}

        frame_ms = [ns / 1_000_000.0 for ns in self.frame_times_ns]
        avg_frame_ms = sum(frame_ms) / len(frame_ms)
        fps_samples = [1000.0 / ms for ms in frame_ms if ms > 0]

        sections = {}
        category_self_ms: Dict[str, float] = defaultdict(float)
        for name, inclusive_samples in self.section_inclusive_ns.items():
            self_samples = self.section_self_ns[name]
            inclusive_ms = self._avg_ms(inclusive_samples)
            self_ms = self._avg_ms(self_samples)
            category = self.section_categories.get(name, "work")
            category_self_ms[category] += self_ms
            sections[name] = {
                "category": category,
                "inclusive_ms": inclusive_ms,
                "self_ms": self_ms,
                "max_inclusive_ms": (
                    max(inclusive_samples) / 1_000_000.0 if inclusive_samples else 0.0
                ),
                "max_self_ms": max(self_samples) / 1_000_000.0 if self_samples else 0.0,
                "frame_share_pct": (self_ms / avg_frame_ms * 100.0) if avg_frame_ms else 0.0,
                "samples": len(inclusive_samples),
            }

        present_ms = category_self_ms.get("present", 0.0)
        limiter_ms = category_self_ms.get("wait", 0.0)
        measured_self_ms = sum(category_self_ms.values())
        uninstrumented_ms = max(0.0, avg_frame_ms - measured_self_ms)
        active_ms = max(0.0, avg_frame_ms - present_ms - limiter_ms)

        return {
            "sample_count": len(frame_ms),
            "avg_fps": (sum(fps_samples) / len(fps_samples)) if fps_samples else 0.0,
            "min_fps": min(fps_samples) if fps_samples else 0.0,
            "max_fps": max(fps_samples) if fps_samples else 0.0,
            "avg_frame_ms": avg_frame_ms,
            "p50_frame_ms": self._percentile(frame_ms, 0.50),
            "p95_frame_ms": self._percentile(frame_ms, 0.95),
            "p99_frame_ms": self._percentile(frame_ms, 0.99),
            "active_ms": active_ms,
            "present_ms": present_ms,
            "fps_limiter_wait_ms": limiter_ms,
            "uninstrumented_ms": uninstrumented_ms,
            "category_self_ms": dict(category_self_ms),
            "sections": sections,
            "metadata": dict(self._metadata),
        }

    def print_stats(self) -> None:
        if not self.enable_profiler:
            return
        stats = self.get_stats()
        if not stats:
            return

        print("\n" + "=" * 72)
        print("STAR Performance Profiler v2")
        print("=" * 72)
        print(
            f"FPS avg/min/max: {stats['avg_fps']:.1f} / "
            f"{stats['min_fps']:.1f} / {stats['max_fps']:.1f}"
        )
        print(
            "Frame ms avg/p50/p95/p99: "
            f"{stats['avg_frame_ms']:.2f} / {stats['p50_frame_ms']:.2f} / "
            f"{stats['p95_frame_ms']:.2f} / {stats['p99_frame_ms']:.2f}"
        )
        print(
            "Frame budget: "
            f"active={stats['active_ms']:.2f}ms  "
            f"present={stats['present_ms']:.2f}ms  "
            f"fps_cap_wait={stats['fps_limiter_wait_ms']:.2f}ms  "
            f"uninstrumented={stats['uninstrumented_ms']:.2f}ms"
        )
        if stats["metadata"]:
            meta = "  ".join(f"{k}={v}" for k, v in sorted(stats["metadata"].items()))
            print(f"Context: {meta}")

        print("\nTimed sections (exclusive/self time drives %; inclusive shown for nesting):")
        section_stats = sorted(
            stats["sections"].items(),
            key=lambda item: item[1]["self_ms"],
            reverse=True,
        )
        for name, data in section_stats:
            print(
                f"  {name:28} "
                f"self={data['self_ms']:7.2f}ms "
                f"incl={data['inclusive_ms']:7.2f}ms "
                f"({data['frame_share_pct']:5.1f}%) "
                f"[{data['category']}]"
            )

    def write_json(self, path: str | Path) -> None:
        """Persist the current rolling-window snapshot for experiment logs."""
        stats = self.get_stats()
        Path(path).write_text(json.dumps(stats, indent=2, sort_keys=True), encoding="utf-8")


class SystemTimer(AbstractContextManager):
    def __init__(self, profiler: PerformanceProfiler, system_name: str, category: str):
        self.profiler = profiler
        self.system_name = system_name
        self.category = category
        self._timer: Optional[_ActiveTimer] = None

    def __enter__(self):
        self._timer = self.profiler._push_timer(self.system_name, self.category)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._timer is not None:
            self.profiler._pop_timer(self._timer)
        return False


# Global profiler installed into ``framework.ecs.profiling`` by rotk_env.main.
profiler = PerformanceProfiler()
