"""Safe-point memory diagnostics for repeated realtime GC-defer phases.

This module is test-harness only. It never samples memory from the frame hot loop.
The driver asks for snapshots at explicit phase boundaries so the measurement
itself does not contaminate realtime latency.
"""

from __future__ import annotations

import gc
import time
from typing import Any, Dict

from framework.utils.process_memory import process_memory_snapshot


def _gc_stats() -> Dict[str, Any]:
    generations = gc.get_stats()
    return {
        "enabled": bool(gc.isenabled()),
        "count": [int(value) for value in gc.get_count()],
        "tracked_objects": len(gc.get_objects()),
        "generations": [
            {
                "collections": int(item.get("collections", 0)),
                "collected": int(item.get("collected", 0)),
                "uncollectable": int(item.get("uncollectable", 0)),
            }
            for item in generations
        ],
    }


def _world_stats(world) -> Dict[str, Any]:
    entities = getattr(world, "entities", {})
    component_index = getattr(world, "_component_to_entities", {})
    query_cache = getattr(world, "_query_cache", {})
    singleton_components = getattr(world, "_singleton_components", {})
    component_instances = 0
    if isinstance(entities, dict):
        component_instances = sum(
            len(components)
            for components in entities.values()
            if isinstance(components, dict)
        )
    return {
        "entities": len(entities) if hasattr(entities, "__len__") else 0,
        "component_instances": int(component_instances),
        "component_types": len(component_index) if hasattr(component_index, "__len__") else 0,
        "singleton_components": (
            len(singleton_components)
            if hasattr(singleton_components, "__len__")
            else 0
        ),
        "query_cache_entries": len(query_cache) if hasattr(query_cache, "__len__") else 0,
    }


def _workload_stats(harness) -> Dict[str, Any]:
    try:
        active = int(harness._active_moving_units())
        living = len(harness._living_units())
    except Exception:
        active = 0
        living = 0
    return {
        "active_moving_units": active,
        "living_units": living,
        "density": (active / living if living else 0.0),
    }


def _vision_stats(world) -> Dict[str, Any]:
    """Find the mounted Vision system without importing window/base variants."""
    for system in getattr(world, "systems", ()):  # pragma: no branch - tiny list
        get_stats = getattr(system, "get_stats", None)
        if not callable(get_stats):
            continue
        try:
            stats = get_stats()
        except Exception:
            continue
        if not isinstance(stats, dict) or "geometry_cache_size" not in stats:
            continue
        return {
            "geometry_cache_size": int(stats.get("geometry_cache_size", 0)),
            "geometry_cache_capacity": int(stats.get("geometry_cache_capacity", 0)),
            "geometry_cache_hits": int(stats.get("geometry_cache_hits", 0)),
            "geometry_cache_misses": int(stats.get("geometry_cache_misses", 0)),
            "geometry_cache_evictions": int(stats.get("geometry_cache_evictions", 0)),
        }
    return {}


def _snapshot(harness, world) -> Dict[str, Any]:
    policy = getattr(harness, "_realtime_gc_policy", None)
    if policy is not None:
        policy.tick()
        policy_state = policy.snapshot()
    else:
        policy_state = None
    return {
        "memory": process_memory_snapshot(),
        "gc": _gc_stats(),
        "world": _world_stats(world),
        "workload": _workload_stats(harness),
        "vision": _vision_stats(world),
        "gc_policy": policy_state,
    }


def install_scale_memory_soak(harness, world) -> bool:
    """Add read-only memory probes and an explicit safe-point full collection."""
    if bool(getattr(harness, "_scale_memory_soak_installed", False)):
        return True

    original_handle = harness.handle_command

    def _handle(command: Dict[str, Any]) -> Dict[str, Any]:
        op = str(command.get("command", "")).strip()
        if op == "memory_snapshot":
            return {"ok": True, **_snapshot(harness, world)}

        if op == "safe_gc_collect":
            policy = getattr(harness, "_realtime_gc_policy", None)
            if policy is not None:
                policy.tick()
                state = policy.snapshot()
                if bool(state.get("active")):
                    return {
                        "ok": False,
                        "error": "realtime_gc_policy_active",
                        "gc_policy": state,
                    }

            before = _snapshot(harness, world)
            t0 = time.perf_counter_ns()
            collected = int(gc.collect(2))
            collect_ms = (time.perf_counter_ns() - t0) / 1_000_000.0
            after = _snapshot(harness, world)
            return {
                "ok": True,
                "collected": collected,
                "collect_ms": round(collect_ms, 6),
                "before": before,
                "after": after,
                "rss_delta_mb": round(
                    float(after["memory"]["rss_mb"])
                    - float(before["memory"]["rss_mb"]),
                    3,
                ),
                "tracked_objects_delta": (
                    int(after["gc"]["tracked_objects"])
                    - int(before["gc"]["tracked_objects"])
                ),
            }

        return original_handle(command)

    harness.handle_command = _handle
    harness._scale_memory_soak_installed = True
    return True


__all__ = ["install_scale_memory_soak"]