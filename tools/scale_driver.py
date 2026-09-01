#!/usr/bin/env python3
"""Control STAR's local Scale Test Harness over a Unix Domain Socket."""

from __future__ import annotations

import argparse
import json
import socket
import sys
import time
from pathlib import Path
from typing import Any, Dict


def request(socket_path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        client.connect(socket_path)
        client.sendall((json.dumps(payload, separators=(",", ":")) + "\n").encode())
        chunks = bytearray()
        while b"\n" not in chunks:
            chunk = client.recv(65536)
            if not chunk:
                raise RuntimeError("scale harness closed the socket before replying")
            chunks.extend(chunk)
        line = bytes(chunks).split(b"\n", 1)[0]
        return json.loads(line.decode("utf-8"))
    finally:
        client.close()


def _prepare_payload(args, *, density_override: float | None = None) -> Dict[str, Any]:
    return {
        "command": "prepare_random_moves",
        "density": args.density if density_override is None else density_override,
        "seed": args.seed,
        "target_radius": args.target_radius,
        "policy": args.policy,
        "correct_unreachable": args.correct_unreachable,
    }


def _sustained_payload(
    args,
    *,
    execution_density: float | None = None,
    execution_seed: int | None = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "command": "start_sustained_batch",
        "duration_seconds": args.duration,
        "phase": args.phase,
        "require_fog": args.require_fog,
    }
    if args.phase_seed is not None:
        payload["phase_seed"] = args.phase_seed
    if getattr(args, "batch_id", None) is not None:
        payload["batch_id"] = args.batch_id
    if execution_density is not None:
        payload["execution_density"] = execution_density
    if execution_seed is not None:
        payload["execution_seed"] = execution_seed
    return payload


def _add_prepare_args(parser: argparse.ArgumentParser, *, require_density: bool = False) -> None:
    parser.add_argument(
        "--density",
        type=float,
        required=require_density,
        default=None if require_density else 1.0,
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--target-radius", type=int, default=12)
    parser.add_argument(
        "--policy",
        choices=["normal", "stress_stack_endpoint"],
        default="stress_stack_endpoint",
    )
    parser.add_argument(
        "--correct-unreachable",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Correct no-path targets to the nearest budget-reachable endpoint "
            "(default: enabled; use --no-correct-unreachable for raw no-path measurement)"
        ),
    )


def _add_sustained_args(
    parser: argparse.ArgumentParser,
    *,
    density_curve_defaults: bool = False,
) -> None:
    parser.add_argument("--duration", type=float, default=20.0)
    parser.add_argument(
        "--phase",
        choices=["synchronized", "staggered"],
        default="staggered" if density_curve_defaults else "synchronized",
        help=(
            "Temporal phase of segment boundaries. synchronized is the burst "
            "worst case; staggered is the steady-state density-curve workload."
        ),
    )
    parser.add_argument(
        "--phase-seed",
        type=int,
        default=None,
        help="Deterministic stagger seed (default: prepared batch seed)",
    )
    parser.add_argument(
        "--require-fog",
        choices=["on", "off", "any"],
        default="on" if density_curve_defaults else "any",
        help=(
            "Reject the run if the current FogOfWar state does not match. "
            "Formal density-curve points default to 'on'."
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="STAR Scale Test Harness control client"
    )
    parser.add_argument(
        "--socket",
        default="/tmp/star-scale.sock",
        help="Unix socket path (default: /tmp/star-scale.sock)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    prepare = sub.add_parser(
        "prepare", help="Generate random targets and batch-plan/correct moves"
    )
    _add_prepare_args(prepare)

    start = sub.add_parser(
        "start", help="Execute prepared MovePlans once with normal move side effects"
    )
    start.add_argument("--batch-id", type=int, default=None)

    sustained = sub.add_parser(
        "start-sustained",
        help=(
            "Run prepared paths as pure repeated motion for a fixed duration; "
            "no pathfinding, MP spend, recovery scheduling, or normal action stats"
        ),
    )
    sustained.add_argument("--batch-id", type=int, default=None)
    _add_sustained_args(sustained)

    sub.add_parser(
        "profile-snapshot",
        help="Read the current measurement-epoch profiler snapshot and guards",
    )

    density = sub.add_parser(
        "density-point",
        help=(
            "Warm up, prepare one common 5000-plan pool, start a nested execution "
            "subset, wait, and snapshot one formal Dynamic World point. Use a fresh "
            "ENV process for each point."
        ),
    )
    _add_prepare_args(density, require_density=True)
    _add_sustained_args(density, density_curve_defaults=True)
    density.add_argument(
        "--warmup",
        type=float,
        default=5.0,
        help="Seconds to let render/overscan caches settle before planning (default: 5)",
    )
    density.add_argument(
        "--sample-after",
        type=float,
        default=10.0,
        help="Seconds after kickoff before taking the profiler snapshot (default: 10)",
    )
    density.add_argument(
        "--output",
        default=None,
        help="Optional JSON output path for the combined prepare/start/snapshot result",
    )

    sub.add_parser("stop-sustained", help="Cancel the current sustained motion workload")
    sub.add_parser("status", help="Show prepared batch and current moving density")
    sub.add_parser("clear", help="Stop sustained motion and discard the prepared batch")
    return parser


def _print_and_optionally_write(data: Dict[str, Any], output: str | None = None) -> None:
    text = json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True)
    print(text)
    if output:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n", encoding="utf-8")


def _validate_snapshot(snapshot: Dict[str, Any], requested_density: float) -> Dict[str, Any]:
    guards = snapshot.get("guards", {}) if isinstance(snapshot, dict) else {}
    living = int(guards.get("living_units", 0) or 0)
    actual_density = float(guards.get("actual_density", 0.0) or 0.0)
    density_tolerance = max(1.0 / living, 1e-4) if living > 0 else 1e-4
    density_matches = abs(actual_density - requested_density) <= density_tolerance
    checks = {
        "snapshot_ok": bool(snapshot.get("ok")),
        "rolling_window_full": bool(snapshot.get("rolling_window_full")),
        "fog_matches_required": bool(guards.get("fog_matches_required")),
        "camera_unchanged": bool(guards.get("camera_unchanged")),
        "density_matches_requested": density_matches,
    }
    return {
        "valid": all(checks.values()),
        "checks": checks,
        "requested_density": requested_density,
        "actual_density": actual_density,
        "density_tolerance": density_tolerance,
    }


def _run_density_point(args) -> int:
    if not 0.0 <= args.density <= 1.0:
        _print_and_optionally_write(
            {"ok": False, "error": "density_out_of_range", "density": args.density},
            args.output,
        )
        return 1
    if args.warmup < 0.0:
        _print_and_optionally_write(
            {"ok": False, "error": "invalid_warmup", "warmup": args.warmup},
            args.output,
        )
        return 1
    if args.sample_after <= 0.0 or args.sample_after >= args.duration:
        _print_and_optionally_write(
            {
                "ok": False,
                "error": "invalid_sample_window",
                "message": "sample-after must be > 0 and < duration",
                "sample_after": args.sample_after,
                "duration": args.duration,
            },
            args.output,
        )
        return 1

    experiment = (
        "dynamic_world_density_curve_v1"
        if args.phase == "staggered"
        else "dynamic_world_burst_resilience_v1"
    )

    # Let one fresh window settle render/overscan/font caches before the common
    # planning burst. The later execution epoch reset excludes all warmup/planning.
    time.sleep(args.warmup)

    # Formal execution points all use the same full 5000-unit plan pool. The
    # measurement adapter then starts a deterministic nested prefix for the
    # requested execution density. Planning/targets therefore do not vary with d.
    prepare = request(args.socket, _prepare_payload(args, density_override=1.0))
    combined: Dict[str, Any] = {
        "ok": False,
        "experiment": experiment,
        "density": args.density,
        "warmup_seconds": args.warmup,
        "prepare": prepare,
    }
    if not prepare.get("ok"):
        _print_and_optionally_write(combined, args.output)
        return 1

    start = request(
        args.socket,
        _sustained_payload(
            args,
            execution_density=args.density,
            execution_seed=args.seed,
        ),
    )
    combined["start"] = start
    if not start.get("ok"):
        _print_and_optionally_write(combined, args.output)
        return 1

    time.sleep(args.sample_after)
    snapshot = request(args.socket, {"command": "profile_snapshot"})
    validation = _validate_snapshot(snapshot, args.density)
    combined["snapshot"] = snapshot
    combined["validation"] = validation
    combined["sample_after_seconds"] = args.sample_after
    combined["ok"] = bool(validation["valid"])
    _print_and_optionally_write(combined, args.output)
    return 0 if combined["ok"] else 1


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "density-point":
        return _run_density_point(args)

    if args.command == "prepare":
        payload = _prepare_payload(args)
    elif args.command == "start":
        payload = {"command": "start_prepared_batch"}
        if args.batch_id is not None:
            payload["batch_id"] = args.batch_id
    elif args.command == "start-sustained":
        payload = _sustained_payload(args)
    elif args.command == "profile-snapshot":
        payload = {"command": "profile_snapshot"}
    elif args.command == "stop-sustained":
        payload = {"command": "stop_sustained"}
    else:
        payload = {"command": args.command}

    response = request(args.socket, payload)
    _print_and_optionally_write(response)
    return 0 if response.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
