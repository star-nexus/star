"""Measurement overlay for bounded Vision geometry-cache working-set ablations.

This adapter is test-harness only. It records Vision cache counters and process
RSS at explicit control-plane boundaries, never from the realtime frame hot loop.
Each formal point should use a fresh window process with a fixed cache capacity.
"""

from __future__ import annotations

from typing import Any, Dict

from framework.utils.process_memory import process_memory_snapshot

from .scale_memory_soak import _vision_stats


def _counter_delta(start: Dict[str, Any], current: Dict[str, Any], key: str) -> int:
    return int(current.get(key, 0)) - int(start.get(key, 0))


def _vision_delta(start: Dict[str, Any], current: Dict[str, Any]) -> Dict[str, Any]:
    hits = _counter_delta(start, current, "geometry_cache_hits")
    misses = _counter_delta(start, current, "geometry_cache_misses")
    evictions = _counter_delta(start, current, "geometry_cache_evictions")
    lookups = hits + misses
    return {
        "geometry_cache_hits": hits,
        "geometry_cache_misses": misses,
        "geometry_cache_evictions": evictions,
        "geometry_cache_lookups": lookups,
        "geometry_hit_rate": (hits / lookups if lookups > 0 else 0.0),
        "geometry_cache_size_start": int(start.get("geometry_cache_size", 0)),
        "geometry_cache_size_current": int(current.get("geometry_cache_size", 0)),
        "geometry_cache_capacity": int(current.get("geometry_cache_capacity", 0)),
    }


def install_scale_vision_cache_ablation(harness, world) -> bool:
    """Expose measurement-epoch Vision cache deltas and RSS in profile snapshots."""
    if bool(getattr(harness, "_scale_vision_cache_ablation_installed", False)):
        return True

    original_handle = harness.handle_command
    harness._scale_vision_cache_measurement_start = None

    def _handle(command: Dict[str, Any]) -> Dict[str, Any]:
        op = str(command.get("command", "")).strip()

        if op == "start_sustained_batch":
            result = original_handle(command)
            if not result.get("ok"):
                return result

            # The base measurement reset is still pending until the next frame,
            # so these explicit probes are outside the realtime measurement epoch.
            start = {
                "vision": _vision_stats(world),
                "memory": process_memory_snapshot(),
            }
            harness._scale_vision_cache_measurement_start = start
            result["vision_cache_start"] = start["vision"]
            result["memory_start"] = start["memory"]
            return result

        if op == "profile_snapshot":
            # Ask the existing measurement stack for its frozen profiler result
            # first. The RSS probe below therefore cannot contaminate that window.
            result = original_handle(command)
            if not result.get("ok"):
                return result

            current_vision = _vision_stats(world)
            current_memory = process_memory_snapshot()
            start = getattr(harness, "_scale_vision_cache_measurement_start", None)
            start = start if isinstance(start, dict) else {}
            start_vision = start.get("vision", {}) if isinstance(start, dict) else {}
            start_memory = start.get("memory", {}) if isinstance(start, dict) else {}

            delta = _vision_delta(start_vision, current_vision)
            capacity_unchanged = (
                int(start_vision.get("geometry_cache_capacity", 0))
                == int(current_vision.get("geometry_cache_capacity", 0))
            )
            result["vision_cache"] = {
                "start": start_vision,
                "current": current_vision,
                "delta": delta,
            }
            result["memory"] = {
                "start": start_memory,
                "current": current_memory,
                "rss_growth_mb": round(
                    float(current_memory.get("rss_mb", 0.0))
                    - float(start_memory.get("rss_mb", 0.0)),
                    3,
                ),
            }
            guards = result.setdefault("guards", {})
            guards["vision_cache_capacity_unchanged"] = capacity_unchanged
            context = result.setdefault("context", {})
            context["scale_vision_geometry_cache_capacity"] = int(
                current_vision.get("geometry_cache_capacity", 0)
            )
            if not capacity_unchanged:
                result["ok"] = False
                result["error"] = "vision_cache_capacity_changed"
            return result

        if op in {"stop_sustained", "clear"}:
            result = original_handle(command)
            harness._scale_vision_cache_measurement_start = None
            return result

        return original_handle(command)

    harness.handle_command = _handle
    harness._scale_vision_cache_ablation_installed = True
    return True


__all__ = ["install_scale_vision_cache_ablation"]
