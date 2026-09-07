#!/usr/bin/env python3
"""Aggregate three Phase-5 E7 100%-moving tail-composition repeats."""
from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import Counter
from pathlib import Path
from typing import Any

EXPECTED_RUNTIME_SHA = "e7ba18b31870577110b591104ef8fa7b4713e43c"
CANONICAL_GATE_MS = 33.33
MIN_STABLE_TOP3_REPEATS = 2
MIN_ACTIONABLE_MEDIAN_UPLIFT_MS = 0.15


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _median(values):
    vals = [float(v) for v in values if isinstance(v, (int, float)) and math.isfinite(float(v))]
    return statistics.median(vals) if vals else math.nan


def analyze(run_dir: Path) -> dict[str, Any]:
    source = _load(run_dir / "source-guards.json")
    source_ok = source.get("pass") is True and source.get("runtime_sha") == EXPECTED_RUNTIME_SHA
    repeats = []
    top3_frequency: Counter[str] = Counter()
    metric_top_frequency: Counter[str] = Counter()
    pair_frequency: Counter[tuple[str, str]] = Counter()

    for repeat in (1, 2, 3):
        point = _load(run_dir / f"repeat-{repeat}" / "point.json")
        profile = _load(run_dir / f"repeat-{repeat}" / "profile.json")
        tail = profile.get("tail_attribution")
        if not isinstance(tail, dict) or tail.get("ok") is not True:
            raise RuntimeError(f"repeat-{repeat}: missing/invalid tail_attribution")
        guards = point.get("guards", {})
        guards_ok = isinstance(guards, dict) and bool(guards) and all(bool(v) for v in guards.values())
        contributors = tail.get("section_self_contributors", [])
        positive_top3 = [
            row["name"] for row in contributors
            if float(row.get("self_tail_uplift_ms", 0.0)) > 0.0
        ][:3]
        top3_frequency.update(positive_top3)
        metric_rows = tail.get("numeric_metric_associations", [])
        metric_top_frequency.update(row["name"] for row in metric_rows[:5])
        pair_rows = tail.get("section_p90_cooccurrence_inside_tail", [])
        for row in pair_rows[:5]:
            pair_frequency[(row["a"], row["b"])] += 1
        controlled = tail["controlled_ms"]
        repeats.append({
            "repeat": repeat,
            "guards_ok": guards_ok,
            "sample_count": tail.get("sample_count"),
            "controlled_avg_ms": controlled.get("mean"),
            "controlled_p95_ms": controlled.get("p95"),
            "controlled_p99_ms": controlled.get("p99"),
            "controlled_max_ms": controlled.get("max"),
            "controlled_tail_uplift_ms": controlled.get("tail_uplift"),
            "canonical_breach_frames": controlled.get("canonical_breach_frame_count"),
            "positive_top3": positive_top3,
            "contributors": contributors,
            "metrics": metric_rows,
            "pairs": pair_rows,
        })

    all_guards = source_ok and all(r["guards_ok"] for r in repeats)
    names = sorted({row["name"] for r in repeats for row in r["contributors"]})
    stable = []
    for name in names:
        rows = [
            next((row for row in r["contributors"] if row["name"] == name), None)
            for r in repeats
        ]
        rows = [row for row in rows if row is not None]
        stable.append({
            "name": name,
            "top3_repeat_count": top3_frequency[name],
            "median_self_tail_uplift_ms": _median([row.get("self_tail_uplift_ms") for row in rows]),
            "median_self_tail_uplift_share_pct": _median([row.get("self_tail_uplift_share_pct") for row in rows]),
            "median_pearson_r_controlled": _median([row.get("self_pearson_r_controlled") for row in rows]),
            "median_tail_p90_fraction": _median([row.get("self_p90_fraction_inside_tail") for row in rows]),
        })
    stable.sort(key=lambda row: row["median_self_tail_uplift_ms"], reverse=True)
    actionable = [
        row for row in stable
        if row["top3_repeat_count"] >= MIN_STABLE_TOP3_REPEATS
        and row["median_self_tail_uplift_ms"] >= MIN_ACTIONABLE_MEDIAN_UPLIFT_MS
    ]

    metric_names = sorted({row["name"] for r in repeats for row in r["metrics"]})
    stable_metrics = []
    for name in metric_names:
        rows = [next((row for row in r["metrics"] if row["name"] == name), None) for r in repeats]
        rows = [row for row in rows if row is not None]
        stable_metrics.append({
            "name": name,
            "top5_repeat_count": metric_top_frequency[name],
            "median_pearson_r_controlled": _median([row.get("pearson_r_controlled") for row in rows]),
            "median_tail_delta": _median([row.get("tail_delta") for row in rows]),
            "median_tail_ratio": _median([row.get("tail_ratio") for row in rows]),
        })
    stable_metrics.sort(key=lambda row: abs(row["median_pearson_r_controlled"]), reverse=True)

    stable_pairs = [
        {"a": a, "b": b, "top5_repeat_count": count}
        for (a, b), count in pair_frequency.items() if count >= 2
    ]
    stable_pairs.sort(key=lambda row: row["top5_repeat_count"], reverse=True)

    decision = "STABLE_TAIL_CONTRIBUTORS_FOUND" if actionable else "NO_ACTIONABLE_STABLE_TAIL_CONTRIBUTOR"
    p99_values = [float(r["controlled_p99_ms"]) for r in repeats]
    result = {
        "experiment": "Phase 5 E7 100% moving P99 tail composition attribution",
        "source_guards": source,
        "all_guards_pass": all_guards,
        "method": {
            "repeats": 3,
            "tail_set": "per-run controlled_work >= p95",
            "reference_set": "per-run p25-p75 controlled_work",
            "contribution_basis": "controlled-category section self time",
            "stable_top3_repeats_required": MIN_STABLE_TOP3_REPEATS,
            "actionable_median_tail_uplift_ms": MIN_ACTIONABLE_MEDIAN_UPLIFT_MS,
            "p99_is_diagnostic_not_primary_attribution_set": True,
        },
        "repeats": repeats,
        "stable_section_contributors": stable,
        "actionable_stable_contributors": actionable,
        "stable_numeric_metric_associations": stable_metrics,
        "stable_section_cooccurrence_pairs": stable_pairs,
        "decision": decision if all_guards else "INVALID_GUARDS",
        "next_causal_target": actionable[0]["name"] if actionable and all_guards else None,
        "canonical_30hz_diagnostic": {
            "gate_ms": CANONICAL_GATE_MS,
            "repeat_p99_ms": p99_values,
            "median_p99_ms": statistics.median(p99_values),
            "pass_repeat_count": sum(v <= CANONICAL_GATE_MS for v in p99_values),
            "frontier_update_authorized": False,
        },
    }
    return result


def _print(result: dict[str, Any]) -> None:
    print("\nPhase 5 E7 — 100% moving P99 tail composition attribution")
    print("=" * 96)
    for r in result["repeats"]:
        print(
            f"repeat-{r['repeat']}: avg={r['controlled_avg_ms']:.3f} ms "
            f"p95={r['controlled_p95_ms']:.3f} p99={r['controlled_p99_ms']:.3f} "
            f"tail uplift={r['controlled_tail_uplift_ms']:.3f} ms "
            f"breaches={r['canonical_breach_frames']} guards={'PASS' if r['guards_ok'] else 'FAIL'}"
        )
        print("  top3: " + ", ".join(r["positive_top3"]))
    print("-" * 96)
    print("Stable section contributors:")
    for row in result["stable_section_contributors"][:8]:
        print(
            f"  {row['name']:<28} top3={row['top3_repeat_count']}/3 "
            f"median uplift={row['median_self_tail_uplift_ms']:+.3f} ms "
            f"share={row['median_self_tail_uplift_share_pct']:+.1f}% "
            f"r={row['median_pearson_r_controlled']:+.3f}"
        )
    print("-" * 96)
    print(f"DECISION: {result['decision']}")
    print(f"NEXT CAUSAL TARGET: {result['next_causal_target']}")
    gate = result["canonical_30hz_diagnostic"]
    print(
        f"30Hz diagnostic: median p99={gate['median_p99_ms']:.3f} ms; "
        f"passes={gate['pass_repeat_count']}/3; frontier update authorized=False"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    args = parser.parse_args()
    result = analyze(args.run_dir)
    out = args.run_dir / "phase5-e7-tail-composition-summary.json"
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _print(result)
    return 0 if result["all_guards_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
