#!/usr/bin/env python3
"""Run a deterministic moving-world + camera pan/zoom terrain stress point."""

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
        description="STAR deterministic terrain camera-stress profiler"
    )
    parser.add_argument("--socket", default="/tmp/star-scale.sock")
    parser.add_argument("--density", type=float, default=1.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--target-radius", type=int, default=12)
    parser.add_argument("--warmup", type=float, default=5.0)
    parser.add_argument("--stress-duration", type=float, default=10.0)
    parser.add_argument("--step-seconds", type=float, default=0.75)
    parser.add_argument("--sustained-duration", type=float, default=20.0)
    parser.add_argument("--output", default=None)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if not 0.0 <= args.density <= 1.0:
        _write({"ok": False, "error": "density_out_of_range"}, args.output)
        return 1
    if args.warmup < 0.0 or args.stress_duration <= 0.0:
        _write({"ok": False, "error": "invalid_duration"}, args.output)
        return 1
    if args.step_seconds < 0.1:
        _write({"ok": False, "error": "camera_stress_step_too_short"}, args.output)
        return 1
    if args.sustained_duration <= args.stress_duration + 1.0:
        _write(
            {
                "ok": False,
                "error": "sustained_duration_too_short",
                "message": "sustained-duration must exceed stress-duration by >1s",
            },
            args.output,
        )
        return 1

    time.sleep(args.warmup)
    prepare = request(
        args.socket,
        {
            "command": "prepare_random_moves",
            "density": 1.0,
            "seed": args.seed,
            "target_radius": args.target_radius,
            "policy": "stress_stack_endpoint",
            "correct_unreachable": True,
        },
    )
    result: Dict[str, Any] = {
        "ok": False,
        "experiment": "terrain_camera_stress_v1",
        "density": args.density,
        "warmup_seconds": args.warmup,
        "stress_duration_seconds": args.stress_duration,
        "camera_step_seconds": args.step_seconds,
        "prepare": prepare,
    }
    if not prepare.get("ok"):
        _write(result, args.output)
        return 1

    sustained = request(
        args.socket,
        {
            "command": "start_sustained_batch",
            "duration_seconds": args.sustained_duration,
            "phase": "staggered",
            "require_fog": "on",
            "execution_density": args.density,
            "execution_seed": args.seed,
        },
    )
    result["start"] = sustained
    if not sustained.get("ok"):
        _write(result, args.output)
        return 1

    camera = request(
        args.socket,
        {
            "command": "start_camera_stress",
            "step_seconds": args.step_seconds,
        },
    )
    result["camera_start"] = camera
    if not camera.get("ok"):
        request(args.socket, {"command": "stop_sustained"})
        _write(result, args.output)
        return 1

    try:
        time.sleep(args.stress_duration)
        snapshot = request(args.socket, {"command": "profile_snapshot"})
        result["snapshot"] = snapshot

        guards = snapshot.get("guards", {}) if isinstance(snapshot, dict) else {}
        context = snapshot.get("context", {}) if isinstance(snapshot, dict) else {}
        living = int(guards.get("living_units", 0) or 0)
        actual_density = float(guards.get("actual_density", 0.0) or 0.0)
        tolerance = max(1.0 / living, 1e-4) if living else 1e-4
        transitions = int(context.get("scale_camera_stress_transitions", 0) or 0)
        checks = {
            "snapshot_ok": bool(snapshot.get("ok")),
            "rolling_window_full": bool(snapshot.get("rolling_window_full")),
            "fog_matches_required": bool(guards.get("fog_matches_required")),
            "density_matches_requested": abs(actual_density - args.density) <= tolerance,
            "camera_stress_active": bool(context.get("scale_camera_stress_active")),
            "camera_stress_transitioned": transitions >= 2,
        }
        result["validation"] = {
            "valid": all(checks.values()),
            "checks": checks,
            "actual_density": actual_density,
            "density_tolerance": tolerance,
            "camera_transitions": transitions,
            "terrain_present_mode": context.get("scale_terrain_present_mode"),
        }
        result["ok"] = bool(result["validation"]["valid"])
    finally:
        try:
            result["camera_stop"] = request(
                args.socket,
                {"command": "stop_camera_stress", "restore": True},
            )
        finally:
            result["sustained_stop"] = request(
                args.socket,
                {"command": "stop_sustained"},
            )

    _write(result, args.output)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
