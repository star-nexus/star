#!/usr/bin/env python3
"""Repeated realtime-GC memory soak for STAR's Scale Test Harness.

The soak models the production policy we actually want: bounded realtime windows
with cyclic GC deferred, followed by explicit safe points where normal GC is
restored and a full collection is allowed. A priming cycle is excluded from the
reported baseline so one-time MovementAnimation/cache initialization is not
misclassified as a leak.
"""

from __future__ import annotations

import argparse
import json
import socket
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple


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


def _density_check(
    snapshot: Dict[str, Any], requested_density: float, max_missing_units: int
) -> Tuple[bool, Dict[str, Any]]:
    workload = snapshot.get("workload") or {}
    living = int(workload.get("living_units", 0) or 0)
    active = int(workload.get("active_moving_units", 0) or 0)
    expected = int(round(living * requested_density)) if living else 0
    delta = active - expected
    ok = living > 0 and abs(delta) <= max(0, int(max_missing_units))
    return ok, {
        "living_units": living,
        "active_moving_units": active,
        "expected_active_units": expected,
        "active_delta_units": delta,
        "max_missing_units": max(0, int(max_missing_units)),
        "actual_density": (active / living if living else 0.0),
    }


def _prepare(socket_path: str, args, seed: int) -> Dict[str, Any]:
    return request(
        socket_path,
        {
            "command": "prepare_random_moves",
            "density": 1.0,
            "seed": seed,
            "target_radius": args.target_radius,
            "policy": "stress_stack_endpoint",
            "correct_unreachable": True,
        },
    )


def _start(socket_path: str, args, batch_id: int, seed: int) -> Dict[str, Any]:
    return request(
        socket_path,
        {
            "command": "start_sustained_batch",
            "batch_id": batch_id,
            "duration_seconds": args.sustained_duration,
            "phase": args.phase,
            "phase_seed": args.seed,
            "require_fog": args.require_fog,
            "execution_density": args.density,
            "execution_seed": seed,
            "gc_policy": "realtime_defer",
        },
    )


def _policy_active(start: Dict[str, Any]) -> bool:
    return bool(
        start.get("ok")
        and start.get("gc_policy") == "realtime_defer"
        and bool(start.get("gc_policy_active"))
        and not bool(start.get("gc_automatic_enabled"))
    )


def _compact_prepare(prepare: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "ok": prepare.get("ok"),
        "batch_id": prepare.get("batch_id"),
        "prepared_units": prepare.get("prepared_units"),
        "batch_planning_ms": prepare.get("batch_planning_ms"),
    }


def _compact_start(start: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "ok": start.get("ok"),
        "accepted_units": start.get("accepted_units"),
        "actual_density": start.get("actual_density"),
        "gc_policy": start.get("gc_policy"),
        "gc_policy_active": start.get("gc_policy_active"),
        "gc_automatic_enabled": start.get("gc_automatic_enabled"),
        "gc_full_collect_ms": start.get("gc_full_collect_ms"),
    }


def _summary(result: Dict[str, Any]) -> Dict[str, Any]:
    cycles = result.get("cycles", [])
    baseline = result.get("baseline_collect", {}).get("after", {})
    baseline_memory = baseline.get("memory", {})
    baseline_gc = baseline.get("gc", {})
    baseline_world = baseline.get("world", {})
    baseline_vision = baseline.get("vision", {})

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
    final_vision = final.get("vision", {})
    deferred_vision_sizes = [
        int(item.get("vision", {}).get("geometry_cache_size", 0)) for item in deferred
    ]

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
        "vision_geometry_cache_capacity": final_vision.get(
            "geometry_cache_capacity", baseline_vision.get("geometry_cache_capacity")
        ),
        "baseline_vision_geometry_cache_size": baseline_vision.get(
            "geometry_cache_size"
        ),
        "final_vision_geometry_cache_size": final_vision.get("geometry_cache_size"),
        "peak_deferred_vision_geometry_cache_size": (
            max(deferred_vision_sizes) if deferred_vision_sizes else None
        ),
        "final_vision_geometry_cache_evictions": final_vision.get(
            "geometry_cache_evictions"
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
    parser.add_argument("--priming-realtime-seconds", type=float, default=15.0)
    parser.add_argument("--sustained-duration", type=float, default=20.0)
    parser.add_argument("--warmup", type=float, default=5.0)
    parser.add_argument("--density", type=float, default=1.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--target-radius", type=int, default=12)
    parser.add_argument(
        "--max-missing-moving-units",
        type=int,
        default=10,
        help="Allowed active-unit delta from requested density during soak (default: 10)",
    )
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
    if args.priming_realtime_seconds <= 0.0:
        raise SystemExit("--priming-realtime-seconds must be > 0")
    if args.sustained_duration <= max(
        args.cycle_realtime_seconds, args.priming_realtime_seconds
    ):
        raise SystemExit(
            "--sustained-duration must exceed both cycle and priming realtime seconds"
        )
    if not 0.0 <= args.density <= 1.0:
        raise SystemExit("--density must be within [0, 1]")
    if args.max_missing_moving_units < 0:
        raise SystemExit("--max-missing-moving-units must be >= 0")

    result: Dict[str, Any] = {
        "ok": False,
        "experiment": "realtime_gc_memory_soak_v2",
        "config": {
            "realtime_seconds": args.realtime_seconds,
            "cycle_realtime_seconds": args.cycle_realtime_seconds,
            "priming_realtime_seconds": args.priming_realtime_seconds,
            "sustained_duration": args.sustained_duration,
            "density": args.density,
            "seed": args.seed,
            "target_radius": args.target_radius,
            "max_missing_moving_units": args.max_missing_moving_units,
            "phase": args.phase,
            "require_fog": args.require_fog,
            "gc_policy": "realtime_defer",
        },
        "cycles": [],
    }

    try:
        time.sleep(max(0.0, args.warmup))

        # Prime one representative realtime window before defining the baseline.
        # This absorbs one-time MovementAnimation attachment and cold cache growth.
        priming_prepare = _prepare(args.socket, args, args.seed)
        priming: Dict[str, Any] = {"prepare": _compact_prepare(priming_prepare)}
        if not priming_prepare.get("ok"):
            priming["ok"] = False
            priming["error"] = "prepare_failed"
            result["priming"] = priming
            _write(output, result)
            return 1

        priming_start = _start(
            args.socket, args, int(priming_prepare["batch_id"]), args.seed
        )
        priming["start"] = _compact_start(priming_start)
        if not _policy_active(priming_start):
            priming["ok"] = False
            priming["error"] = "realtime_gc_policy_not_active"
            result["priming"] = priming
            _write(output, result)
            return 1

        time.sleep(args.priming_realtime_seconds)
        priming_deferred = request(args.socket, {"command": "memory_snapshot"})
        priming["deferred"] = priming_deferred
        priming_density_ok, priming_density = _density_check(
            priming_deferred, args.density, args.max_missing_moving_units
        )
        priming["density_check"] = priming_density
        priming_policy = priming_deferred.get("gc_policy") or {}
        if not (
            priming_deferred.get("ok")
            and bool(priming_policy.get("active"))
            and not bool(priming_policy.get("automatic_gc_enabled"))
            and priming_density_ok
        ):
            priming["ok"] = False
            priming["error"] = "invalid_deferred_snapshot"
            result["priming"] = priming
            request(args.socket, {"command": "stop_sustained"})
            _write(output, result)
            return 1

        priming_stop = request(args.socket, {"command": "stop_sustained"})
        priming_collect = request(args.socket, {"command": "safe_gc_collect"})
        priming["stop"] = priming_stop
        priming["post_collect"] = priming_collect
        priming["ok"] = bool(priming_stop.get("ok") and priming_collect.get("ok"))
        result["priming"] = priming
        if not priming["ok"]:
            result["error"] = "priming_safe_point_failed"
            _write(output, result)
            return 1

        # The post-priming safe point is the actual leak baseline.
        result["baseline_collect"] = priming_collect

        cumulative = 0.0
        cycle_index = 0
        while cumulative + 1e-9 < args.realtime_seconds:
            cycle_index += 1
            runtime = min(
                args.cycle_realtime_seconds,
                args.realtime_seconds - cumulative,
            )
            cycle_seed = args.seed + cycle_index

            prepare = _prepare(args.socket, args, cycle_seed)
            cycle: Dict[str, Any] = {
                "cycle": cycle_index,
                "seed": cycle_seed,
                "realtime_seconds": round(runtime, 3),
                "prepare": _compact_prepare(prepare),
            }
            if not prepare.get("ok"):
                cycle["ok"] = False
                cycle["error"] = "prepare_failed"
                result["cycles"].append(cycle)
                break

            start = _start(args.socket, args, int(prepare["batch_id"]), cycle_seed)
            cycle["start"] = _compact_start(start)
            if not _policy_active(start):
                cycle["ok"] = False
                cycle["error"] = "realtime_gc_policy_not_active"
                result["cycles"].append(cycle)
                break

            time.sleep(runtime)
            deferred = request(args.socket, {"command": "memory_snapshot"})
            cycle["deferred"] = deferred
            policy_state = deferred.get("gc_policy") or {}
            density_ok, density_check = _density_check(
                deferred, args.density, args.max_missing_moving_units
            )
            cycle["density_check"] = density_check
            if not (
                deferred.get("ok")
                and bool(policy_state.get("active"))
                and not bool(policy_state.get("automatic_gc_enabled"))
                and density_ok
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
            vision = after.get("vision", {})
            cache_size = vision.get("geometry_cache_size", "?")
            cache_capacity = vision.get("geometry_cache_capacity", "?")
            print(
                f"[GC soak] cycle={cycle_index} realtime={cumulative:.1f}/{args.realtime_seconds:.1f}s "
                f"deferred_rss={deferred['memory']['rss_mb']:.1f}MB "
                f"post_gc_rss={after['memory']['rss_mb']:.1f}MB "
                f"tracked={after['gc']['tracked_objects']} "
                f"vision_cache={cache_size}/{cache_capacity} "
                f"collected={post_collect['collected']}"
            )

        result["summary"] = _summary(result)
        result["ok"] = (
            bool(result["cycles"])
            and all(cycle.get("ok") for cycle in result["cycles"])
            and result["summary"]["realtime_seconds_completed"]
            >= args.realtime_seconds - 1e-6
        )
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
