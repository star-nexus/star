#!/usr/bin/env python3
"""Phase-5 E7 aligned P99-tail composition attribution launcher.

Runs exact retained E6-1 production and changes no gameplay/runtime semantics.
The experiment only extends the profiler rolling window and augments get_stats()
at snapshot time using the profiler's already-aligned per-frame deques.
"""
from __future__ import annotations

import math
import statistics
import subprocess
import sys
from numbers import Real
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

EXPECTED_RUNTIME_SHA = "e7ba18b31870577110b591104ef8fa7b4713e43c"
EXPECTED_PROFILER_BLOB = "005ebafce310b6015c0971b54dc060b82bdf6351"
TAIL_WINDOW_SECONDS = 10.0
CANONICAL_GATE_MS = 33.33


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return math.nan
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    pos = (len(ordered) - 1) * q
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return ordered[lo]
    frac = pos - lo
    return ordered[lo] * (1.0 - frac) + ordered[hi] * frac


def _mean_at(values: list[float], indices: list[int]) -> float:
    if not indices:
        return math.nan
    return statistics.fmean(values[i] for i in indices)


def _pearson(xs: list[float], ys: list[float]) -> float:
    if len(xs) != len(ys) or len(xs) < 3:
        return math.nan
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    dx = [x - mx for x in xs]
    dy = [y - my for y in ys]
    vx = sum(x * x for x in dx)
    vy = sum(y * y for y in dy)
    if vx <= 0.0 or vy <= 0.0:
        return 0.0
    return sum(x * y for x, y in zip(dx, dy)) / math.sqrt(vx * vy)


def _numeric(value: object) -> bool:
    return isinstance(value, Real) and not isinstance(value, bool)


def _ms_series(series: Any, n: int) -> list[float] | None:
    values = list(series)
    if len(values) != n:
        return None
    return [float(v) / 1_000_000.0 for v in values]


def build_tail_snapshot(profiler: Any) -> dict[str, Any]:
    controlled = _ms_series(profiler.frame_controlled_ns, len(profiler.frame_controlled_ns))
    if not controlled:
        return {"schema": "phase5-tail-composition-v1", "ok": False, "reason": "no frames"}
    n = len(controlled)
    q25 = _percentile(controlled, 0.25)
    q50 = _percentile(controlled, 0.50)
    q75 = _percentile(controlled, 0.75)
    q95 = _percentile(controlled, 0.95)
    q99 = _percentile(controlled, 0.99)
    tail_idx = [i for i, value in enumerate(controlled) if value >= q95]
    ref_idx = [i for i, value in enumerate(controlled) if q25 <= value <= q75]
    breach_idx = [i for i, value in enumerate(controlled) if value > CANONICAL_GATE_MS]
    tail_mean = _mean_at(controlled, tail_idx)
    ref_mean = _mean_at(controlled, ref_idx)
    controlled_uplift = tail_mean - ref_mean

    section_rows: list[dict[str, Any]] = []
    section_values: dict[str, list[float]] = {}
    section_p90: dict[str, float] = {}
    names = sorted(set(profiler.section_self_ns) | set(profiler.section_inclusive_ns))
    for name in names:
        category = profiler.section_categories.get(name, "work")
        if category not in {"work", "update", "render", "vision", "input"}:
            continue
        self_values = _ms_series(profiler.section_self_ns.get(name, ()), n)
        inclusive_values = _ms_series(profiler.section_inclusive_ns.get(name, ()), n)
        if self_values is None or inclusive_values is None:
            continue
        section_values[name] = self_values
        own_p90 = _percentile(self_values, 0.90)
        section_p90[name] = own_p90
        self_tail = _mean_at(self_values, tail_idx)
        self_ref = _mean_at(self_values, ref_idx)
        uplift = self_tail - self_ref
        inclusive_tail = _mean_at(inclusive_values, tail_idx)
        inclusive_ref = _mean_at(inclusive_values, ref_idx)
        high_tail_count = sum(1 for i in tail_idx if self_values[i] >= own_p90)
        row = {
            "name": name,
            "category": category,
            "self_overall_mean_ms": statistics.fmean(self_values),
            "self_reference_mean_ms": self_ref,
            "self_tail_mean_ms": self_tail,
            "self_tail_uplift_ms": uplift,
            "self_tail_uplift_share_pct": (100.0 * uplift / controlled_uplift) if controlled_uplift > 0 else math.nan,
            "self_pearson_r_controlled": _pearson(self_values, controlled),
            "self_p90_ms": own_p90,
            "self_p90_fraction_inside_tail": high_tail_count / len(tail_idx) if tail_idx else 0.0,
            "inclusive_reference_mean_ms": inclusive_ref,
            "inclusive_tail_mean_ms": inclusive_tail,
            "inclusive_tail_uplift_ms": inclusive_tail - inclusive_ref,
        }
        section_rows.append(row)
    section_rows.sort(key=lambda row: row["self_tail_uplift_ms"], reverse=True)

    metric_rows: list[dict[str, Any]] = []
    metric_values_by_name: dict[str, list[object | None]] = {}
    for name, series in profiler.frame_metric_samples.items():
        values = list(series)
        if len(values) != n:
            continue
        pairs = [(i, float(value)) for i, value in enumerate(values) if _numeric(value)]
        if len(pairs) < max(10, n // 2):
            continue
        indices = [i for i, _ in pairs]
        numeric_values = [value for _, value in pairs]
        controlled_pairs = [controlled[i] for i in indices]
        if max(numeric_values) == min(numeric_values):
            continue
        tail_values = [float(values[i]) for i in tail_idx if _numeric(values[i])]
        ref_values = [float(values[i]) for i in ref_idx if _numeric(values[i])]
        if not tail_values or not ref_values:
            continue
        tail_metric = statistics.fmean(tail_values)
        ref_metric = statistics.fmean(ref_values)
        metric_values_by_name[name] = values
        metric_rows.append({
            "name": name,
            "observed_samples": len(pairs),
            "reference_mean": ref_metric,
            "tail_mean": tail_metric,
            "tail_delta": tail_metric - ref_metric,
            "tail_ratio": (tail_metric / ref_metric) if ref_metric != 0 else None,
            "pearson_r_controlled": _pearson(numeric_values, controlled_pairs),
        })
    metric_rows.sort(key=lambda row: abs(row["pearson_r_controlled"]), reverse=True)
    metric_rows = metric_rows[:16]

    top_positive = [row["name"] for row in section_rows if row["self_tail_uplift_ms"] > 0][:8]
    pairs: list[dict[str, Any]] = []
    for ai, a in enumerate(top_positive):
        for b in top_positive[ai + 1:]:
            count = sum(
                1 for i in tail_idx
                if section_values[a][i] >= section_p90[a] and section_values[b][i] >= section_p90[b]
            )
            pairs.append({
                "a": a,
                "b": b,
                "count_inside_tail": count,
                "fraction_inside_tail": count / len(tail_idx) if tail_idx else 0.0,
            })
    pairs.sort(key=lambda row: row["fraction_inside_tail"], reverse=True)

    selected_metric_names = [row["name"] for row in metric_rows[:8]]
    breach_frames = []
    for i in sorted(breach_idx, key=lambda idx: controlled[idx], reverse=True)[:20]:
        frame_sections = sorted(
            ({"name": name, "self_ms": values[i]} for name, values in section_values.items()),
            key=lambda item: item["self_ms"], reverse=True,
        )[:10]
        frame_metrics = {
            name: metric_values_by_name[name][i]
            for name in selected_metric_names
            if name in metric_values_by_name and _numeric(metric_values_by_name[name][i])
        }
        breach_frames.append({
            "window_frame_index": i,
            "controlled_ms": controlled[i],
            "top_section_self_ms": frame_sections,
            "selected_numeric_metrics": frame_metrics,
        })

    return {
        "schema": "phase5-tail-composition-v1",
        "ok": True,
        "method": {
            "tail_set": "controlled_work >= per-run p95",
            "reference_set": "per-run p25 <= controlled_work <= p75",
            "contribution_basis": "controlled-category section self time; no inclusive double counting",
            "canonical_breach_ms": CANONICAL_GATE_MS,
        },
        "sample_count": n,
        "controlled_ms": {
            "mean": statistics.fmean(controlled),
            "p25": q25,
            "p50": q50,
            "p75": q75,
            "p95": q95,
            "p99": q99,
            "max": max(controlled),
            "reference_frame_count": len(ref_idx),
            "tail_frame_count": len(tail_idx),
            "canonical_breach_frame_count": len(breach_idx),
            "reference_mean": ref_mean,
            "tail_mean": tail_mean,
            "tail_uplift": controlled_uplift,
        },
        "section_self_contributors": section_rows,
        "numeric_metric_associations": metric_rows,
        "section_p90_cooccurrence_inside_tail": pairs[:20],
        "canonical_breach_frames": breach_frames,
    }


def _verify_source() -> None:
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=_REPO_ROOT, text=True).strip()
    if sha != EXPECTED_RUNTIME_SHA:
        raise RuntimeError(f"E7 requires exact retained production {EXPECTED_RUNTIME_SHA}, got {sha}")
    blob = subprocess.check_output(["git", "hash-object", "performance_profiler.py"], cwd=_REPO_ROOT, text=True).strip()
    if blob != EXPECTED_PROFILER_BLOB:
        raise RuntimeError(f"performance_profiler.py drift: expected {EXPECTED_PROFILER_BLOB}, got {blob}")


def _install() -> None:
    _verify_source()
    import performance_profiler as perf

    original = perf.PerformanceProfiler.get_stats
    if getattr(original, "_phase5_e7_wrapped", False):
        return

    def wrapped(self):
        stats = original(self)
        stats["tail_attribution"] = build_tail_snapshot(self)
        return stats

    wrapped._phase5_e7_wrapped = True
    perf.PerformanceProfiler.get_stats = wrapped
    perf.profiler.sample_window_seconds = TAIL_WINDOW_SECONDS
    perf.profiler.set_metadata(
        phase5_e7_tail_composition=True,
        phase5_e7_runtime_sha=EXPECTED_RUNTIME_SHA,
        phase5_e7_sample_window_seconds=TAIL_WINDOW_SECONDS,
        phase5_e7_attribution_only=True,
        phase5_e7_production_semantics_unchanged=True,
    )

    import rotk_env.main as env_main
    env_main.main()


def main() -> int:
    _install()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
