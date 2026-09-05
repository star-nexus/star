from collections import deque
from types import SimpleNamespace

from rotk_env.testing.crossing_cost_correlation import build_crossing_cost_correlation


def _ns_ms(*values):
    return deque(int(value * 1_000_000) for value in values)


def test_crossing_cost_correlation_aligns_commits_budget_and_maintenance_groups():
    profiler = SimpleNamespace(
        frame_controlled_ns=_ns_ms(10.0, 12.0, 17.0, 18.0, 19.0),
        frame_metric_samples={
            "effect_position_index_changes": deque([20, 35, 45, 55, 65]),
            "vision_audit_scanned": deque([0, 0, 5000, 0, 0]),
            "minimap_unit_refreshed": deque([0, 1, 0, 0, 1]),
        },
        section_inclusive_ns={
            "AnimationSystem": _ns_ms(1.0, 1.2, 1.4, 1.6, 1.8),
            "VisionSystem": _ns_ms(0.2, 0.3, 2.2, 0.5, 0.6),
            "MiniMapSystem": _ns_ms(0.1, 4.0, 0.1, 0.1, 4.2),
            "UnitRenderSystem": _ns_ms(4.0, 4.1, 4.2, 4.3, 4.4),
            "MapRenderSystem": _ns_ms(2.0, 2.0, 2.1, 2.1, 2.2),
        },
    )

    report = build_crossing_cost_correlation(profiler)

    assert report["available"] is True
    assert report["runtime_instrumentation_added"] is False
    assert report["sample_count"] == 5
    assert report["commit_buckets"]["lt_30"]["samples"] == 1
    assert report["commit_buckets"]["30_39"]["samples"] == 1
    assert report["commit_buckets"]["40_49"]["samples"] == 1
    assert report["commit_buckets"]["50_59"]["samples"] == 1
    assert report["commit_buckets"]["60_plus"]["samples"] == 1

    assert report["budget_groups"]["within_16_67ms"]["samples"] == 2
    assert report["budget_groups"]["over_16_67ms"]["samples"] == 3
    assert report["maintenance_groups"]["none"]["samples"] == 2
    assert report["maintenance_groups"]["vision_audit_only"]["samples"] == 1
    assert report["maintenance_groups"]["minimap_refresh_only"]["samples"] == 2
    assert report["maintenance_groups"]["vision_audit_and_minimap_refresh"]["samples"] == 0

    fit = report["linear_fit"]["all_frames"]["controlled_work_ms"]
    assert fit["samples"] == 5
    assert fit["slope_ms_per_commit"] > 0.0
    assert fit["pearson_r"] > 0.0


def test_crossing_cost_correlation_reports_missing_commit_series_cleanly():
    profiler = SimpleNamespace(
        frame_controlled_ns=_ns_ms(10.0),
        frame_metric_samples={},
        section_inclusive_ns={},
    )

    report = build_crossing_cost_correlation(profiler)

    assert report["available"] is False
    assert report["reason"] == "missing_aligned_controlled_or_commit_samples"
