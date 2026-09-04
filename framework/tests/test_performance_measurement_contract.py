"""Measurement-contract tests for the STAR performance profiler."""

from __future__ import annotations

import pytest

import performance_profiler as profiler_module
from performance_profiler import PerformanceProfiler


def _clock(monkeypatch, values_ns):
    values = iter(values_ns)
    monkeypatch.setattr(profiler_module.time, "perf_counter_ns", lambda: next(values))


def _enabled(*, capacity=4096, seconds=5.0):
    profiler = PerformanceProfiler(
        sample_window=capacity,
        sample_window_seconds=seconds,
    )
    profiler.enabled = True
    return profiler


def test_wall_clock_window_keeps_about_five_seconds_at_high_fps(monkeypatch):
    # 1200 frames at 5ms/frame represent six seconds at 200 FPS. A historical
    # fixed 300-frame window would retain only 1.5 seconds. The measurement
    # contract must retain ~5 seconds independent of frame rate.
    values = []
    frame_ns = 5_000_000
    for index in range(1200):
        start = index * frame_ns
        values.extend([start, start + frame_ns])
    _clock(monkeypatch, values)

    profiler = _enabled(capacity=2000, seconds=5.0)
    for _ in range(1200):
        profiler.start_frame()
        profiler.end_frame()

    stats = profiler.get_stats()
    assert 995 <= stats["sample_count"] <= 1005
    assert stats["sample_count"] > 300
    assert stats["window_coverage_s"] == pytest.approx(5.0, abs=0.02)
    assert stats["window_target_s"] == pytest.approx(5.0)
    assert stats["window_capacity_limited"] is False


def test_window_reports_when_hard_frame_capacity_truncates_horizon(monkeypatch):
    values = []
    frame_ns = 5_000_000
    for index in range(200):
        start = index * frame_ns
        values.extend([start, start + frame_ns])
    _clock(monkeypatch, values)

    profiler = _enabled(capacity=100, seconds=5.0)
    for _ in range(200):
        profiler.start_frame()
        profiler.end_frame()

    stats = profiler.get_stats()
    assert stats["sample_count"] == 100
    assert stats["window_coverage_s"] < 1.0
    assert stats["window_capacity_limited"] is True


def test_active_tail_is_separate_from_present_and_intentional_wait(monkeypatch):
    # ``active`` is the backwards-compatible frame-body budget excluding only
    # presentation and intentional wait. Controlled work is tested separately.
    _clock(
        monkeypatch,
        [
            0,
            0,
            4_000_000,
            4_000_000,
            10_000_000,
            10_000_000,
            40_000_000,
            40_000_000,
        ],
    )
    profiler = _enabled()

    profiler.start_frame()
    with profiler.time_system("scene_update", category="update"):
        pass
    with profiler.time_system("display_present", category="present"):
        pass
    with profiler.time_system("fps_limiter_wait", category="wait"):
        pass
    profiler.end_frame()

    stats = profiler.get_stats()
    assert stats["max_frame_ms"] == pytest.approx(40.0)
    assert stats["active_frame_ms"]["max"] == pytest.approx(4.0)
    assert stats["present_frame_ms"]["max"] == pytest.approx(6.0)
    assert stats["fps_limiter_wait_frame_ms"]["max"] == pytest.approx(30.0)
    assert stats["frame_tail"]["gt_33.33ms"]["count"] == 1
    assert stats["active_tail"]["gt_8.33ms"]["count"] == 0


def test_controlled_work_excludes_platform_input_present_and_wait(monkeypatch):
    # A 30ms frame contains 10ms SDL/platform input, 4ms STAR-controlled input
    # work, 4ms presentation and 12ms intentional wait. ``active`` remains 14ms
    # for compatibility, while controlled work is the regression-oriented 4ms.
    _clock(
        monkeypatch,
        [
            0,
            0,
            1_000_000,
            11_000_000,
            11_000_000,
            13_000_000,
            14_000_000,
            14_000_000,
            18_000_000,
            18_000_000,
            30_000_000,
            30_000_000,
        ],
    )
    profiler = _enabled()

    profiler.start_frame()
    with profiler.time_system("input_system", category="input"):
        with profiler.time_system("input_event_pump", category="platform_input"):
            pass
        with profiler.time_system("input_dispatch", category="input"):
            pass
    with profiler.time_system("display_present", category="present"):
        pass
    with profiler.time_system("fps_limiter_wait", category="wait"):
        pass
    profiler.end_frame()

    stats = profiler.get_stats()
    assert stats["active_ms"] == pytest.approx(14.0)
    assert stats["controlled_work_ms"] == pytest.approx(4.0)
    assert stats["platform_input_ms"] == pytest.approx(10.0)
    assert stats["present_ms"] == pytest.approx(4.0)
    assert stats["fps_limiter_wait_ms"] == pytest.approx(12.0)
    assert stats["controlled_work_frame_ms"]["p99"] == pytest.approx(4.0)
    assert stats["controlled_work_tail"]["gt_8.33ms"]["count"] == 0
    assert stats["sections"]["input_event_pump"]["category"] == "platform_input"


def test_window_throughput_includes_inter_frame_gap(monkeypatch):
    # Three 10ms frame bodies separated by 2ms of loop/profiler bookkeeping.
    # Frame-body FPS is 100, but end-to-end window throughput is lower.
    _clock(
        monkeypatch,
        [
            0,
            10_000_000,
            12_000_000,
            22_000_000,
            24_000_000,
            34_000_000,
        ],
    )
    profiler = _enabled(seconds=1.0)

    for _ in range(3):
        profiler.start_frame()
        profiler.end_frame()

    stats = profiler.get_stats()
    assert stats["frame_body_fps"] == pytest.approx(100.0)
    assert stats["avg_fps"] == pytest.approx(stats["frame_body_fps"])
    assert stats["avg_fps_semantics"] == "inverse_mean_frame_body_ms"
    assert stats["window_coverage_s"] == pytest.approx(0.034)
    assert stats["window_throughput_fps"] == pytest.approx(3.0 / 0.034)
    assert stats["inter_frame_gap_ms"]["avg"] == pytest.approx(2.0)
    assert stats["inter_frame_gap_ms"]["max"] == pytest.approx(2.0)


def test_slow_frame_scope_is_explicitly_gameplay_epoch(monkeypatch):
    _clock(monkeypatch, [0, 40_000_000])
    profiler = _enabled()

    profiler.start_frame()
    profiler.end_frame()

    stats = profiler.get_stats()
    assert stats["slow_frame_scope"] == "gameplay_epoch"
    assert stats["slow_frame_count"] == 1
    assert stats["epoch_slow_frame_count"] == 1
    assert stats["epoch_worst_slow_frame"] == stats["worst_slow_frame"]


def test_section_stats_include_p95_and_p99(monkeypatch):
    _clock(
        monkeypatch,
        [
            0,
            0,
            2_000_000,
            10_000_000,
            10_000_000,
            10_000_000,
            16_000_000,
            20_000_000,
        ],
    )
    profiler = _enabled()

    profiler.start_frame()
    with profiler.time_system("work"):
        pass
    profiler.end_frame()

    profiler.start_frame()
    with profiler.time_system("work"):
        pass
    profiler.end_frame()

    work = profiler.get_stats()["sections"]["work"]
    assert work["self_ms"] == pytest.approx(4.0)
    assert work["max_self_ms"] == pytest.approx(6.0)
    assert 5.0 < work["p95_self_ms"] <= 6.0
    assert 5.0 < work["p99_self_ms"] <= 6.0


def test_frame_metrics_are_summarized_without_treating_missing_as_zero(monkeypatch):
    _clock(
        monkeypatch,
        [0, 10_000_000, 10_000_000, 20_000_000, 20_000_000, 30_000_000],
    )
    profiler = _enabled()

    profiler.start_frame()
    profiler.set_frame_metric("vision_units_scanned", 1)
    profiler.set_frame_metric("vision_mode", "dirty_refcount")
    profiler.end_frame()

    profiler.start_frame()
    profiler.set_frame_metric("vision_units_scanned", 3)
    profiler.set_frame_metric("vision_mode", "dirty_refcount")
    profiler.end_frame()

    profiler.start_frame()
    profiler.end_frame()

    metrics = profiler.get_stats()["frame_metrics"]
    scanned = metrics["vision_units_scanned"]
    assert scanned["kind"] == "numeric"
    assert scanned["observed_samples"] == 2
    assert scanned["missing_samples"] == 1
    assert scanned["last"] == 3
    assert scanned["avg"] == pytest.approx(2.0)
    assert scanned["max"] == pytest.approx(3.0)

    mode = metrics["vision_mode"]
    assert mode["kind"] == "categorical"
    assert mode["observed_samples"] == 2
    assert mode["missing_samples"] == 1
    assert mode["last"] == "dirty_refcount"
    assert mode["values"] == ["dirty_refcount"]
