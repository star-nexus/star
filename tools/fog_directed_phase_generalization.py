#!/usr/bin/env python3
"""Run the final directed Fog raster-phase correctness matrix."""

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

from rotk_env.testing.fog_directed_phase_generalization import (
    aggregate_generalization_results,
)
from rotk_env.testing.fog_directed_phase_experiment import DIRECTIONS

START_OFFSETS = (
    ("integer", 1240.0, 634.0),
    ("quarter", 1240.25, 634.25),
    ("half", 1240.5, 634.5),
    ("three_quarter", 1240.75, 634.75),
    ("non_simple", 1240.123456789, 634.876543211),
)
ZOOMS = (0.10, 0.15, 0.50)


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
        description="Run the final directed Fog raster-phase feasibility matrix"
    )
    parser.add_argument("--socket", default="/tmp/star-scale.sock")
    parser.add_argument("--warmup", type=float, default=2.0)
    parser.add_argument("--poll-seconds", type=float, default=0.05)
    parser.add_argument("--between-workloads", type=float, default=0.05)
    parser.add_argument("--timeout-per-workload", type=float, default=30.0)
    parser.add_argument("--output", default=None)
    return parser


def _run_workload(
    socket_path: str,
    *,
    direction: str,
    start_name: str,
    start_x: float,
    start_y: float,
    zoom: float,
    poll_seconds: float,
    timeout: float,
) -> Dict[str, Any]:
    started = request(
        socket_path,
        {
            "command": "start_fog_directed_phase_generalization",
            "direction": direction,
            "start_offset_x": start_x,
            "start_offset_y": start_y,
            "zoom": zoom,
        },
    )
    workload: Dict[str, Any] = {
        "direction": direction,
        "start_offset_name": start_name,
        "start_offset": [start_x, start_y],
        "zoom": zoom,
        "start": started,
    }
    if not started.get("ok"):
        workload["ok"] = False
        workload["error"] = "start_failed"
        return workload

    status: Dict[str, Any] = {}
    deadline = time.monotonic() + timeout
    try:
        while time.monotonic() < deadline:
            time.sleep(poll_seconds)
            status = request(
                socket_path,
                {"command": "fog_directed_phase_generalization_status"},
            )
            if not status.get("ok") or status.get("completed"):
                break
        workload["status"] = status
    finally:
        stopped = request(
            socket_path,
            {"command": "stop_fog_directed_phase_generalization"},
        )
        workload["stop"] = stopped

    result = stopped.get("result") or {}
    first_anchor = result.get("first_anchor") or {}
    rolling_anchor = result.get("rolling_anchor") or {}
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
        "performance_timers_disabled": stopped.get("performance_timers_enabled")
        is False,
        "fog_remained_enabled": stopped.get("fog_disabled_frames") == 0,
        "units_stationary": (
            stopped.get("active_moving_units_start") == 0
            and stopped.get("active_moving_units_end") == 0
            and stopped.get("unit_movement_frames") == 0
        ),
        "canonical_frames_complete": result.get("camera_changing_frames")
        == stopped.get("camera_changed_frames"),
        "first_and_rolling_hit_counts_equal": first_anchor.get("reusable_hits")
        == rolling_anchor.get("reusable_hits"),
    }
    workload["validation"] = {"valid": all(checks.values()), "checks": checks}
    workload["result"] = result
    workload["ok"] = bool(stopped.get("ok")) and all(checks.values())
    return workload


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
        (direction, start_name, start_x, start_y, zoom)
        for zoom in ZOOMS
        for start_name, start_x, start_y in START_OFFSETS
        for direction in DIRECTIONS
    ]
    time.sleep(args.warmup)
    workloads = []
    for index, (direction, start_name, start_x, start_y, zoom) in enumerate(
        matrix, start=1
    ):
        print(
            f"[{index}/{len(matrix)}] {direction} start={start_name} zoom={zoom}",
            flush=True,
        )
        workload = _run_workload(
            args.socket,
            direction=direction,
            start_name=start_name,
            start_x=start_x,
            start_y=start_y,
            zoom=zoom,
            poll_seconds=args.poll_seconds,
            timeout=args.timeout_per_workload,
        )
        workloads.append(workload)
        if not workload["ok"]:
            break
        if index < len(matrix):
            time.sleep(args.between_workloads)

    valid = len(workloads) == len(matrix) and all(item["ok"] for item in workloads)
    global_result = (
        aggregate_generalization_results(workloads) if valid else None
    )
    output = {
        "ok": valid,
        "experiment": "fog_directed_phase_generalization_v1",
        "configuration": {
            "directions": list(DIRECTIONS),
            "start_offsets": [
                {"name": name, "offset": [x, y]}
                for name, x, y in START_OFFSETS
            ],
            "zooms": list(ZOOMS),
            "pan_target_pixels": 128.0,
            "geometry_path": "fused",
            "corner_path": "precomputed",
            "performance_timers_enabled": False,
            "stationary_units_required": True,
            "canonical_full_rebuild_ground_truth": True,
        },
        "workloads": workloads,
        "global": global_result,
        "structural_recommendation": (
            global_result.get("structural_recommendation")
            if global_result is not None
            else None
        ),
    }
    _write(output, args.output)
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
