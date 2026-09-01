#!/usr/bin/env python3
"""Repeated realtime-GC memory soak for STAR's Scale Test Harness.

The soak intentionally keeps each realtime window bounded. Every cycle:
1. plans a fresh 5000-unit workload at a safe point;
2. runs a standard staggered realtime window with cyclic GC deferred;
3. samples RSS/tracked objects while GC is still deferred;
4. explicitly stops motion, restoring automatic GC;
5. performs a full collection at that safe point and records the post-collect state.

This tests the production policy we actually want, rather than constructing one
artificial multi-million-node animation path for a 10-minute single phase.
"""

from __future__ import annotations

import argparse
import json
import math
import socket
import sys
import time
from pathlib import Path
from typing import Any, Dict, List


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
        return json.loads(bytes(chunks).split(b"\n", 1)[0].decode("utf-8"))
    finally:
        client.close()


def _write(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)


def _slope_per_hour(xs: List[float], ys: List[float]) -> float:
    if len(xs) < 2 or len(xs) != len(ys):
        return 0.0
    x_mean = sum(xs) / len(xs)
    y_mean = sum(ys) / len(ys)
    denom = sum((x - x_mean) ** 2 for x in xs)
    if denom <= 0.0:
        return 0.0
    slope_per_second = sum(
        (x - x_mean) * (y - y_mean) for x, y in zip(xs, ys)
    ) / denom
    return slope_per_second * 3600.0


def _summary(result: Dict[str, Any]) -> Dict[str, Any]:
    cycles = result.get("cycles", [])
    baseline = result.get("baseline_collect", {}).get("after", {})
    baseline_memory = baseline.get("memory", {})
    baseline_gc = baseline.get("gc", {})
    baseline_world = baseline.get("world", {})

    completed = [cycle for cycle in cycles if cycle.get("ok")]
    post = [cycle["post_collect"]["after"] for cycle in completed]
    deferred = [cycle["deferred"] for cycle in completed]
    xs = [float(cycle.get("cumulative_realtime_seconds", 0.0)) for cycle in completed]
    post_rss = [float(item["memory"]["rss_mb"]) for item in post]
    post_tracked = [float(item["gc"]["tracked_objects"]) for item in post]

    final = post[-1] if post else baseline
    final_memory = final.get("memory", {})
    final_gc = final.get("gc", {})
    final_world = final.get("world", {})

    return {
        "cycles_completed": len(completed),
        "realtime_seconds_completed": round(
            sum(float(cycle.get("realtime_seconds", 0.0)) for cycle in completed), 3
        ),
        "baseline_rss_mb": baseline_memory.get("rss_mb"),
        "final_post_collect_rss_mb": final_memory.get("rss_mb"),
        "post_collect_rss_growth_mb": round(
            float(final_memory.get("rss_mb", 0.0))
            - float(baseline_memory.get("rss_mb", 0.0)),
            3,
        ),
        "post_collect_rss_slope_mb_per_hour": round(
            _slope_per_hour(xs, post_rss), 3
        ),
        "peak_deferred_rss_mb": (
            max(float(item["memory"]["rss_mb"]) for item in deferred)
            if deferred
            else None
        ),
        "baseline_tracked_objects": baseline_gc.get("tracked_objects"),
        "final_post_collect_tracked_objects": final_gc.get("tracked_objects"),
        "post_collect_tracked_objects_growth": (
            int(final_gc.get("tracked_objects", 0))
            - int(baseline_gc.get("tracked_objects", 0))
        ),
        "post_collect_tracked_objects_slope_per_hour": round(
            _slope_per_hour(xs, post_tracked), 3
        ),
        "entity_growth": (
            int(final_world.get("entities", 0))
            - int(baseline_world.get("entities", 0))
        ),
        "component_instance_growth": (
            int(final_world.get("component_instances", 0))
            - int(baseline_world.get("component_instances", 0))
        ),
        "max_safe_collect_ms": (
            max(float(cycle["post_collect"]["collect_ms"]) for cycle in completed)
            if completed
            else None
        ),
        "total_safe_collect_collected": sum(
            int(cycle["post_collect"]["collected"]) for cycle in completed
        ),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Repeated bounded realtime-GC memory soak for STAR"
    )
    parser.add_argument("--socket", default="/tmp/star-scale.sock")
    parser.add_argument("--realtime-seconds", type=float, default=600.0)
    parser.add_argument("--cycle-realtime-seconds", type=float, default=15.0)
    parser.add_argument("--sustained-duration", type=float, default=20.0)
    parser.add_argument("--warmup", type=float, default=5.0)
    parser.add_argument("--density", type=float, default=1.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--target-radius", type=int, default=12)
    parser.add_argument(
        "--phase", choices=["synchronized", "staggered"], default="staggered"
    )
    parser.add_argument(
        "--require-fog", choices=["on", "off", "any"], default="on"
    )
    parser.add_argument(
        "--output", default="results/gc-soak/realtime-gc-soak.json"
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    output = Path(args.output)

    if args.realtime_seconds <= 0.0:
        raise SystemExit("--realtime-seconds must be > 0")
    if args.cycle_realtime_seconds <= 0.0:
        raise SystemExit("--cycle-realtime-seconds must be > 0")
    if args.sustained_duration <= args.cycle_realtime_seconds:
        raise SystemExit("--sustained-duration must exceed --cycle-realtime-seconds")
    if not 0.0 <= args.density <= 1.0:
        raise SystemExit("--density must be within [0, 1]")

    result: Dict[str, Any] = {
        "ok": False,
        "experiment": "realtime_gc_memory_soak_v1",
        "config": {
            "realtime_seconds": args.realtime_seconds,
            "cycle_realtime_seconds": args.cycle_realtime_seconds,
            "sustained_duration": args.sustained_duration,
            "density": args.density,
            "seed": args.seed,
            "target_radius": args.target_radius,
            "phase": args.phase,
            "require_fog": args.require_fog,
            "gc_policy": "realtime_defer",
        },
        "cycles": [],
    }

    try:
        time.sleep(max(0.0, args.warmup))
        baseline = request(args.socket, {"command": "safe_gc_collect"})
        result["baseline_collect"] = baseline
        if not baseline.get("ok"):
            result["error"] = "baseline_collect_failed"
            _write(output, result)
            return 1

        cumulative = 0.0
        cycle_index = 0
        while cumulative + 1e-9 < args.realtime_seconds:
            cycle_index += 1
            runtime = min(
                args.cycle_realtime_seconds,
                args.realtime_seconds - cumulative,
            )

            prepare = request(
                args.socket,
                {
                    "command": "prepare_random_moves",
                    "density": 1.0,
                    "seed": args.seed + cycle_index - 1,
                    "target_radius": args.target_radius,
                    "policy": "stress_stack_endpoint",
                    "correct_unreachable": True,
                },
            )
            cycle: Dict[str, Any] = {
                "cycle": cycle_index,
                "realtime_seconds": round(runtime, 3),
                "prepare": {
                    "ok": prepare.get("ok"),
                    "batch_id": prepare.get("batch_id"),
                    "prepared_units": prepare.get("prepared_units"),
                    "batch_planning_ms": prepare.get("batch_planning_ms"),
                },
            }
            if not prepare.get("ok"):
                cycle["ok"] = False
                cycle["error"] = "prepare_failed"
                result["cycles"].append(cycle)
                break

            start = request(
                args.socket,
                {
                    "command": "start_sustained_batch",
                    "batch_id": prepare.get("batch_id"),
                    "duration_seconds": args.sustained_duration,
                    "phase": args.phase,
                    "phase_seed": args.seed,
                    "require_fog": args.require_fog,
                    "execution_density": args.density,
                    "execution_seed": args.seed,
                    "gc_policy": "realtime_defer",
                },
            )
            cycle["start"] = {
                "ok": start.get("ok"),
                "accepted_units": start.get("accepted_units"),
                "actual_density": start.get("actual_density"),
                "gc_policy": start.get("gc_policy"),
                "gc_policy_active": start.get("gc_policy_active"),
                "gc_automatic_enabled": start.get("gc_automatic_enabled"),
                "gc_full_collect_ms": start.get("gc_full_collect_ms"),
            }
            if not (
                start.get("ok")
                and start.get("gc_policy") == "realtime_defer"
                and bool(start.get("gc_policy_active"))
                and not bool(start.get("gc_automatic_enabled"))
            ):
                cycle["ok"] = False
                cycle["error"] = "realtime_gc_policy_not_active"
                result["cycles"].append(cycle)
                break

            time.sleep(runtime)
            deferred = request(args.socket, {"command": "memory_snapshot"})
            cycle["deferred"] = deferred
            policy_state = deferred.get("gc_policy") or {}
            workload = deferred.get("workload") or {}
            living = int(workload.get("living_units", 0) or 0)
            tolerance = max(1.0 / living, 1e-4) if living else 1e-4
            density_matches = abs(
                float(workload.get("density", 0.0)) - args.density
            ) <= tolerance
            if not (
                deferred.get("ok")
                and bool(policy_state.get("active"))
                and not bool(policy_state.get("automatic_gc_enabled"))
                and density_matches
            ):
                cycle["ok"] = False
                cycle["error"] = "invalid_deferred_snapshot"
                result["cycles"].append(cycle)
                request(args.socket, {"command": "stop_sustained"})
                break

            stop = request(args.socket, {"command": "stop_sustained"})
            cycle["stop"] = stop
            post_collect = request(args.socket, {"command": "safe_gc_collect"})
            cycle["post_collect"] = post_collect
            if not (stop.get("ok") and post_collect.get("ok")):
                cycle["ok"] = False
                cycle["error"] = "safe_point_failed"
                result["cycles"].append(cycle)
                break

            cumulative += runtime
            cycle["cumulative_realtime_seconds"] = round(cumulative, 3)
            cycle["ok"] = True
            result["cycles"].append(cycle)
            result["summary"] = _summary(result)
            _write(output, result)

            after = post_collect["after"]
            print(
                f"[GC soak] cycle={cycle_index} realtime={cumulative:.1f}/{args.realtime_seconds:.1f}s "
                f"deferred_rss={deferred['memory']['rss_mb']:.1f}MB "
                f"post_gc_rss={after['memory']['rss_mb']:.1f}MB "
                f"tracked={after['gc']['tracked_objects']} collected={post_collect['collected']}"
            )

        result["summary"] = _summary(result)
        result["ok"] = bool(result["cycles"]) and all(
            cycle.get("ok") for cycle in result["cycles"]
        ) and result["summary"]["realtime_seconds_completed"] >= args.realtime_seconds - 1e-6
        if not result["ok"] and "error" not in result:
            result["error"] = "soak_incomplete"
        _write(output, result)
        return 0 if result["ok"] else 1

    except KeyboardInterrupt:
        try:
            request(args.socket, {"command": "stop_sustained"})
        except Exception:
            pass
        result["interrupted"] = True
        result["summary"] = _summary(result)
        _write(output, result)
        return 130
    except Exception as exc:
        try:
            request(args.socket, {"command": "stop_sustained"})
        except Exception:
            pass
        result["error"] = type(exc).__name__
        result["message"] = str(exc)
        result["summary"] = _summary(result)
        _write(output, result)
        raise


if __name__ == "__main__":
    sys.exit(main())
