#!/usr/bin/env python3
"""Run deterministic camera-only Fog full-rebuild attribution epochs."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Dict, List

from scale_driver import request

EXPERIMENT_ID = "2026-09-camera-fog-full-rebuild"
ALL_MODES = ("stationary", "short-pan", "long-pan", "zoom")


def _write(data: Dict[str, Any], output: str | None) -> None:
    text = json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True)
    print(text)
    if output:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="STAR Fog camera full-rebuild attribution experiment"
    )
    parser.add_argument("--socket", default="/tmp/star-scale.sock")
    parser.add_argument(
        "--mode",
        choices=("all", *ALL_MODES),
        default="all",
        help="Run one independent camera epoch or all four (default: all)",
    )
    parser.add_argument("--warmup", type=float, default=2.0)
    parser.add_argument("--between-epochs", type=float, default=0.5)
    parser.add_argument("--stationary-frames", type=int, default=120)
    parser.add_argument("--timer-sanity-samples", type=int, default=20_000)
    parser.add_argument(
        "--polygon-timing",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable detailed polygon timing (default: enabled)",
    )
    parser.add_argument(
        "--hex-corners-timing",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable detailed get_hex_corners timing (default: enabled)",
    )
    parser.add_argument(
        "--geometry-prepare-timing",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Enable detailed Fog geometry-preparation timing (default: disabled)",
    )
    parser.add_argument(
        "--screen-transform-timing",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Enable detailed screen-space point timing (default: disabled)",
    )
    parser.add_argument(
        "--bounds-rect-timing",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Enable detailed bounds and Rect timing (default: disabled)",
    )
    parser.add_argument("--poll-seconds", type=float, default=0.05)
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--output", default=None)
    return parser


def _run_mode(args, mode: str) -> Dict[str, Any]:
    started = request(
        args.socket,
        {
            "command": "start_fog_camera_attribution",
            "mode": mode,
            "stationary_frames": args.stationary_frames,
            "timer_sanity_samples": args.timer_sanity_samples,
            "polygon_timing_enabled": args.polygon_timing,
            "hex_corners_timing_enabled": args.hex_corners_timing,
            "geometry_prepare_timing_enabled": args.geometry_prepare_timing,
            "screen_transform_timing_enabled": args.screen_transform_timing,
            "bounds_rect_timing_enabled": args.bounds_rect_timing,
        },
    )
    result: Dict[str, Any] = {"mode": mode, "start": started, "ok": False}
    if not started.get("ok"):
        return result

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
        result["status"] = status
    finally:
        result["stop"] = request(
            args.socket, {"command": "stop_fog_camera_attribution"}
        )

    stopped = result["stop"]
    checks = {
        "completed": bool(stopped.get("completed")),
        "camera_restored": bool(stopped.get("camera_restored")),
        "fog_counter_delta_exact": (
            stopped.get("fog_full_build_delta")
            == stopped.get("fog_full_build_counter_end", 0)
            - stopped.get("fog_full_build_counter_start", 0)
        ),
        "units_stationary_at_start": stopped.get("active_moving_units_start") == 0,
        "units_stationary_at_end": stopped.get("active_moving_units_end") == 0,
        "units_stationary_during_epoch": stopped.get("unit_movement_frames") == 0,
        "fog_enabled_at_start": stopped.get("fog_enabled_start") is True,
        "fog_enabled_at_end": stopped.get("fog_enabled_end") is True,
        "fog_enabled_during_epoch": stopped.get("fog_disabled_frames") == 0,
        "not_aborted": stopped.get("aborted_reason") is None,
    }
    result["validation"] = {"valid": all(checks.values()), "checks": checks}
    result["ok"] = bool(stopped.get("ok")) and all(checks.values())
    return result


def main() -> int:
    args = build_parser().parse_args()
    if args.warmup < 0.0 or args.between_epochs < 0.0:
        _write({"ok": False, "error": "invalid_warmup"}, args.output)
        return 1
    if args.stationary_frames <= 0:
        _write({"ok": False, "error": "invalid_stationary_frames"}, args.output)
        return 1
    if args.timer_sanity_samples <= 0:
        _write({"ok": False, "error": "invalid_timer_sanity_samples"}, args.output)
        return 1
    if args.poll_seconds <= 0.0 or args.timeout <= 0.0:
        _write({"ok": False, "error": "invalid_poll_or_timeout"}, args.output)
        return 1

    modes: List[str] = list(ALL_MODES) if args.mode == "all" else [args.mode]
    time.sleep(args.warmup)
    runs = []
    for index, mode in enumerate(modes):
        if index:
            time.sleep(args.between_epochs)
        runs.append(_run_mode(args, mode))

    output = {
        "ok": all(run.get("ok") for run in runs),
        "experiment": EXPERIMENT_ID,
        "runs": runs,
    }
    _write(output, args.output)
    return 0 if output["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
