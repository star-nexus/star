#!/usr/bin/env python3
"""Run the directed Fog presentation-bounds correctness matrix."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scale_driver import request

from rotk_env.testing.fog_presentation_bounds_experiment import DIRECTIONS
from rotk_env.testing.fog_presentation_bounds_feasibility import (
    evaluate_direct_correctness_matrix,
)

START_OFFSET = (1240.0, 634.0)
PAN_ZOOMS = (0.15, 0.50)


def _write(data: Dict[str, Any], output: str | None) -> None:
    text = json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True)
    if output:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n", encoding="utf-8")
        print(
            json.dumps(
                {
                    "ok": data.get("ok"),
                    "experiment": data.get("experiment"),
                    "workload_count": len(data.get("workloads", ())),
                    "global": data.get("global"),
                    "output": str(path),
                },
                indent=2,
                ensure_ascii=False,
                sort_keys=True,
            )
        )
    else:
        print(text)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run Fog presentation-bounds decoupling feasibility matrix"
    )
    parser.add_argument("--socket", default="/tmp/star-scale-bounds.sock")
    parser.add_argument("--warmup", type=float, default=2.0)
    parser.add_argument("--poll-seconds", type=float, default=0.05)
    parser.add_argument("--between-workloads", type=float, default=0.05)
    parser.add_argument("--timeout-per-workload", type=float, default=30.0)
    parser.add_argument("--output", default=None)
    return parser


def _run_workload(
    socket_path: str,
    specification: Dict[str, object],
    *,
    poll_seconds: float,
    timeout: float,
) -> Dict[str, Any]:
    command = {
        "command": "start_fog_presentation_bounds_feasibility",
        "mode": specification["mode"],
        "direction": specification.get("direction", "horizontal_positive"),
        "start_offset_x": START_OFFSET[0],
        "start_offset_y": START_OFFSET[1],
        "zoom": specification["zoom"],
        "target_zoom": specification.get("target_zoom", 0.50),
    }
    started = request(socket_path, command)
    workload: Dict[str, Any] = {"specification": specification, "start": started}
    if not started.get("ok"):
        workload.update(ok=False, error="start_failed")
        return workload

    status: Dict[str, Any] = {}
    deadline = time.monotonic() + timeout
    try:
        while time.monotonic() < deadline:
            time.sleep(poll_seconds)
            status = request(
                socket_path,
                {"command": "fog_presentation_bounds_feasibility_status"},
            )
            if not status.get("ok") or status.get("completed"):
                break
        workload["status"] = status
    finally:
        stopped = request(
            socket_path,
            {"command": "stop_fog_presentation_bounds_feasibility"},
        )
        workload["stop"] = stopped

    result = stopped.get("result") or {}
    checks = {
        "completed": stopped.get("completed") is True,
        "not_aborted": stopped.get("aborted_reason") is None,
        "camera_restored": stopped.get("camera_restored") is True,
        "observer_restored": stopped.get("observer_restored") is True,
        "timers_restored": stopped.get("timers_restored") is True,
        "geometry_path_is_fused": stopped.get("geometry_path_effective") == "fused",
        "geometry_path_restored": stopped.get("geometry_path_restored") is True,
        "corner_path_is_precomputed": stopped.get("corner_path_effective") == "precomputed",
        "corner_path_restored": stopped.get("corner_path_restored") is True,
        "world_corner_path_is_cached": stopped.get("world_corner_path_effective") == "cached",
        "world_corner_path_restored": stopped.get("world_corner_path_restored") is True,
        "performance_timers_disabled": stopped.get("performance_timers_enabled") is False,
        "fog_remained_enabled": stopped.get("fog_disabled_frames") == 0,
        "units_stationary": (
            stopped.get("active_moving_units_start") == 0
            and stopped.get("active_moving_units_end") == 0
            and stopped.get("unit_movement_frames") == 0
        ),
        "initial_and_changed_frames_observed": result.get("full_rebuild_comparisons")
        == stopped.get("camera_changed_frames", 0) + 1,
        "legacy_recompute_matches": all(
            item.get("legacy_recomputed_exact") is True
            for item in result.get("comparisons", ())
        ),
    }
    workload["validation"] = {"valid": all(checks.values()), "checks": checks}
    workload["result"] = result
    workload["ok"] = bool(stopped.get("ok")) and all(checks.values())
    return workload


def _aggregate(
    workloads: list[Dict[str, Any]], direct_result: Dict[str, object]
) -> Dict[str, object]:
    results = [item["result"] for item in workloads]
    comparisons = sum(int(item["full_rebuild_comparisons"]) for item in results)
    exact = sum(int(item["exact_match_count"]) for item in results)
    set_changes = sum(int(item["visible_tiles_set_change_frames"]) for item in results)
    exact_set_changes = sum(int(item["exact_on_set_change_frames"]) for item in results)
    categories: Dict[str, int] = {}
    for result in results:
        for name, count in result["mismatch_category_counts"].items():
            categories[name] = categories.get(name, 0) + int(count)
    return {
        "runtime_workload_count": len(workloads),
        "full_rebuild_comparisons": comparisons,
        "exact_match_count": exact,
        "mismatch_count": comparisons - exact,
        "visible_tiles_set_change_frames": set_changes,
        "exact_on_set_change_frames": exact_set_changes,
        "candidate_exact_across_set_changes": set_changes > 0 and set_changes == exact_set_changes,
        "mismatch_category_counts": categories,
        "structural_conclusion": (
            "STRUCTURAL-FEASIBILITY-4 VERIFIED / READY-FOR-PRESENTATION-BOUNDS-A-B"
            if comparisons == exact
            and set_changes > 0
            and direct_result["supported_production_topology_mismatches"] == 0
            else "STRUCTURAL-FEASIBILITY-4 REJECTED / PRESENTATION-BOUNDS-DECOUPLING-NOT-EXACT"
        ),
    }


def main() -> int:
    args = build_parser().parse_args()
    if (
        args.warmup < 0.0
        or args.poll_seconds <= 0.0
        or args.between_workloads < 0.0
        or args.timeout_per_workload <= 0.0
    ):
        _write({"ok": False, "error": "invalid_timing_argument"}, args.output)
        return 1

    matrix = [
        {"name": f"pan_{direction}_zoom_{zoom:.2f}", "mode": "pan", "direction": direction, "zoom": zoom}
        for zoom in PAN_ZOOMS
        for direction in DIRECTIONS
    ]
    matrix.append(
        {"name": "zoom_0.15_to_0.50", "mode": "zoom", "zoom": 0.15, "target_zoom": 0.50}
    )
    time.sleep(args.warmup)
    direct_result = evaluate_direct_correctness_matrix()
    workloads = []
    for index, specification in enumerate(matrix, start=1):
        print(f"[{index}/{len(matrix)}] {specification['name']}", flush=True)
        workload = _run_workload(
            args.socket,
            specification,
            poll_seconds=args.poll_seconds,
            timeout=args.timeout_per_workload,
        )
        workloads.append(workload)
        if not workload["ok"]:
            break
        if index < len(matrix):
            time.sleep(args.between_workloads)

    valid = len(workloads) == len(matrix) and all(item["ok"] for item in workloads)
    global_result = _aggregate(workloads, direct_result) if valid else None
    output = {
        "ok": valid,
        "experiment": "fog_presentation_bounds_feasibility_v1",
        "configuration": {
            "start_offset": list(START_OFFSET),
            "pan_zooms": list(PAN_ZOOMS),
            "directions": list(DIRECTIONS),
            "pan_target_pixels": 128.0,
            "zoom_workload": [0.15, 0.50],
            "canonical_full_rebuild_ground_truth": True,
            "production_presentation_rect_unchanged": True,
            "performance_timers_enabled": False,
            "stationary_units_required": True,
        },
        "direct": direct_result,
        "workloads": workloads,
        "global": global_result,
        "structural_conclusion": (
            global_result.get("structural_conclusion")
            if global_result is not None
            else None
        ),
    }
    _write(output, args.output)
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
