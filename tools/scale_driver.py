#!/usr/bin/env python3
"""Drive the explicit STAR Phase-4 scale harness over a Unix-domain socket."""

from __future__ import annotations

import argparse
import json
import socket
import time
from pathlib import Path
from typing import Any, Dict


def request(socket_path: str, payload: Dict[str, Any], timeout: float = 30.0) -> Dict[str, Any]:
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.settimeout(timeout)
    try:
        client.connect(socket_path)
        client.sendall((json.dumps(payload, separators=(",", ":")) + "\n").encode("utf-8"))
        data = bytearray()
        while b"\n" not in data:
            chunk = client.recv(65536)
            if not chunk:
                break
            data.extend(chunk)
        if not data:
            raise RuntimeError("scale harness closed the socket without a response")
        raw = bytes(data).split(b"\n", 1)[0]
        response = json.loads(raw.decode("utf-8"))
        if not isinstance(response, dict):
            raise RuntimeError("scale harness returned a non-object response")
        return response
    finally:
        client.close()


def wait_for_socket(path: str, timeout_s: float) -> None:
    deadline = time.monotonic() + timeout_s
    last_error = None
    while time.monotonic() < deadline:
        try:
            response = request(path, {"command": "status"}, timeout=1.0)
            if response.get("ok"):
                return
        except (FileNotFoundError, ConnectionRefusedError, OSError, RuntimeError) as exc:
            last_error = exc
        time.sleep(0.1)
    raise RuntimeError(f"scale harness not ready at {path}: {last_error}")


def _print(payload: Dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def _load_profile(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _metric_stat(profile: Dict[str, Any], name: str, stat: str):
    metric = profile.get("frame_metrics", {}).get(name)
    return metric.get(stat) if isinstance(metric, dict) else None


def _metric_max(profile: Dict[str, Any], name: str):
    return _metric_stat(profile, name, "max")


def _metric_min(profile: Dict[str, Any], name: str):
    return _metric_stat(profile, name, "min")


def _metric_values(profile: Dict[str, Any], name: str):
    return _metric_stat(profile, name, "values")


def _profile_digest(profile: Dict[str, Any]) -> Dict[str, Any]:
    sections = profile.get("sections", {})
    wanted = (
        "AnimationSystem",
        "VisionSystem",
        "UnitRenderSystem",
        "MiniMapSystem",
        "render_engine",
        "render_scalar_execute",
    )
    digest_sections = {name: sections[name] for name in wanted if name in sections}
    metrics = profile.get("frame_metrics", {})
    wanted_metrics = (
        "scale_configured_moving_units",
        "scale_execution_density",
        "scale_motion_phase",
        "fog_enabled",
        "effect_position_index_changes",
        "vision_dirty_units",
        "vision_units_scanned",
        "vision_fog_delta_tiles",
        "input_key_down",
        "input_mouse_button",
        "input_mouse_wheel",
    )
    digest_metrics = {name: metrics[name] for name in wanted_metrics if name in metrics}
    return {
        "metadata": profile.get("metadata", {}),
        "window_coverage_s": profile.get("window_coverage_s"),
        "sample_count": profile.get("sample_count"),
        "window_capacity_limited": profile.get("window_capacity_limited"),
        "window_throughput_fps": profile.get("window_throughput_fps"),
        "frame_body_fps": profile.get("frame_body_fps"),
        "frame_ms": {
            "avg": profile.get("avg_frame_ms"),
            "p95": profile.get("p95_frame_ms"),
            "p99": profile.get("p99_frame_ms"),
            "max": profile.get("max_frame_ms"),
        },
        "controlled_work_frame_ms": profile.get("controlled_work_frame_ms"),
        "platform_input_frame_ms": profile.get("platform_input_frame_ms"),
        "present_frame_ms": profile.get("present_frame_ms"),
        "uninstrumented_frame_ms": profile.get("uninstrumented_frame_ms"),
        "frame_metrics": digest_metrics,
        "sections": digest_sections,
    }


def _density_point(args: argparse.Namespace) -> int:
    wait_for_socket(args.socket, args.ready_timeout)
    if args.warmup > 0:
        time.sleep(args.warmup)

    prepare = request(
        args.socket,
        {
            "command": "prepare_routes",
            "density": 1.0,
            "seed": args.seed,
            "route_steps": args.route_steps,
        },
        timeout=args.command_timeout,
    )
    if not prepare.get("ok"):
        _print({"ok": False, "stage": "prepare", "prepare": prepare})
        return 2

    start = request(
        args.socket,
        {
            "command": "start_sustained",
            "batch_id": prepare.get("batch_id"),
            "execution_density": args.density,
            "duration_seconds": args.duration,
            "phase": args.phase,
            "phase_seed": args.phase_seed,
        },
        timeout=args.command_timeout,
    )
    if not start.get("ok"):
        _print({"ok": False, "stage": "start", "prepare": prepare, "start": start})
        return 2

    # Planning/startup naturally age out of the profiler. The formal evidence is
    # the final wall-clock rolling window after sustained production execution.
    time.sleep(args.sample_after)

    profile_path = Path(args.profile).expanduser().resolve()
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    snap = request(
        args.socket,
        {"command": "profile_snapshot", "path": str(profile_path)},
        timeout=args.command_timeout,
    )
    if not snap.get("ok"):
        _print({"ok": False, "stage": "snapshot", "snapshot": snap})
        return 2

    # Status is deliberately requested only after the profile has been written,
    # so its O(N) validation scan cannot contaminate the saved measurement.
    status = request(args.socket, {"command": "status"}, timeout=args.command_timeout)
    request(args.socket, {"command": "stop_sustained"}, timeout=args.command_timeout)
    profile = _load_profile(profile_path)

    resident = int(status.get("living_units") or 0)
    active = int(status.get("active_moving_units") or 0)
    requested_density = float(args.density)
    accepted = int(start.get("accepted_moving_units") or 0)
    actual_density = active / resident if resident else 0.0
    density_tolerance = max(0.01, (1.0 / resident) if resident else 1.0)
    metadata = profile.get("metadata", {})
    configured_max = _metric_max(profile, "scale_configured_moving_units")
    density_max = _metric_max(profile, "scale_execution_density")
    phase_values = _metric_values(profile, "scale_motion_phase")
    dynamic_required = requested_density > 0.0
    position_max = float(_metric_max(profile, "effect_position_index_changes") or 0.0)
    vision_dirty_max = float(_metric_max(profile, "vision_dirty_units") or 0.0)

    guards = {
        "rolling_window_full": float(profile.get("window_coverage_s") or 0.0) >= 4.5,
        "window_not_capacity_limited": profile.get("window_capacity_limited") is False,
        "controlled_work_present": isinstance(profile.get("controlled_work_frame_ms"), dict),
        "resident_matches_prepare": resident == int(prepare.get("living_units") or -1),
        "active_matches_start": active == accepted,
        "density_matches": abs(actual_density - requested_density) <= density_tolerance,
        "profile_configured_movers_match": configured_max == float(accepted),
        "profile_density_matches": (
            isinstance(density_max, (int, float))
            and abs(float(density_max) - requested_density) <= 1e-9
        ),
        "profile_phase_matches": isinstance(phase_values, list) and args.phase in phase_values,
        "fog_fixed_on": (
            _metric_min(profile, "fog_enabled") == 1.0
            and _metric_max(profile, "fog_enabled") == 1.0
        ),
        "input_policy_fixed": metadata.get("scale_input_policy") == "blocked_gameplay_events",
        "no_key_input": _metric_max(profile, "input_key_down") == 0.0,
        "no_mouse_button_input": _metric_max(profile, "input_mouse_button") == 0.0,
        "no_mouse_wheel_input": _metric_max(profile, "input_mouse_wheel") == 0.0,
        "position_commits_present": not dynamic_required or position_max > 0.0,
        "vision_dirty_present": not dynamic_required or vision_dirty_max > 0.0,
        "zero_density_no_position_commits": dynamic_required or position_max == 0.0,
        "zero_density_no_vision_dirty": dynamic_required or vision_dirty_max == 0.0,
        "production_animation_path": start.get("production_animation_and_commits") is True,
        "no_pathfinding_during_execution": start.get("pathfinding_during_execution") is False,
    }
    ok = all(guards.values())

    result = {
        "ok": ok,
        "workload": {
            "seed": args.seed,
            "route_steps": args.route_steps,
            "execution_density": requested_density,
            "phase": args.phase,
            "phase_seed": args.phase_seed,
            "duration_seconds": args.duration,
            "warmup_seconds": args.warmup,
            "sample_after_seconds": args.sample_after,
        },
        "prepare": prepare,
        "start": start,
        "status": status,
        "guards": guards,
        "profile_path": str(profile_path),
        "profile": _profile_digest(profile),
    }
    if args.output:
        output = Path(args.output).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _print(result)
    return 0 if ok else 1


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Control STAR's explicit production-path system-scale harness."
    )
    parser.add_argument("--socket", default="/tmp/star-scale.sock")
    parser.add_argument("--command-timeout", type=float, default=30.0)
    sub = parser.add_subparsers(dest="subcommand", required=True)

    status = sub.add_parser("status")
    status.set_defaults(command={"command": "status"})

    prepare = sub.add_parser("prepare")
    prepare.add_argument("--density", type=float, default=1.0)
    prepare.add_argument("--seed", type=int, default=42)
    prepare.add_argument("--route-steps", type=int, default=12)

    start = sub.add_parser("start")
    start.add_argument("--batch-id", type=int, default=None)
    start.add_argument("--density", type=float, default=1.0)
    start.add_argument("--duration", type=float, default=20.0)
    start.add_argument("--phase", choices=["staggered", "synchronized"], default="staggered")
    start.add_argument("--phase-seed", type=int, default=42)

    sub.add_parser("stop")

    snapshot = sub.add_parser("snapshot")
    snapshot.add_argument("--profile", required=True)

    point = sub.add_parser("density-point")
    point.add_argument("--density", type=float, required=True)
    point.add_argument("--seed", type=int, default=42)
    point.add_argument("--route-steps", type=int, default=12)
    point.add_argument("--phase", choices=["staggered", "synchronized"], default="staggered")
    point.add_argument("--phase-seed", type=int, default=42)
    point.add_argument("--duration", type=float, default=20.0)
    point.add_argument("--warmup", type=float, default=5.0)
    point.add_argument("--sample-after", type=float, default=7.0)
    point.add_argument("--ready-timeout", type=float, default=30.0)
    point.add_argument("--profile", required=True)
    point.add_argument("--output", default=None)
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    if args.subcommand == "density-point":
        return _density_point(args)
    if args.subcommand == "prepare":
        payload = {
            "command": "prepare_routes",
            "density": args.density,
            "seed": args.seed,
            "route_steps": args.route_steps,
        }
    elif args.subcommand == "start":
        payload = {
            "command": "start_sustained",
            "execution_density": args.density,
            "duration_seconds": args.duration,
            "phase": args.phase,
            "phase_seed": args.phase_seed,
        }
        if args.batch_id is not None:
            payload["batch_id"] = args.batch_id
    elif args.subcommand == "stop":
        payload = {"command": "stop_sustained"}
    elif args.subcommand == "snapshot":
        payload = {
            "command": "profile_snapshot",
            "path": str(Path(args.profile).expanduser().resolve()),
        }
    else:
        payload = args.command

    response = request(args.socket, payload, timeout=args.command_timeout)
    _print(response)
    return 0 if response.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
