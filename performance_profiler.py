"""
Performance profiler v2 for STAR.

Goals:
- separate active work from presentation / FPS-cap waiting;
- report inclusive and exclusive (self) time so nested timers do not double-count;
- use monotonic high-resolution timing;
- provide frame-time percentiles for runtime diagnostics;
- capture exceptional p99-style slow frames with per-section diagnostics;
- retain the worst slow-frame diagnosis so rare spikes are visible in periodic stats;
- keep the old ``time_system(name)`` API compatible with existing call sites;
- add effectively zero profiling overhead when profiling is disabled.
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
DEFAULT_SLOW_FRAME_THRESHOLD_MS = 30.0
DEFAULT_SLOW_FRAME_P99_FACTOR = 1.5
DEFAULT_SLOW_FRAME_HISTORY = 20


@dataclass(slots=True)
class _ActiveTimer:
    name: str
    category: str
    start_ns: int
    child_ns: int = 0


class _NoopTimer(AbstractContextManager):
    __slots__ = ()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False


_NOOP_TIMER = _NoopTimer()


class PerformanceProfiler:
    """Low-overhead hierarchical rolling-window frame profiler.

    Timers are hierarchical. ``inclusive`` time contains nested timers while
    ``self`` / ``exclusive`` time subtracts them. Percentages use self time, so
    a parent and its children no longer double-count the same milliseconds.

    Section samples are aggregated *per frame* and missing sections receive a
    zero for that frame. This makes percentages meaningful even for systems
    that do not execute every frame.

    Slow-frame capture is based on the frame *before* its samples are folded
    into the rolling window. A spike therefore cannot raise its own detection
    threshold. The threshold is the larger of an absolute floor (30ms by
    default) and 1.5x the previous rolling p99 once enough history exists.

    ``reset()`` intentionally preserves run metadata and the enabled/console
    switches. GameScene uses that behavior to drop menu/map-initialization
    samples and begin a clean gameplay measurement epoch.
    """

    def __init__(self, sample_window: int = DEFAULT_SAMPLE_WINDOW):
        self.sample_window = max(10, int(sample_window))
        self.enabled = False
        self._console_output = False

        self.frame_times_ns: Deque[int] = deque(maxlen=self.sample_window)
        self.section_inclusive_ns: Dict[str, Deque[int]] = {}
        self.section_self_ns: Dict[str, Deque[int]] = {}
        self.section_categories: Dict[str, str] = {}

        self._timer_stack: List[_ActiveTimer] = []
        self._frame_start_ns: Optional[int] = None
        self._frame_open = False
        self._frame_inclusive_ns: Dict[str, int] = defaultdict(int)
        self._frame_self_ns: Dict[str, int] = defaultdict(int)
        self._metadata: Dict[str, object] = {}
        self._frame_metrics: Dict[str, object] = {}
        self._frame_index = 0

        self.slow_frame_threshold_ms = DEFAULT_SLOW_FRAME_THRESHOLD_MS
        self.slow_frame_p99_factor = DEFAULT_SLOW_FRAME_P99_FACTOR
        self.slow_frame_min_history = 30
        self.slow_frames: Deque[Dict[str, object]] = deque(
            maxlen=DEFAULT_SLOW_FRAME_HISTORY
        )
        self.slow_frame_count = 0
        self.worst_slow_frame: Optional[Dict[str, object]] = None
        self.slow_frame_log_cooldown_s = 0.5
        self._last_slow_frame_log_time = 0.0

    @property
    def enable_profiler(self) -> bool:
        """Back-compatible console switch."""
        return self._console_output

    @enable_profiler.setter
    def enable_profiler(self, value: bool) -> None:
        self._console_output = bool(value)
        if value:
            self.enabled = True

    # ------------------------------------------------------------------
    # Frame lifecycle
    # ------------------------------------------------------------------
    def start_frame(self) -> None:
        """Begin timing a frame."""
        if not self.enabled:
            return
        now = time.perf_counter_ns()
        if self._frame_open and self._frame_start_ns is not None:
            self._finish_frame_at(now)

        self._frame_start_ns = now
        self._frame_open = True
        self._timer_stack.clear()
        self._frame_inclusive_ns.clear()
        self._frame_self_ns.clear()
        self._frame_metrics.clear()

    def end_frame(self) -> None:
        """Finish the current frame and record its total wall-clock duration."""
        if not self.enabled or not self._frame_open or self._frame_start_ns is None:
            return
        self._finish_frame_at(time.perf_counter_ns())

    def _new_section_series(self) -> Deque[int]:
        # A section first observed now was absent in previous retained frames.
        history_len = max(0, len(self.frame_times_ns) - 1)
        return deque([0] * history_len, maxlen=self.sample_window)

    def _finish_frame_at(self, end_ns: int) -> None:
        if self._frame_start_ns is None:
            return

        frame_ns = max(0, end_ns - self._frame_start_ns)
        frame_ms = frame_ns / 1_000_000.0

        # Detect against the previous window so a spike cannot raise its own
        # threshold before it is evaluated.
        previous_frame_ms = [ns / 1_000_000.0 for ns in self.frame_times_ns]
        p99_reference_ms = (
            self._percentile(previous_frame_ms, 0.99)
            if len(previous_frame_ms) >= self.slow_frame_min_history
            else 0.0
        )
        dynamic_threshold_ms = self.slow_frame_threshold_ms
        if p99_reference_ms > 0.0:
            dynamic_threshold_ms = max(
                dynamic_threshold_ms,
                p99_reference_ms * self.slow_frame_p99_factor,
            )

        self._frame_index += 1
        if frame_ms >= dynamic_threshold_ms:
            self._capture_slow_frame(
                frame_ms=frame_ms,
                threshold_ms=dynamic_threshold_ms,
                p99_reference_ms=p99_reference_ms,
            )

        self.frame_times_ns.append(frame_ns)

        names = (
            set(self.section_inclusive_ns)
            | set(self._frame_inclusive_ns)
            | set(self._frame_self_ns)
        )
        for name in names:
            if name not in self.section_inclusive_ns:
                self.section_inclusive_ns[name] = self._new_section_series()
                self.section_self_ns[name] = self._new_section_series()
            self.section_inclusive_ns[name].append(self._frame_inclusive_ns.get(name, 0))
            self.section_self_ns[name].append(self._frame_self_ns.get(name, 0))

        self._frame_open = False
        self._frame_start_ns = None
        self._timer_stack.clear()
        self._frame_inclusive_ns.clear()
        self._frame_self_ns.clear()
        self._frame_metrics.clear()

    # ------------------------------------------------------------------
    # Timers
    # ------------------------------------------------------------------
    def time_system(self, system_name: str, *, category: str = "work"):
        """Return a hierarchical timer context manager."""
        if not self.enabled:
            return _NOOP_TIMER
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
        if current is not timer:
            # Recover safely from malformed nesting instead of attributing child
            # time to the wrong parent.
            self._timer_stack.clear()
            current = timer

        inclusive = max(0, end_ns - current.start_ns)
        exclusive = max(0, inclusive - current.child_ns)
        self.section_categories[current.name] = current.category
        self._frame_inclusive_ns[current.name] += inclusive
        self._frame_self_ns[current.name] += exclusive

        if self._timer_stack:
            self._timer_stack[-1].child_ns += inclusive

    # Backwards compatibility for older tests/callers.
    def add_system_time(
        self,
        system_name: str,
        elapsed_time: float,
        *,
        category: str = "work",
    ) -> None:
        if not self.enabled:
            return
        elapsed_ns = max(0, int(elapsed_time * 1_000_000_000))
        self.section_categories[system_name] = category
        if self._frame_open:
            self._frame_inclusive_ns[system_name] += elapsed_ns
            self._frame_self_ns[system_name] += elapsed_ns
            return

        # Legacy out-of-frame recording. Keep it visible without pretending it
        # has a frame percentage until a frame sample exists.
        series = self.section_inclusive_ns.setdefault(
            system_name, deque(maxlen=self.sample_window)
        )
        self_series = self.section_self_ns.setdefault(
            system_name, deque(maxlen=self.sample_window)
        )
        series.append(elapsed_ns)
        self_series.append(elapsed_ns)

    # ------------------------------------------------------------------
    # Metadata / slow-frame diagnostics
    # ------------------------------------------------------------------
    def set_metadata(self, **values: object) -> None:
        """Set run-level context that is copied into summary output."""
        self._metadata.update(values)

    def set_frame_metric(self, name: str, value: object) -> None:
        """Attach a cheap diagnostic value to the current frame."""
        if self.enabled and self._frame_open:
            self._frame_metrics[name] = value

    def _capture_slow_frame(
        self,
        *,
        frame_ms: float,
        threshold_ms: float,
        p99_reference_ms: float,
    ) -> None:
        category_self_ns: Dict[str, int] = defaultdict(int)
        top_sections = []
        for name in set(self._frame_self_ns) | set(self._frame_inclusive_ns):
            self_ns = self._frame_self_ns.get(name, 0)
            inclusive_ns = self._frame_inclusive_ns.get(name, 0)
            category = self.section_categories.get(name, "work")
            category_self_ns[category] += self_ns
            top_sections.append(
                {
                    "name": name,
                    "category": category,
                    "self_ms": self_ns / 1_000_000.0,
                    "inclusive_ms": inclusive_ns / 1_000_000.0,
                }
            )

        top_sections.sort(key=lambda item: item["self_ms"], reverse=True)
        present_ms = category_self_ns.get("present", 0) / 1_000_000.0
        wait_ms = category_self_ns.get("wait", 0) / 1_000_000.0
        measured_self_ms = sum(category_self_ns.values()) / 1_000_000.0
        active_ms = max(0.0, frame_ms - present_ms - wait_ms)
        uninstrumented_ms = max(0.0, frame_ms - measured_self_ms)

        snapshot: Dict[str, object] = {
            "frame_index": self._frame_index,
            "frame_ms": frame_ms,
            "threshold_ms": threshold_ms,
            "p99_reference_ms": p99_reference_ms,
            "active_ms": active_ms,
            "present_ms": present_ms,
            "fps_limiter_wait_ms": wait_ms,
            "measured_self_ms": measured_self_ms,
            "uninstrumented_ms": uninstrumented_ms,
            "frame_metrics": dict(self._frame_metrics),
            "top_sections": top_sections[:10],
        }
        self.slow_frames.append(snapshot)
        self.slow_frame_count += 1
        if (
            self.worst_slow_frame is None
            or frame_ms > float(self.worst_slow_frame.get("frame_ms", 0.0))
        ):
            self.worst_slow_frame = snapshot

        if not self._console_output:
            return
        now = time.monotonic()
        if now - self._last_slow_frame_log_time < self.slow_frame_log_cooldown_s:
            return
        self._last_slow_frame_log_time = now
        self._print_slow_frame(snapshot)

    @staticmethod
    def _print_slow_frame(snapshot: Dict[str, object]) -> None:
        print("\n" + "!" * 76)
        print(
            "[SLOW FRAME] "
            f"frame={snapshot['frame_index']}  "
            f"frame_ms={snapshot['frame_ms']:.2f}  "
            f"threshold={snapshot['threshold_ms']:.2f}  "
            f"prior_p99={snapshot['p99_reference_ms']:.2f}"
        )
        print(
            "  budget: "
            f"active={snapshot['active_ms']:.2f}ms  "
            f"present={snapshot['present_ms']:.2f}ms  "
            f"fps_wait={snapshot['fps_limiter_wait_ms']:.2f}ms  "
            f"uninstrumented={snapshot['uninstrumented_ms']:.2f}ms"
        )
        metrics = snapshot.get("frame_metrics", {})
        if metrics:
            metric_text = "  ".join(f"{k}={v}" for k, v in sorted(metrics.items()))
            print(f"  frame metrics: {metric_text}")
        print("  top sections:")
        for section in snapshot.get("top_sections", [])[:8]:
            print(
                f"    {section['name']:26} "
                f"self={section['self_ms']:7.2f}ms "
                f"incl={section['inclusive_ms']:7.2f}ms "
                f"[{section['category']}]"
            )
        print("!" * 76)

    def reset(self) -> None:
        """Start a fresh measurement epoch while preserving configuration/context."""
        self.frame_times_ns.clear()
        self.section_inclusive_ns.clear()
        self.section_self_ns.clear()
        self.section_categories.clear()
        self._timer_stack.clear()
        self._frame_start_ns = None
        self._frame_open = False
        self._frame_inclusive_ns.clear()
        self._frame_self_ns.clear()
        self._frame_metrics.clear()
        self._frame_index = 0
        self.slow_frames.clear()
        self.slow_frame_count = 0
        self.worst_slow_frame = None
        self._last_slow_frame_log_time = 0.0

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
    def _avg_ms(samples: Deque[int], frame_count: int) -> float:
        if not samples or frame_count <= 0:
            return 0.0
        return sum(samples) / max(1, min(len(samples), frame_count)) / 1_000_000.0

    def get_stats(self) -> Dict:
        if not self.frame_times_ns:
            return {}

        frame_count = len(self.frame_times_ns)
        frame_ms = [ns / 1_000_000.0 for ns in self.frame_times_ns]
        avg_frame_ms = sum(frame_ms) / frame_count
        fps_samples = [1000.0 / ms for ms in frame_ms if ms > 0]

        sections = {}
        category_self_ms: Dict[str, float] = defaultdict(float)
        for name, inclusive_samples in self.section_inclusive_ns.items():
            self_samples = self.section_self_ns[name]
            inclusive_ms = self._avg_ms(inclusive_samples, frame_count)
            self_ms = self._avg_ms(self_samples, frame_count)
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
                "samples": frame_count,
            }

        present_ms = category_self_ms.get("present", 0.0)
        limiter_ms = category_self_ms.get("wait", 0.0)
        measured_self_ms = sum(category_self_ms.values())
        uninstrumented_ms = max(0.0, avg_frame_ms - measured_self_ms)
        active_ms = max(0.0, avg_frame_ms - present_ms - limiter_ms)

        return {
            "sample_count": frame_count,
            "avg_fps": (1000.0 / avg_frame_ms) if avg_frame_ms > 0 else 0.0,
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
            "slow_frame_count": self.slow_frame_count,
            "slow_frame_threshold_ms": self.slow_frame_threshold_ms,
            "slow_frames": list(self.slow_frames),
            "worst_slow_frame": self.worst_slow_frame,
        }

    @staticmethod
    def _format_slow_frame_summary(snapshot: Dict[str, object]) -> str:
        top = snapshot.get("top_sections", [])[:3]
        top_text = "; ".join(
            f"{item['name']}={item['self_ms']:.2f}ms" for item in top
        ) or "no timed section"
        return (
            f"frame={snapshot['frame_index']}  frame_ms={snapshot['frame_ms']:.2f}  "
            f"active={snapshot['active_ms']:.2f}ms  "
            f"uninstrumented={snapshot['uninstrumented_ms']:.2f}ms  "
            f"top: {top_text}"
        )

    def print_stats(self) -> None:
        if not self._console_output:
            return
        stats = self.get_stats()
        if not stats:
            return

        print("\n" + "=" * 76)
        print("STAR Performance Profiler v2")
        print("=" * 76)
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
        print(
            "Slow-frame capture: "
            f"count={stats['slow_frame_count']}  "
            f"absolute_floor={stats['slow_frame_threshold_ms']:.1f}ms  "
            f"rule=max(floor, prior_p99×{self.slow_frame_p99_factor:.2f})"
        )
        if stats.get("worst_slow_frame"):
            print(
                "Worst slow frame this gameplay epoch: "
                + self._format_slow_frame_summary(stats["worst_slow_frame"])
            )
        if stats["metadata"]:
            meta = "  ".join(f"{k}={v}" for k, v in sorted(stats["metadata"].items()))
            print(f"Context: {meta}")

        print("\nTimed sections (self/exclusive drives %, inclusive shows nesting):")
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
        """Persist the current rolling-window snapshot for diagnostics."""
        Path(path).write_text(
            json.dumps(self.get_stats(), indent=2, sort_keys=True),
            encoding="utf-8",
        )


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
