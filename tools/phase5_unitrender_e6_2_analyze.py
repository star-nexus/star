#!/usr/bin/env python3
"""Analyze Phase-5 UnitRender E6-2 slotted-record composition attribution."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

BASE_SHA = "e7ba18b31870577110b591104ef8fa7b4713e43c"
RATE_TOLERANCE_PCT = 2.0
MIN_CULL_SAVING_MS_50 = 0.05
MIN_CULL_SAVING_MS_100 = 0.07
MAX_UNITRENDER_AVG_REGRESSION_PCT = 1.0
MAX_CONTROLLED_AVG_REGRESSION_PCT = 1.0
MAX_ANIMATION_AVG_REGRESSION_PCT = 2.0
CANONICAL_30HZ_P99_MS = 33.33


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _pct_delta(new: float, old: float) -> float:
    if old == 0:
        return math.inf if new != 0 else 0.0
    return (new - old) / old * 100.0


def _metric_avg(profile: dict[str, Any], name: str) -> float:
    metric = profile.get("frame_metrics", {}).get(name)
    if not isinstance(metric, dict) or not isinstance(metric.get("avg"), (int, float)):
        raise KeyError(f"missing frame metric avg: {name}")
    return float(metric["avg"])


def _section(profile: dict[str, Any], name: str) -> dict[str, float]:
    section = profile.get("sections", {}).get(name)
    if not isinstance(section, dict) or not isinstance(section.get("inclusive_ms"), (int, float)):
        raise KeyError(f"missing section inclusive_ms: {name}")
    result = {"avg": float(section["inclusive_ms"])}
    for key, out in (
        ("p95_inclusive_ms", "p95"),
        ("p99_inclusive_ms", "p99"),
        ("max_inclusive_ms", "max"),
    ):
        if isinstance(section.get(key), (int, float)):
            result[out] = float(section[key])
    return result


def _point(run_dir: Path, variant: str, density: str) -> dict[str, Any]:
    point_dir = run_dir / variant / f"{density}pct-moving"
    raw = _load(point_dir / "point.json")
    profile = _load(point_dir / "profile.json")
    controlled = profile.get("controlled_work_frame_ms")
    if not isinstance(controlled, dict):
        raise KeyError("missing controlled_work_frame_ms")
    throughput = float(profile.get("window_throughput_fps") or 0.0)
    if throughput <= 0:
        raise KeyError("missing/invalid window_throughput_fps")
    guards = raw.get("guards", {})
    return {
        "guards_ok": isinstance(guards, dict) and bool(guards) and all(bool(v) for v in guards.values()),
        "metadata": profile.get("metadata", {}),
        "controlled": {
            key: float(controlled[key])
            for key in ("avg", "p50", "p95", "p99", "max")
            if isinstance(controlled.get(key), (int, float))
        },
        "throughput_fps": throughput,
        "cull": _section(profile, "unit_visible_cull"),
        "unitrender": _section(profile, "UnitRenderSystem"),
        "animation": _section(profile, "AnimationSystem"),
        "position_commits_per_s": _metric_avg(profile, "effect_position_index_changes") * throughput,
        "vision_changed_per_s": _metric_avg(profile, "vision_units_changed") * throughput,
        "fog_delta_per_s": _metric_avg(profile, "vision_fog_delta_tiles") * throughput,
    }


def _compare(control: dict[str, Any], treatment: dict[str, Any], density: str) -> dict[str, Any]:
    def rate_delta(key: str) -> float:
        return _pct_delta(treatment[key], control[key])

    cull_saving = control["cull"]["avg"] - treatment["cull"]["avg"]
    unitrender_pct = _pct_delta(treatment["unitrender"]["avg"], control["unitrender"]["avg"])
    controlled_pct = _pct_delta(treatment["controlled"]["avg"], control["controlled"]["avg"])
    animation_pct = _pct_delta(treatment["animation"]["avg"], control["animation"]["avg"])
    min_cull = MIN_CULL_SAVING_MS_50 if density == "50" else MIN_CULL_SAVING_MS_100

    control_meta = control["metadata"]
    treatment_meta = treatment["metadata"]
    checks = {
        "guards_ok": control["guards_ok"] and treatment["guards_ok"],
        "control_is_plain_e6_1": not bool(control_meta.get("phase5_unitrender_e6_2_attribution")),
        "treatment_contract": (
            treatment_meta.get("phase5_unitrender_e6_2_attribution") is True
            and treatment_meta.get("phase5_unitrender_e6_2_runtime_sha") == BASE_SHA
            and treatment_meta.get("phase5_unitrender_e6_2_e6_1_geometry_ownership_preserved") is True
            and treatment_meta.get("phase5_unitrender_e6_2_fresh_record_identity_preserved") is True
            and treatment_meta.get("phase5_unitrender_e6_2_cull_algorithm_unchanged") is True
        ),
        "position_rate_preserved": abs(rate_delta("position_commits_per_s")) <= RATE_TOLERANCE_PCT,
        "vision_changed_rate_preserved": abs(rate_delta("vision_changed_per_s")) <= RATE_TOLERANCE_PCT,
        "fog_delta_rate_preserved": abs(rate_delta("fog_delta_per_s")) <= RATE_TOLERANCE_PCT,
        "cull_saving_meets_floor": cull_saving >= min_cull,
        "unitrender_avg_no_material_regression": unitrender_pct <= MAX_UNITRENDER_AVG_REGRESSION_PCT,
        "controlled_avg_no_material_regression": controlled_pct <= MAX_CONTROLLED_AVG_REGRESSION_PCT,
        "animation_avg_no_material_regression": animation_pct <= MAX_ANIMATION_AVG_REGRESSION_PCT,
    }
    return {
        "control": control,
        "treatment": treatment,
        "deltas": {
            "controlled_avg_ms": treatment["controlled"]["avg"] - control["controlled"]["avg"],
            "controlled_avg_pct": controlled_pct,
            "controlled_p99_ms": treatment["controlled"].get("p99", math.nan) - control["controlled"].get("p99", math.nan),
            "cull_saving_ms": cull_saving,
            "cull_p95_saving_ms": control["cull"].get("p95", math.nan) - treatment["cull"].get("p95", math.nan),
            "unitrender_avg_ms": treatment["unitrender"]["avg"] - control["unitrender"]["avg"],
            "unitrender_avg_pct": unitrender_pct,
            "animation_avg_ms": treatment["animation"]["avg"] - control["animation"]["avg"],
            "animation_avg_pct": animation_pct,
            "position_rate_pct": rate_delta("position_commits_per_s"),
            "vision_changed_rate_pct": rate_delta("vision_changed_per_s"),
            "fog_delta_rate_pct": rate_delta("fog_delta_per_s"),
        },
        "checks": checks,
        "pass": all(checks.values()),
    }


def analyze(run_dir: Path) -> dict[str, Any]:
    comparisons = {
        "50pct-moving": _compare(
            _point(run_dir, "control", "50"),
            _point(run_dir, "treatment", "50"),
            "50",
        ),
        "100pct-moving": _compare(
            _point(run_dir, "control", "100"),
            _point(run_dir, "treatment", "100"),
            "100",
        ),
    }
    passed = all(item["pass"] for item in comparisons.values())
    p99 = comparisons["100pct-moving"]["treatment"]["controlled"].get("p99", math.inf)
    canonical_pass = p99 <= CANONICAL_30HZ_P99_MS
    return {
        "experiment": "Phase 5 UnitRender E6-2 E6-1 plus slotted spatial-record composition",
        "decision": (
            "SLOTTED_RECORD_COMPOSITION_CANDIDATE_JUSTIFIED"
            if passed
            else "SLOTTED_RECORD_COMPOSITION_NOT_MATERIAL"
        ),
        "criteria": {
            "retained_e6_1_base_sha": BASE_SHA,
            "prior_e5_1_cull_saving_ms_50": 0.090,
            "prior_e5_1_cull_saving_ms_100": 0.113,
            "rate_tolerance_pct": RATE_TOLERANCE_PCT,
            "min_cull_saving_ms_50": MIN_CULL_SAVING_MS_50,
            "min_cull_saving_ms_100": MIN_CULL_SAVING_MS_100,
            "max_unitrender_avg_regression_pct": MAX_UNITRENDER_AVG_REGRESSION_PCT,
            "max_controlled_avg_regression_pct": MAX_CONTROLLED_AVG_REGRESSION_PCT,
            "max_animation_avg_regression_pct": MAX_ANIMATION_AVG_REGRESSION_PCT,
            "positive_is_not_production_keep": True,
            "canonical_30hz_p99_ms": CANONICAL_30HZ_P99_MS,
        },
        "comparisons": comparisons,
        "canonical_30hz_100pct": {
            "controlled_p99_ms": p99,
            "gate_ms": CANONICAL_30HZ_P99_MS,
            "pass": canonical_pass,
        },
        "production_candidate_next": bool(passed),
        "frontier_update_candidate": False,
    }


def _print(result: dict[str, Any]) -> None:
    print("\nPhase 5 UnitRender E6-2 — E6-1 + slotted-record composition")
    print("=" * 96)
    for label in ("50pct-moving", "100pct-moving"):
        item = result["comparisons"][label]
        a, b, d = item["control"], item["treatment"], item["deltas"]
        print(f"{label}:")
        print(f"  controlled avg: {a['controlled']['avg']:.3f} -> {b['controlled']['avg']:.3f} ms ({d['controlled_avg_pct']:+.2f}%)")
        print(f"  controlled p99: {a['controlled'].get('p99', math.nan):.3f} -> {b['controlled'].get('p99', math.nan):.3f} ms")
        print(f"  Cull avg:       {a['cull']['avg']:.3f} -> {b['cull']['avg']:.3f} ms  saving={d['cull_saving_ms']:.3f}")
        print(f"  Cull p95 save:  {d['cull_p95_saving_ms']:.3f} ms")
        print(f"  UnitRender avg: {a['unitrender']['avg']:.3f} -> {b['unitrender']['avg']:.3f} ms ({d['unitrender_avg_pct']:+.2f}%)")
        print(f"  Animation avg:  {a['animation']['avg']:.3f} -> {b['animation']['avg']:.3f} ms ({d['animation_avg_pct']:+.2f}%)")
        print(f"  position rate:  {d['position_rate_pct']:+.3f}%")
        print(f"  vision changed: {d['vision_changed_rate_pct']:+.3f}%")
        print(f"  fog delta:      {d['fog_delta_rate_pct']:+.3f}%")
        failed = [name for name, ok in item["checks"].items() if not ok]
        print(f"  checks:         {'PASS' if item['pass'] else 'FAIL'}" + (f" ({', '.join(failed)})" if failed else ""))
    gate = result["canonical_30hz_100pct"]
    op = "<=" if gate["pass"] else ">"
    print("-" * 96)
    print(f"DECISION: {result['decision']}")
    print(f"30Hz diagnostic @100%: {'PASS' if gate['pass'] else 'FAIL'} ({gate['controlled_p99_ms']:.3f} ms {op} {gate['gate_ms']:.2f} ms)")
    print(f"PRODUCTION CANDIDATE NEXT: {result['production_candidate_next']}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    args = parser.parse_args()
    result = analyze(args.run_dir)
    (args.run_dir / "unitrender-e6-2-summary.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    _print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
