#!/usr/bin/env python3
"""Run the directed Fog-content bounds correctness matrix."""

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

from rotk_env.testing.fog_content_bounds_experiment import DIRECTIONS
from rotk_env.testing.fog_content_bounds_feasibility import (
    evaluate_direct_fog_content_matrix,
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
        description="Run Fog-content presentation-bounds feasibility matrix"
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
        "command": "start_fog_content_bounds_feasibility",
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
    stopped: Dict[str, Any] = {}
    deadline = time.monotonic() + timeout
    try:
        while time.monotonic() < deadline:
            time.sleep(poll_seconds)
            status = request(
                socket_path,
                {"command": "fog_content_bounds_feasibility_status"},
            )
            if not status.get("ok") or status.get("completed"):
                break
        workload["status"] = status
    finally:
        stopped = request(
            socket_path, {"command": "stop_fog_content_bounds_feasibility"}
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
        "corner_path_is_precomputed": stopped.get("corner_path_effective")
        == "precomputed",
        "corner_path_restored": stopped.get("corner_path_restored") is True,
        "world_corner_path_is_cached": stopped.get("world_corner_path_effective")
        == "cached",
        "world_corner_path_restored": stopped.get("world_corner_path_restored")
        is True,
        "fog_content_path_used": stopped.get("presentation_bounds_path_effective")
        == "fog_content",
        "presentation_path_restored": stopped.get(
            "presentation_bounds_path_restored"
        )
        is True,
        "performance_timers_disabled": stopped.get("performance_timers_enabled")
        is False,
        "fog_remained_enabled": stopped.get("fog_disabled_frames") == 0,
        "units_stationary": stopped.get("active_moving_units_start") == 0
        and stopped.get("active_moving_units_end") == 0
        and stopped.get("unit_movement_frames") == 0,
        "initial_and_changed_frames_observed": result.get(
            "full_rebuild_comparisons"
        )
        == stopped.get("camera_changed_frames", 0) + 1,
        "all_pixel_oracles_exact": result.get("mismatch_count") == 0,
    }
    workload["validation"] = {"valid": all(checks.values()), "checks": checks}
    workload["result"] = result
    workload["ok"] = bool(stopped.get("ok")) and all(checks.values())
    return workload


def _aggregate(
    workloads: list[Dict[str, Any]], direct: Dict[str, object]
) -> Dict[str, object]:
    results = [item["result"] for item in workloads]
    comparisons = sum(int(item["full_rebuild_comparisons"]) for item in results)
    exact = sum(int(item["exact_match_count"]) for item in results)
    set_changes = sum(int(item["visible_tiles_set_change_frames"]) for item in results)
    exact_set_changes = sum(int(item["exact_on_set_change_frames"]) for item in results)
    direct_exact = direct["comparison_count"] == direct["exact_match_count"]
    runtime_exact = comparisons == exact
    return {
        "runtime_workload_count": len(workloads),
        "full_rebuild_comparisons": comparisons,
        "exact_match_count": exact,
        "mismatch_count": comparisons - exact,
        "visible_tiles_set_change_frames": set_changes,
        "exact_on_set_change_frames": exact_set_changes,
        "candidate_exact_across_set_changes": set_changes > 0
        and set_changes == exact_set_changes,
        "input_tiles_total": sum(int(item["input_tiles_total"]) for item in results),
        "visible_no_fog_tiles_total": sum(
            int(item["visible_no_fog_tiles_total"]) for item in results
        ),
        "fog_polygon_tiles_total": sum(
            int(item["fog_polygon_tiles_total"]) for item in results
        ),
        "legacy_source_pixels_total": sum(
            int(item["legacy_source_pixels_total"]) for item in results
        ),
        "candidate_source_pixels_total": sum(
            int(item["candidate_source_pixels_total"]) for item in results
        ),
        "structural_conclusion": (
            "FOG-CONTENT-BOUNDS FEASIBLE / READY-FOR-CONTROLLED-A-B"
            if direct_exact and runtime_exact and set_changes > 0
            else "FOG-CONTENT-BOUNDS REJECTED / FALLBACK-TO-LIGHTWEIGHT-RECT"
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
        {
            "name": f"pan_{direction}_zoom_{zoom:.2f}",
            "mode": "pan",
            "direction": direction,
            "zoom": zoom,
        }
        for zoom in PAN_ZOOMS
        for direction in DIRECTIONS
    ]
    matrix.append(
        {
            "name": "zoom_0.15_to_0.50",
            "mode": "zoom",
            "zoom": 0.15,
            "target_zoom": 0.50,
        }
    )
    time.sleep(args.warmup)
    direct = evaluate_direct_fog_content_matrix()
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
    global_result = _aggregate(workloads, direct) if valid else None
    output = {
        "ok": valid,
        "experiment": "fog_content_bounds_feasibility_v1",
        "configuration": {
            "start_offset": list(START_OFFSET),
            "pan_zooms": list(PAN_ZOOMS),
            "directions": list(DIRECTIONS),
            "pan_target_pixels": 128.0,
            "zoom_workload": [0.15, 0.50],
            "canonical_full_rebuild_ground_truth": True,
            "nontrivial_framebuffer_oracle": True,
            "production_surface_get_bounding_rect": False,
            "performance_timers_enabled": False,
            "stationary_units_required": True,
        },
        "direct": direct,
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
