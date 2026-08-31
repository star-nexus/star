from __future__ import annotations

import json

import pytest

import performance_profiler as profiler_module
from performance_profiler import PerformanceProfiler


def _clock(monkeypatch, values_ns):
    values = iter(values_ns)
    monkeypatch.setattr(profiler_module.time, "perf_counter_ns", lambda: next(values))


def test_nested_timers_report_exclusive_time_without_double_count(monkeypatch):
    # Frame: 16ms total.
    # outer: 1..8 = 7ms inclusive, containing inner 3..5 = 2ms,
    # therefore outer self = 5ms. present = 8..12 = 4ms.
    _clock(
        monkeypatch,
        [
            0,
            1_000_000,
            3_000_000,
            5_000_000,
            8_000_000,
            8_000_000,
            12_000_000,
            16_000_000,
        ],
    )
    profiler = PerformanceProfiler(sample_window=10)

    profiler.start_frame()
    with profiler.time_system("outer", category="update"):
        with profiler.time_system("inner"):
            pass
    with profiler.time_system("display_present", category="present"):
        pass
    profiler.end_frame()

    stats = profiler.get_stats()
    assert stats["avg_frame_ms"] == pytest.approx(16.0)
    assert stats["sections"]["outer"]["inclusive_ms"] == pytest.approx(7.0)
    assert stats["sections"]["outer"]["self_ms"] == pytest.approx(5.0)
    assert stats["sections"]["inner"]["self_ms"] == pytest.approx(2.0)
    assert stats["present_ms"] == pytest.approx(4.0)
    assert stats["uninstrumented_ms"] == pytest.approx(5.0)

    # Exclusive shares are a real frame breakdown rather than nested inclusive
    # percentages that can exceed 100%.
    share = sum(section["frame_share_pct"] for section in stats["sections"].values())
    assert share == pytest.approx(68.75)
    assert share <= 100.0


def test_sections_are_averaged_per_frame_including_zero_frames(monkeypatch):
    # Frame 1 is 10ms and contains 4ms of work. Frame 2 is also 10ms but the
    # section does not execute. The rolling per-frame average must be 2ms,
    # rather than the old profiler's occurrence-only 4ms average.
    _clock(
        monkeypatch,
        [0, 1_000_000, 5_000_000, 10_000_000, 10_000_000, 20_000_000],
    )
    profiler = PerformanceProfiler(sample_window=10)

    profiler.start_frame()
    with profiler.time_system("sometimes"):
        pass
    profiler.end_frame()

    profiler.start_frame()
    profiler.end_frame()

    stats = profiler.get_stats()
    assert stats["sample_count"] == 2
    assert stats["avg_frame_ms"] == pytest.approx(10.0)
    assert stats["sections"]["sometimes"]["self_ms"] == pytest.approx(2.0)
    assert stats["sections"]["sometimes"]["frame_share_pct"] == pytest.approx(20.0)


def test_wait_and_present_are_separated_from_active_budget(monkeypatch):
    _clock(
        monkeypatch,
        [
            0,
            0,
            4_000_000,      # active work = 4ms
            4_000_000,
            10_000_000,     # present = 6ms
            10_000_000,
            16_000_000,     # fps limiter = 6ms
            16_000_000,
        ],
    )
    profiler = PerformanceProfiler(sample_window=10)

    profiler.start_frame()
    with profiler.time_system("scene_update", category="update"):
        pass
    with profiler.time_system("display_present", category="present"):
        pass
    with profiler.time_system("fps_limiter_wait", category="wait"):
        pass
    profiler.end_frame()

    stats = profiler.get_stats()
    assert stats["avg_frame_ms"] == pytest.approx(16.0)
    assert stats["active_ms"] == pytest.approx(4.0)
    assert stats["present_ms"] == pytest.approx(6.0)
    assert stats["fps_limiter_wait_ms"] == pytest.approx(6.0)


def test_json_snapshot_is_serializable(monkeypatch, tmp_path):
    _clock(monkeypatch, [0, 10_000_000])
    profiler = PerformanceProfiler(sample_window=10)
    profiler.set_metadata(scenario="chibi", units=20)
    profiler.start_frame()
    profiler.end_frame()

    output = tmp_path / "profile.json"
    profiler.write_json(output)
    data = json.loads(output.read_text(encoding="utf-8"))

    assert data["metadata"]["scenario"] == "chibi"
    assert data["metadata"]["units"] == 20
    assert data["avg_frame_ms"] == pytest.approx(10.0)
