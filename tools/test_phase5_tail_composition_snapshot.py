#!/usr/bin/env python3
from collections import deque
from types import SimpleNamespace

from tools.phase5_tail_composition_snapshot import build_tail_snapshot


def _ns(values_ms):
    return deque(int(v * 1_000_000) for v in values_ms)


def test_tail_snapshot_uses_self_time_and_finds_stable_uplift():
    n = 100
    controlled = [30.0] * 90 + [35.0] * 10
    unit_self = [8.0] * 90 + [9.0] * 10
    animation = [7.0] * 90 + [9.0] * 10
    vision = [3.0] * n
    # Parent inclusive deliberately overlaps a child-like cost. Attribution share
    # must still come from self series only.
    unit_inclusive = [10.0] * 90 + [12.0] * 10
    pulse = [0.0] * 90 + [10.0] * 10

    profiler = SimpleNamespace(
        frame_controlled_ns=_ns(controlled),
        section_self_ns={
            "UnitRenderSystem": _ns(unit_self),
            "AnimationSystem": _ns(animation),
            "VisionSystem": _ns(vision),
        },
        section_inclusive_ns={
            "UnitRenderSystem": _ns(unit_inclusive),
            "AnimationSystem": _ns(animation),
            "VisionSystem": _ns(vision),
        },
        section_categories={
            "UnitRenderSystem": "work",
            "AnimationSystem": "work",
            "VisionSystem": "vision",
        },
        frame_metric_samples={"synthetic_pulse": deque(pulse)},
    )

    result = build_tail_snapshot(profiler)
    assert result["ok"] is True
    assert result["sample_count"] == 100
    assert result["controlled_ms"]["tail_frame_count"] == 10
    assert result["controlled_ms"]["canonical_breach_frame_count"] == 10

    rows = {row["name"]: row for row in result["section_self_contributors"]}
    assert rows["AnimationSystem"]["self_tail_uplift_ms"] == 2.0
    assert rows["UnitRenderSystem"]["self_tail_uplift_ms"] == 1.0
    assert rows["VisionSystem"]["self_tail_uplift_ms"] == 0.0
    assert rows["UnitRenderSystem"]["inclusive_tail_uplift_ms"] == 2.0
    # Self share must be 1/5, not the overlapping inclusive 2/5.
    assert rows["UnitRenderSystem"]["self_tail_uplift_share_pct"] == 20.0

    metrics = {row["name"]: row for row in result["numeric_metric_associations"]}
    assert metrics["synthetic_pulse"]["pearson_r_controlled"] > 0.99
    assert result["canonical_breach_frames"]


def test_constant_numeric_metrics_are_excluded():
    n = 100
    controlled = [30.0] * 90 + [35.0] * 10
    profiler = SimpleNamespace(
        frame_controlled_ns=_ns(controlled),
        section_self_ns={"AnimationSystem": _ns([7.0] * 90 + [8.0] * 10)},
        section_inclusive_ns={"AnimationSystem": _ns([7.0] * 90 + [8.0] * 10)},
        section_categories={"AnimationSystem": "work"},
        frame_metric_samples={"constant": deque([1.0] * n)},
    )
    result = build_tail_snapshot(profiler)
    assert [row["name"] for row in result["numeric_metric_associations"]] == []
