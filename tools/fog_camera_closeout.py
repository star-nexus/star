#!/usr/bin/env python3
"""Run the final uninstrumented Camera-to-Fog closeout matrix."""

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

from rotk_env.testing.fog_camera_closeout import build_closeout_summary

DEFAULT_BASE_COMMIT = "717932ec520ffc215ab45c32bd33cbb0fa5a68c2"


def _write(data: Dict[str, Any], output: str | None) -> None:
    text = json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True)
    if output:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n", encoding="utf-8")
        print(
            json.dumps(
                {
                    "ok": data.get("integrity_checks", {}).get("valid"),
                    "experiment": data.get("experiment"),
                    "phase": data.get("phase"),
                    "residual_classification": data.get(
                        "residual_classification"
                    ),
                    "closeout_recommendation": data.get(
                        "closeout_recommendation"
                    ),
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
        description="Run STAR Camera-to-Fog final closeout reassessment"
    )
    parser.add_argument("--socket", default="/tmp/star-scale-closeout.sock")
    parser.add_argument("--warmup", type=float, default=2.0)
    parser.add_argument("--between-epochs", type=float, default=0.25)
    parser.add_argument("--poll-seconds", type=float, default=0.05)
    parser.add_argument("--timeout-per-epoch", type=float, default=30.0)
    parser.add_argument("--stationary-frames", type=int, default=120)
    parser.add_argument("--base-commit", default=DEFAULT_BASE_COMMIT)
    parser.add_argument(
        "--output",
        default="results/fog-camera-attribution/fog-camera-closeout.json",
    )
    return parser


def _run_epoch(
    args: argparse.Namespace,
    *,
    name: str,
    mode: str,
    start_zoom: float,
) -> Dict[str, Any]:
    started = request(
        args.socket,
        {
            "command": "start_fog_camera_attribution",
            "mode": mode,
            "geometry_path": "fused",
            "corner_path": "precomputed",
            "world_corner_path": "cached",
            "presentation_bounds_path": "fog_content",
            "start_zoom": start_zoom,
            "stationary_frames": args.stationary_frames,
            "timer_sanity_samples": 1,
            "polygon_timing_enabled": False,
            "hex_corners_timing_enabled": False,
            "geometry_prepare_timing_enabled": False,
            "screen_transform_timing_enabled": False,
            "bounds_rect_timing_enabled": False,
            "translation_feasibility_enabled": False,
            "phase_raster_feasibility_enabled": False,
        },
    )
    result: Dict[str, Any] = {
        "name": name,
        "mode": mode,
        "start_zoom": start_zoom,
        "start": started,
    }
    if not started.get("ok"):
        result.update(ok=False, error="start_failed")
        return result

    status: Dict[str, Any] = {}
    deadline = time.monotonic() + args.timeout_per_epoch
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
    result["ok"] = bool(result["stop"].get("ok")) and bool(
        result["stop"].get("completed")
    )
    return result


def main() -> int:
    args = build_parser().parse_args()
    if (
        args.warmup < 0.0
        or args.between_epochs < 0.0
        or args.poll_seconds <= 0.0
        or args.timeout_per_epoch <= 0.0
        or args.stationary_frames <= 0
    ):
        _write({"ok": False, "error": "invalid_argument"}, args.output)
        return 1

    matrix = (
        ("prime", "short_pan", 0.15),
        ("stationary_z015", "stationary", 0.15),
        ("short_pan_z015_a", "short_pan", 0.15),
        ("short_pan_z050", "short_pan", 0.50),
        ("short_pan_z015_b", "short_pan", 0.15),
        ("long_pan_z015", "long_pan", 0.15),
        ("zoom_z015", "zoom", 0.15),
    )
    time.sleep(args.warmup)
    raw: Dict[str, Dict[str, Any]] = {}
    for index, (name, mode, zoom) in enumerate(matrix, start=1):
        if index > 1:
            time.sleep(args.between_epochs)
        print(f"[{index}/{len(matrix)}] {name}", flush=True)
        raw[name] = _run_epoch(
            args,
            name=name,
            mode=mode,
            start_zoom=zoom,
        )
        if not raw[name].get("ok"):
            failure = {
                "experiment": "2026-09-camera-fog-full-rebuild",
                "phase": "closeout_reassessment_v1",
                "base_commit": args.base_commit,
                "ok": False,
                "failed_epoch": name,
                "raw": raw,
                "residual_classification": "UNEXPLAINED-RESIDUAL",
                "closeout_recommendation": (
                    "CASE-CLOSEOUT-NOT-READY / KEEP-OPEN"
                ),
            }
            _write(failure, args.output)
            return 1

    summary = build_closeout_summary(
        base_commit=args.base_commit,
        prime_raw=raw.pop("prime"),
        run_raw=raw,
    )
    _write(summary, args.output)
    return 0 if summary["integrity_checks"]["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
