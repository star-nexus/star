"""Snapshot-only crossing-cost correlation analysis for Phase-4 scale runs.

The profiler already retains aligned per-frame controlled-work, section timings,
and causal frame metrics.  This module consumes those retained samples only when
a scale profile snapshot is requested, so it adds no work to the measured frame
path itself.
"""

from __future__ import annotations

import math
from numbers import Real
from typing import Any, Dict, Iterable, List

FRAME_BUDGET_MS = 16.67
COMMIT_METRIC = "effect_position_index_changes"
VISION_AUDIT_METRIC = "vision_audit_scanned"
MINIMAP_REFRESH_METRIC = "minimap_unit_refreshed"
SECTION_NAMES = (
    "AnimationSystem",
    "VisionSystem",
    "MiniMapSystem",
    "UnitRenderSystem",
    "MapRenderSystem",
)


def _percentile(values: Iterable[float], q: float) -> float:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return 0.0
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * q
    lo = math.floor(rank)
    hi = math.ceil(rank)
    if lo == hi:
        return ordered[lo]
    frac = rank - lo
    return ordered[lo] * (1.0 - frac) + ordered[hi] * frac


def _series_stats(values: List[float]) -> Dict[str, float]:
    if not values:
        return {"avg": 0.0, "p50": 0.0, "p95": 0.0, "p99": 0.0, "max": 0.0}
    return {
        "avg": sum(values) / len(values),
        "p50": _percentile(values, 0.50),
        "p95": _percentile(values, 0.95),
        "p99": _percentile(values, 0.99),
        "max": max(values),
    }


def _linear_fit(xs: List[float], ys: List[float]) -> Dict[str, float | int | None]:
    count = min(len(xs), len(ys))
    if count < 2:
        return {
            "samples": count,
            "slope_ms_per_commit": None,
            "intercept_ms": None,
            "pearson_r": None,
            "r_squared": None,
        }

    xs = xs[:count]
    ys = ys[:count]
    mean_x = sum(xs) / count
    mean_y = sum(ys) / count
    var_x = sum((value - mean_x) ** 2 for value in xs)
    var_y = sum((value - mean_y) ** 2 for value in ys)
    if var_x <= 0.0:
        return {
            "samples": count,
            "slope_ms_per_commit": None,
            "intercept_ms": None,
            "pearson_r": None,
            "r_squared": None,
        }

    covariance = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    slope = covariance / var_x
    intercept = mean_y - slope * mean_x
    if var_y <= 0.0:
        pearson = 0.0
    else:
        pearson = covariance / math.sqrt(var_x * var_y)
    return {
        "samples": count,
        "slope_ms_per_commit": slope,
        "intercept_ms": intercept,
        "pearson_r": pearson,
        "r_squared": pearson * pearson,
    }


def _numeric(value: object) -> float | None:
    if isinstance(value, Real) and not isinstance(value, bool):
        return float(value)
    return None


def _record_summary(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    controlled = [float(record["controlled_ms"]) for record in records]
    commits = [float(record["commits"]) for record in records]
    over_budget = sum(1 for value in controlled if value > FRAME_BUDGET_MS)
    sections: Dict[str, Dict[str, float]] = {}
    for section_name in SECTION_NAMES:
        values = [float(record["sections"].get(section_name, 0.0)) for record in records]
        sections[section_name] = _series_stats(values)

    return {
        "samples": len(records),
        "commit_count": _series_stats(commits),
        "controlled_work_ms": _series_stats(controlled),
        "over_16_67ms": {
            "count": over_budget,
            "rate": (over_budget / len(records)) if records else 0.0,
        },
        "vision_audit_rate": (
            sum(1 for record in records if record["vision_audit"]) / len(records)
            if records
            else 0.0
        ),
        "minimap_refresh_rate": (
            sum(1 for record in records if record["minimap_refresh"]) / len(records)
            if records
            else 0.0
        ),
        "sections_inclusive_ms": sections,
    }


def _fit_targets(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    xs = [float(record["commits"]) for record in records]
    result: Dict[str, Any] = {
        "controlled_work_ms": _linear_fit(
            xs, [float(record["controlled_ms"]) for record in records]
        )
    }
    for section_name in SECTION_NAMES:
        result[section_name] = _linear_fit(
            xs,
            [float(record["sections"].get(section_name, 0.0)) for record in records],
        )
    return result


def _commit_bucket(commit_count: float) -> str:
    if commit_count < 30:
        return "lt_30"
    if commit_count < 40:
        return "30_39"
    if commit_count < 50:
        return "40_49"
    if commit_count < 60:
        return "50_59"
    return "60_plus"


def build_crossing_cost_correlation(profiler) -> Dict[str, Any]:
    """Build aligned crossing-cost diagnostics from the profiler's final window."""

    controlled_ns = list(getattr(profiler, "frame_controlled_ns", ()))
    metric_samples = getattr(profiler, "frame_metric_samples", {})
    commit_samples = list(metric_samples.get(COMMIT_METRIC, ()))
    audit_samples = list(metric_samples.get(VISION_AUDIT_METRIC, ()))
    minimap_samples = list(metric_samples.get(MINIMAP_REFRESH_METRIC, ()))

    if not controlled_ns or not commit_samples:
        return {
            "available": False,
            "reason": "missing_aligned_controlled_or_commit_samples",
            "frame_budget_ms": FRAME_BUDGET_MS,
        }

    sample_count = min(len(controlled_ns), len(commit_samples))
    section_series = {
        name: list(getattr(profiler, "section_inclusive_ns", {}).get(name, ()))
        for name in SECTION_NAMES
    }

    records: List[Dict[str, Any]] = []
    for index in range(sample_count):
        commits = _numeric(commit_samples[index])
        if commits is None:
            continue
        audit_value = _numeric(audit_samples[index]) if index < len(audit_samples) else 0.0
        minimap_value = (
            _numeric(minimap_samples[index]) if index < len(minimap_samples) else 0.0
        )
        sections = {}
        for name, series in section_series.items():
            sections[name] = (
                float(series[index]) / 1_000_000.0 if index < len(series) else 0.0
            )
        records.append(
            {
                "commits": commits,
                "controlled_ms": float(controlled_ns[index]) / 1_000_000.0,
                "vision_audit": bool(audit_value and audit_value > 0.0),
                "minimap_refresh": bool(minimap_value and minimap_value > 0.0),
                "sections": sections,
            }
        )

    buckets: Dict[str, List[Dict[str, Any]]] = {
        "lt_30": [],
        "30_39": [],
        "40_49": [],
        "50_59": [],
        "60_plus": [],
    }
    maintenance: Dict[str, List[Dict[str, Any]]] = {
        "none": [],
        "vision_audit_only": [],
        "minimap_refresh_only": [],
        "vision_audit_and_minimap_refresh": [],
    }
    budget_groups = {"within_16_67ms": [], "over_16_67ms": []}

    for record in records:
        buckets[_commit_bucket(float(record["commits"]))].append(record)
        if record["vision_audit"] and record["minimap_refresh"]:
            maintenance["vision_audit_and_minimap_refresh"].append(record)
        elif record["vision_audit"]:
            maintenance["vision_audit_only"].append(record)
        elif record["minimap_refresh"]:
            maintenance["minimap_refresh_only"].append(record)
        else:
            maintenance["none"].append(record)

        budget_key = (
            "over_16_67ms"
            if float(record["controlled_ms"]) > FRAME_BUDGET_MS
            else "within_16_67ms"
        )
        budget_groups[budget_key].append(record)

    maintenance_off = maintenance["none"]
    return {
        "available": True,
        "analysis_stage": "snapshot_only",
        "runtime_instrumentation_added": False,
        "frame_budget_ms": FRAME_BUDGET_MS,
        "commit_metric": COMMIT_METRIC,
        "maintenance_metrics": {
            "vision_audit": VISION_AUDIT_METRIC,
            "minimap_refresh": MINIMAP_REFRESH_METRIC,
        },
        "sample_count": len(records),
        "all_frames": _record_summary(records),
        "commit_buckets": {
            name: _record_summary(group) for name, group in buckets.items()
        },
        "maintenance_groups": {
            name: _record_summary(group) for name, group in maintenance.items()
        },
        "budget_groups": {
            name: _record_summary(group) for name, group in budget_groups.items()
        },
        "linear_fit": {
            "all_frames": _fit_targets(records),
            "maintenance_off_only": _fit_targets(maintenance_off),
        },
    }
