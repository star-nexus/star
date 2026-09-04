"""
Performance profiler for STAR.

Goals:
- separate STAR-controlled work from platform boundaries and FPS-cap waiting;
- report inclusive and exclusive (self) time so nested timers do not double-count;
- use monotonic high-resolution timing;
- make the rolling measurement window wall-clock based rather than FPS dependent;
- distinguish frame-body FPS from end-to-end window throughput;
- provide frame, controlled-work, section, and causal-metric tail statistics;
- capture exceptional p99-style slow frames with per-section diagnostics;
- retain the worst slow-frame diagnosis so rare spikes are visible in periodic stats;
- keep the established ``time_system(name)`` API available to call sites;
- add effectively zero profiling overhead when profiling is disabled.
"""

from __future__ import annotations

import json
import math
import time
from collections import defaultdict, deque
from contextlib import AbstractContextManager
from dataclasses import dataclass
from numbers import Real
from pathlib import Path
from typing import Deque, Dict, List, Optional


# ``sample_window`` is a hard safety capacity, not the statistical meaning of
# the rolling window. The semantic horizon is DEFAULT_SAMPLE_WINDOW_SECONDS.
# 4096 frames covers a five-second window up to ~819 FPS without truncation.
DEFAULT_SAMPLE_WINDOW = 4096
DEFAULT_SAMPLE_WINDOW_SECONDS = 5.0
DEFAULT_SLOW_FRAME_THRESHOLD_MS = 30.0
DEFAULT_SLOW_FRAME_P99_FACTOR = 1.5
DEFAULT_SLOW_FRAME_HISTORY = 20
TAIL_THRESHOLDS_MS = (8.33, 16.67, 33.33)

# Exclusive/self time in these categories is STAR-controlled measured work.
# Platform event handling, presentation, and intentional waits are observable
# separately and deliberately excluded from the controlled-work regression plane.
CONTROLLED_CATEGORIES = frozenset({"work", "update", "render", "vision", "input"})
PLATFORM_INPUT_CATEGORY = "platform_input"
SLOW_FRAME_SCOPE = "gameplay_epoch"


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
    """Low-overhead hierarchical wall-clock rolling profiler.

    Timers are hierarchical. ``inclusive`` time contains nested timers while
    ``self`` / ``exclusive`` time subtracts them. Percentages use self time, so
    a parent and its children do not double-count the same milliseconds.

    The statistical window is defined by elapsed wall-clock time. This matters
    because a fixed 300-frame window happened to mean ~5 seconds at 60 FPS but
    only ~1.3 seconds at ~230 FPS. ``sample_window`` remains a hard memory
    capacity; ``sample_window_seconds`` defines the measurement horizon.

    ``active`` remains a backwards-compatible frame-body concept: frame time
    excluding presentation and intentional wait. It can include platform-boundary
    work such as SDL event pumping. ``controlled_work`` is the regression-oriented
    plane: exclusive time from STAR-controlled categories only.

    Section samples are aggregated per frame and missing sections receive zero.
    Frame metrics preserve missing values explicitly rather than treating them
    as zero, so causal metrics can be used safely by regression contracts.

    Slow-frame capture is based on the window before the current frame is folded
    in. A spike therefore cannot raise its own detection threshold. Slow-frame
    history intentionally spans the whole gameplay measurement epoch, while frame
    distribution statistics describe only the current wall-clock window.

    ``reset()`` preserves run metadata and profiler configuration while starting
    a clean gameplay measurement epoch.
    """

    def __init__(
        self,
        sample_window: int = DEFAULT_SAMPLE_WINDOW,
        sample_window_seconds: float = DEFAULT_SAMPLE_WINDOW_SECONDS,
    ):
        self.sample_window = max(10, int(sample_window))
        self.sample_window_seconds = max(0.05, float(sample_window_seconds))
        self.enabled = False
        self._console_output = False

        self.frame_times_ns: Deque[int] = deque(maxlen=self.sample_window)
        self.frame_start_ns: Deque[int] = deque(maxlen=self.sample_window)
        self.frame_end_ns: Deque[int] = deque(maxlen=self.sample_window)
        self.frame_active_ns: Deque[int] = deque(maxlen=self.sample_window)
        self.frame_controlled_ns: Deque[int] = deque(maxlen=self.sample_window)
        self.frame_platform_input_ns: Deque[int] = deque(maxlen=self.sample_window)
        self.frame_present_ns: Deque[int] = deque(maxlen=self.sample_window)
        self.frame_wait_ns: Deque[int] = deque(maxlen=self.sample_window)
        self.frame_uninstrumented_ns: Deque[int] = deque(maxlen=self.sample_window)

        self.section_inclusive_ns: Dict[str, Deque[int]] = {}
        self.section_self_ns: Dict[str, Deque[int]] = {}
        self.section_categories: Dict[str, str] = {}
        self.frame_metric_samples: Dict[str, Deque[object | None]] = {}

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
        """Begin timing a frame body."""
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
        """Finish the current frame body and record its wall-clock duration."""
        if not self.enabled or not self._frame_open or self._frame_start_ns is None:
            return
        self._finish_frame_at(time.perf_counter_ns())

    def _new_section_series(self) -> Deque[int]:
        history_len = max(0, len(self.frame_times_ns) - 1)
        return deque([0] * history_len, maxlen=self.sample_window)

    def _new_metric_series(self) -> Deque[object | None]:
        history_len = max(0, len(self.frame_times_ns) - 1)
        return deque([None] * history_len, maxlen=self.sample_window)

    def _current_category_self_ns(self) -> Dict[str, int]:
        category_self_ns: Dict[str, int] = defaultdict(int)
        for name, self_ns in self._frame_self_ns.items():
            category = self.section_categories.get(name, "work")
            category_self_ns[category] += self_ns
        return category_self_ns

    @staticmethod
    def _controlled_work_ns(category_self_ns: Dict[str, int]) -> int:
        return sum(category_self_ns.get(category, 0) for category in CONTROLLED_CATEGORIES)

    def _current_budget_ns(
        self, frame_ns: int
    ) -> tuple[int, int, int, int, int, int]:
        category_self_ns = self._current_category_self_ns()
        controlled_ns = self._controlled_work_ns(category_self_ns)
        platform_input_ns = category_self_ns.get(PLATFORM_INPUT_CATEGORY, 0)
        present_ns = category_self_ns.get("present", 0)
        wait_ns = category_self_ns.get("wait", 0)
        measured_self_ns = sum(category_self_ns.values())
        active_ns = max(0, frame_ns - present_ns - wait_ns)
        uninstrumented_ns = max(0, frame_ns - measured_self_ns)
        return (
            active_ns,
            controlled_ns,
            platform_input_ns,
            present_ns,
            wait_ns,
            uninstrumented_ns,
        )

    def _finish_frame_at(self, end_ns: int) -> None:
        if self._frame_start_ns is None:
            return

        start_ns = self._frame_start_ns
        frame_ns = max(0, end_ns - start_ns)
        frame_ms = frame_ns / 1_000_000.0

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

        (
            active_ns,
            controlled_ns,
            platform_input_ns,
            present_ns,
            wait_ns,
            uninstrumented_ns,
        ) = self._current_budget_ns(frame_ns)
        self.frame_times_ns.append(frame_ns)
        self.frame_start_ns.append(start_ns)
        self.frame_end_ns.append(end_ns)
        self.frame_active_ns.append(active_ns)
        self.frame_controlled_ns.append(controlled_ns)
        self.frame_platform_input_ns.append(platform_input_ns)
        self.frame_present_ns.append(present_ns)
        self.frame_wait_ns.append(wait_ns)
        self.frame_uninstrumented_ns.append(uninstrumented_ns)

        section_names = (
            set(self.section_inclusive_ns)
            | set(self._frame_inclusive_ns)
            | set(self._frame_self_ns)
        )
        for name in section_names:
            if name not in self.section_inclusive_ns:
                self.section_inclusive_ns[name] = self._new_section_series()
                self.section_self_ns[name] = self._new_section_series()
            self.section_inclusive_ns[name].append(self._frame_inclusive_ns.get(name, 0))
            self.section_self_ns[name].append(self._frame_self_ns.get(name, 0))

        metric_names = set(self.frame_metric_samples) | set(self._frame_metrics)
        for name in metric_names:
            if name not in self.frame_metric_samples:
                self.frame_metric_samples[name] = self._new_metric_series()
            self.frame_metric_samples[name].append(self._frame_metrics.get(name))

        self._prune_wall_clock_window(end_ns)

        self._frame_open = False
        self._frame_start_ns = None
        self._timer_stack.clear()
        self._frame_inclusive_ns.clear()
        self._frame_self_ns.clear()
        self._frame_metrics.clear()

    def _prune_wall_clock_window(self, newest_end_ns: int) -> None:
        """Prune complete old frames until only the target wall-clock horizon remains."""
        cutoff_ns = newest_end_ns - int(self.sample_window_seconds * 1_000_000_000)
        while len(self.frame_end_ns) > 1 and self.frame_end_ns[0] < cutoff_ns:
            self._popleft_aligned_frame()

    def _popleft_aligned_frame(self) -> None:
        self.frame_times_ns.popleft()
        self.frame_start_ns.popleft()
        self.frame_end_ns.popleft()
        self.frame_active_ns.popleft()
        self.frame_controlled_ns.popleft()
        self.frame_platform_input_ns.popleft()
        self.frame_present_ns.popleft()
        self.frame_wait_ns.popleft()
        self.frame_uninstrumented_ns.popleft()
        for series in self.section_inclusive_ns.values():
            if series:
                series.popleft()
        for series in self.section_self_ns.values():
            if series:
                series.popleft()
        for series in self.frame_metric_samples.values():
            if series:
                series.popleft()

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
            self._timer_stack.clear()
            current = timer

        inclusive = max(0, end_ns - current.start_ns)
        exclusive = max(0, inclusive - current.child_ns)
        self.section_categories[current.name] = current.category
        self._frame_inclusive_ns[current.name] += inclusive
        self._frame_self_ns[current.name] += exclusive

        if self._timer_stack:
            self._timer_stack[-1].child_ns += inclusive

    def add_system_time(
        self,
        system_name: str,
        elapsed_time: float,
        *,
        category: str = "work",
    ) -> None:
        """Record an externally measured duration; frame-bound calls remain preferred."""
        if not self.enabled:
            return
        elapsed_ns = max(0, int(elapsed_time * 1_000_000_000))
        self.section_categories[system_name] = category
        if self._frame_open:
            self._frame_inclusive_ns[system_name] += elapsed_ns
            self._frame_self_ns[system_name] += elapsed_ns
            return

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
        """Attach a cheap causal diagnostic value to the current frame."""
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
        controlled_ms = self._controlled_work_ns(category_self_ns) / 1_000_000.0
        platform_input_ms = (
            category_self_ns.get(PLATFORM_INPUT_CATEGORY, 0) / 1_000_000.0
        )
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
            "controlled_work_ms": controlled_ms,
            "platform_input_ms": platform_input_ms,
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
            f"controlled={snapshot['controlled_work_ms']:.2f}ms  "
            f"platform_input={snapshot['platform_input_ms']:.2f}ms  "
            f"present={snapshot['present_ms']:.2f}ms  "
            f"fps_wait={snapshot['fps_limiter_wait_ms']:.2f}ms  "
            f"active_compat={snapshot['active_ms']:.2f}ms  "
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

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------
    def reset(self) -> None:
        """Start a fresh measurement epoch while preserving configuration/context."""
        self.frame_times_ns.clear()
        self.frame_start_ns.clear()
        self.frame_end_ns.clear()
        self.frame_active_ns.clear()
        self.frame_controlled_ns.clear()
        self.frame_platform_input_ns.clear()
        self.frame_present_ns.clear()
        self.frame_wait_ns.clear()
        self.frame_uninstrumented_ns.clear()
        self.section_inclusive_ns.clear()
        self.section_self_ns.clear()
        self.section_categories.clear()
        self.frame_metric_samples.clear()
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

    @classmethod
    def _series_stats_ms(cls, samples: Deque[int]) -> Dict[str, float]:
        values = [ns / 1_000_000.0 for ns in samples]
        if not values:
            return {"avg": 0.0, "p50": 0.0, "p95": 0.0, "p99": 0.0, "max": 0.0}
        return {
            "avg": sum(values) / len(values),
            "p50": cls._percentile(values, 0.50),
            "p95": cls._percentile(values, 0.95),
            "p99": cls._percentile(values, 0.99),
            "max": max(values),
        }

    @staticmethod
    def _tail_summary(values_ms: List[float]) -> Dict[str, Dict[str, float | int]]:
        total = len(values_ms)
        result: Dict[str, Dict[str, float | int]] = {}
        for threshold in TAIL_THRESHOLDS_MS:
            count = sum(1 for value in values_ms if value > threshold)
            result[f"gt_{threshold:.2f}ms"] = {
                "count": count,
                "rate": (count / total) if total else 0.0,
            }
        return result

    @classmethod
    def _metric_summary(cls, samples: Deque[object | None]) -> Dict[str, object]:
        observed = [value for value in samples if value is not None]
        base: Dict[str, object] = {
            "observed_samples": len(observed),
            "missing_samples": len(samples) - len(observed),
            "last": observed[-1] if observed else None,
        }
        numeric = [
            float(value)
            for value in observed
            if isinstance(value, Real) and not isinstance(value, bool)
        ]
        if len(numeric) == len(observed) and observed:
            base.update(
                {
                    "kind": "numeric",
                    "avg": sum(numeric) / len(numeric),
                    "min": min(numeric),
                    "max": max(numeric),
                    "p50": cls._percentile(numeric, 0.50),
                    "p95": cls._percentile(numeric, 0.95),
                    "p99": cls._percentile(numeric, 0.99),
                }
            )
            return base

        normalized = []
        for value in observed:
            if isinstance(value, (str, int, float, bool)) or value is None:
                normalized.append(value)
            else:
                normalized.append(repr(value))
        unique = []
        for value in normalized:
            if value not in unique:
                unique.append(value)
        base.update({"kind": "categorical", "values": unique})
        return base

    def _window_coverage_seconds(self) -> float:
        if not self.frame_end_ns or not self.frame_start_ns:
            return 0.0
        return max(
            0.0,
            (self.frame_end_ns[-1] - self.frame_start_ns[0]) / 1_000_000_000.0,
        )

    def _inter_frame_gap_ns(self) -> Deque[int]:
        gaps: Deque[int] = deque()
        starts = list(self.frame_start_ns)
        ends = list(self.frame_end_ns)
        for index in range(1, min(len(starts), len(ends))):
            gaps.append(max(0, starts[index] - ends[index - 1]))
        return gaps

    def get_stats(self) -> Dict:
        if not self.frame_times_ns:
            return {}

        frame_count = len(self.frame_times_ns)
        frame_ms = [ns / 1_000_000.0 for ns in self.frame_times_ns]
        active_ms_values = [ns / 1_000_000.0 for ns in self.frame_active_ns]
        controlled_ms_values = [ns / 1_000_000.0 for ns in self.frame_controlled_ns]
        avg_frame_ms = sum(frame_ms) / frame_count
        fps_samples = [1000.0 / ms for ms in frame_ms if ms > 0]

        sections = {}
        category_self_ms: Dict[str, float] = defaultdict(float)
        for name, inclusive_samples in self.section_inclusive_ns.items():
            self_samples = self.section_self_ns[name]
            inclusive_stats = self._series_stats_ms(inclusive_samples)
            self_stats = self._series_stats_ms(self_samples)
            category = self.section_categories.get(name, "work")
            category_self_ms[category] += self_stats["avg"]
            sections[name] = {
                "category": category,
                "inclusive_ms": inclusive_stats["avg"],
                "self_ms": self_stats["avg"],
                "p95_inclusive_ms": inclusive_stats["p95"],
                "p99_inclusive_ms": inclusive_stats["p99"],
                "max_inclusive_ms": inclusive_stats["max"],
                "p95_self_ms": self_stats["p95"],
                "p99_self_ms": self_stats["p99"],
                "max_self_ms": self_stats["max"],
                "frame_share_pct": (
                    self_stats["avg"] / avg_frame_ms * 100.0 if avg_frame_ms else 0.0
                ),
                "samples": frame_count,
            }

        active_stats = self._series_stats_ms(self.frame_active_ns)
        controlled_stats = self._series_stats_ms(self.frame_controlled_ns)
        platform_input_stats = self._series_stats_ms(self.frame_platform_input_ns)
        present_stats = self._series_stats_ms(self.frame_present_ns)
        wait_stats = self._series_stats_ms(self.frame_wait_ns)
        uninstrumented_stats = self._series_stats_ms(self.frame_uninstrumented_ns)
        inter_frame_gap_stats = self._series_stats_ms(self._inter_frame_gap_ns())
        coverage_s = self._window_coverage_seconds()
        window_throughput_fps = frame_count / coverage_s if coverage_s > 0.0 else 0.0
        frame_body_fps = 1000.0 / avg_frame_ms if avg_frame_ms > 0 else 0.0
        capacity_limited = (
            frame_count >= self.sample_window
            and coverage_s < self.sample_window_seconds * 0.95
        )

        metric_summaries = {
            name: self._metric_summary(samples)
            for name, samples in sorted(self.frame_metric_samples.items())
        }

        return {
            "sample_count": frame_count,
            "window_target_s": self.sample_window_seconds,
            "window_coverage_s": coverage_s,
            "window_sample_capacity": self.sample_window,
            "window_capacity_limited": capacity_limited,
            "window_throughput_fps": window_throughput_fps,
            "inter_frame_gap_ms": inter_frame_gap_stats,
            # Back-compatible FPS fields. ``avg_fps`` is the inverse of mean
            # measured frame-body duration, not full loop throughput.
            "avg_fps": frame_body_fps,
            "frame_body_fps": frame_body_fps,
            "avg_fps_semantics": "inverse_mean_frame_body_ms",
            "min_fps": min(fps_samples) if fps_samples else 0.0,
            "max_fps": max(fps_samples) if fps_samples else 0.0,
            "avg_frame_ms": avg_frame_ms,
            "p50_frame_ms": self._percentile(frame_ms, 0.50),
            "p95_frame_ms": self._percentile(frame_ms, 0.95),
            "p99_frame_ms": self._percentile(frame_ms, 0.99),
            "max_frame_ms": max(frame_ms),
            # Back-compatible average budget fields.
            "active_ms": active_stats["avg"],
            "present_ms": present_stats["avg"],
            "fps_limiter_wait_ms": wait_stats["avg"],
            "uninstrumented_ms": uninstrumented_stats["avg"],
            # Regression-oriented STAR-controlled measured work.
            "controlled_work_ms": controlled_stats["avg"],
            "platform_input_ms": platform_input_stats["avg"],
            # Tail-aware budget summaries for regression/diagnostics.
            "active_frame_ms": active_stats,
            "controlled_work_frame_ms": controlled_stats,
            "platform_input_frame_ms": platform_input_stats,
            "present_frame_ms": present_stats,
            "fps_limiter_wait_frame_ms": wait_stats,
            "uninstrumented_frame_ms": uninstrumented_stats,
            "frame_tail": self._tail_summary(frame_ms),
            "active_tail": self._tail_summary(active_ms_values),
            "controlled_work_tail": self._tail_summary(controlled_ms_values),
            "category_self_ms": dict(category_self_ms),
            "controlled_categories": sorted(CONTROLLED_CATEGORIES),
            "sections": sections,
            "frame_metrics": metric_summaries,
            "metadata": dict(self._metadata),
            # Slow-frame diagnostics intentionally span the gameplay epoch.
            "slow_frame_scope": SLOW_FRAME_SCOPE,
            "slow_frame_count": self.slow_frame_count,
            "epoch_slow_frame_count": self.slow_frame_count,
            "slow_frame_threshold_ms": self.slow_frame_threshold_ms,
            "slow_frames": list(self.slow_frames),
            "worst_slow_frame": self.worst_slow_frame,
            "epoch_worst_slow_frame": self.worst_slow_frame,
        }

    @staticmethod
    def _format_slow_frame_summary(snapshot: Dict[str, object]) -> str:
        top = snapshot.get("top_sections", [])[:3]
        top_text = "; ".join(
            f"{item['name']}={item['self_ms']:.2f}ms" for item in top
        ) or "no timed section"
        return (
            f"frame={snapshot['frame_index']}  frame_ms={snapshot['frame_ms']:.2f}  "
            f"controlled={snapshot['controlled_work_ms']:.2f}ms  "
            f"platform_input={snapshot['platform_input_ms']:.2f}ms  "
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
        print("STAR Performance Profiler")
        print("=" * 76)
        print(
            "Window: "
            f"target={stats['window_target_s']:.2f}s  "
            f"coverage={stats['window_coverage_s']:.2f}s  "
            f"frames={stats['sample_count']}  "
            f"capacity_limited={stats['window_capacity_limited']}"
        )
        print(
            "Throughput: "
            f"window={stats['window_throughput_fps']:.1f} fps  "
            f"frame_body={stats['frame_body_fps']:.1f} fps  "
            f"inter_frame_gap_avg={stats['inter_frame_gap_ms']['avg']:.3f}ms"
        )
        print(
            f"Frame-body FPS min/max: {stats['min_fps']:.1f} / {stats['max_fps']:.1f}"
        )
        print(
            "Frame ms avg/p50/p95/p99/max: "
            f"{stats['avg_frame_ms']:.2f} / {stats['p50_frame_ms']:.2f} / "
            f"{stats['p95_frame_ms']:.2f} / {stats['p99_frame_ms']:.2f} / "
            f"{stats['max_frame_ms']:.2f}"
        )
        controlled = stats["controlled_work_frame_ms"]
        print(
            "Controlled work ms avg/p50/p95/p99/max: "
            f"{controlled['avg']:.2f} / {controlled['p50']:.2f} / "
            f"{controlled['p95']:.2f} / {controlled['p99']:.2f} / "
            f"{controlled['max']:.2f}"
        )
        print(
            "Frame budget avg: "
            f"controlled={stats['controlled_work_ms']:.2f}ms  "
            f"platform_input={stats['platform_input_ms']:.2f}ms  "
            f"present={stats['present_ms']:.2f}ms  "
            f"fps_cap_wait={stats['fps_limiter_wait_ms']:.2f}ms  "
            f"active_compat={stats['active_ms']:.2f}ms  "
            f"uninstrumented={stats['uninstrumented_ms']:.2f}ms"
        )
        print(
            "Slow-frame capture: "
            f"scope={stats['slow_frame_scope']}  "
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
                f"p99={data['p99_self_ms']:7.2f}ms "
                f"incl={data['inclusive_ms']:7.2f}ms "
                f"({data['frame_share_pct']:5.1f}%) "
                f"[{data['category']}]"
            )

    def write_json(self, path: str | Path) -> None:
        """Persist the current wall-clock rolling snapshot for diagnostics/gates."""
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
