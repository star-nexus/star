#!/usr/bin/env python3
"""Run the pixel-exact short-pan Fog translation feasibility experiment."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Dict

from scale_driver import request


def _write(data: Dict[str, Any], output: str | None) -> None:
    text = json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True)
    print(text)
    if output:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check whether canonical Fog pan frames are integer translations"
    )
    parser.add_argument("--socket", default="/tmp/star-scale.sock")
    parser.add_argument("--warmup", type=float, default=2.0)
    parser.add_argument("--poll-seconds", type=float, default=0.05)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--nearby-radius", type=int, choices=(0, 1), default=1)
    parser.add_argument("--output", default=None)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.warmup < 0.0 or args.poll_seconds <= 0.0 or args.timeout <= 0.0:
        _write({"ok": False, "error": "invalid_timing_argument"}, args.output)
        return 1

    time.sleep(args.warmup)
    started = request(
        args.socket,
        {
            "command": "start_fog_camera_attribution",
            "mode": "short_pan",
            "geometry_path": "fused",
            "corner_path": "precomputed",
            "polygon_timing_enabled": False,
            "hex_corners_timing_enabled": False,
            "geometry_prepare_timing_enabled": False,
            "screen_transform_timing_enabled": False,
            "bounds_rect_timing_enabled": False,
            "timer_sanity_samples": 1,
            "translation_feasibility_enabled": True,
            "translation_nearby_radius": args.nearby_radius,
        },
    )
    output: Dict[str, Any] = {"ok": False, "start": started}
    if not started.get("ok"):
        _write(output, args.output)
        return 1

    deadline = time.monotonic() + args.timeout
    status: Dict[str, Any] = {}
    try:
        while time.monotonic() < deadline:
            time.sleep(args.poll_seconds)
            status = request(
                args.socket, {"command": "fog_camera_attribution_status"}
            )
            if not status.get("ok") or status.get("completed"):
                break
        output["status"] = status
    finally:
        output["stop"] = request(
            args.socket, {"command": "stop_fog_camera_attribution"}
        )

    stopped = output["stop"]
    feasibility = stopped.get("translation_feasibility") or {}
    checks = {
        "completed": stopped.get("completed") is True,
        "camera_restored": stopped.get("camera_restored") is True,
        "geometry_path_is_fused": stopped.get("geometry_path_effective") == "fused",
        "geometry_path_restored": stopped.get("geometry_path_restored") is True,
        "corner_path_is_precomputed": (
            stopped.get("corner_path_effective") == "precomputed"
        ),
        "corner_path_restored": stopped.get("corner_path_restored") is True,
        "fog_enabled": (
            stopped.get("fog_enabled_start") is True
            and stopped.get("fog_enabled_end") is True
            and stopped.get("fog_disabled_frames") == 0
        ),
        "units_stationary": (
            stopped.get("active_moving_units_start") == 0
            and stopped.get("active_moving_units_end") == 0
            and stopped.get("unit_movement_frames") == 0
        ),
        "camera_frames_compared": (
            feasibility.get("total_camera_changing_frames")
            == stopped.get("camera_changed_frames")
        ),
        "performance_timers_disabled": all(
            stopped.get(name) is False
            for name in (
                "polygon_timing_enabled",
                "hex_corners_timing_enabled",
                "geometry_prepare_timing_enabled",
                "screen_transform_timing_enabled",
                "bounds_rect_timing_enabled",
            )
        ),
        "not_aborted": stopped.get("aborted_reason") is None,
    }
    output["validation"] = {"valid": all(checks.values()), "checks": checks}
    output["experiment"] = "fog_pan_integer_translation_feasibility_v1"
    output["result"] = feasibility
    output["ok"] = bool(stopped.get("ok")) and all(checks.values())
    _write(output, args.output)
    return 0 if output["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
