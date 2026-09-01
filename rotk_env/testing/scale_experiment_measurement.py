"""Formal measurement adapter for Scale Test Harness experiments.

The workload harness owns *what the world does*. This adapter owns *how a run is
measured*: experiment guards, deferred profiler epochs, and compact snapshots.
For formal density curves it also selects a deterministic nested subset from one
common full-world prepared plan pool, so execution density changes without
changing the planning workload or target set.

It is installed only by the optional window scale harness.
"""

from __future__ import annotations

import random
from dataclasses import replace
from typing import Any, Dict, Optional

from ..components import Camera, FogOfWar
from .profiler_epoch import (
    install_deferred_epoch_hook,
    measurement_epoch_pending,
    request_measurement_epoch,
)

_RELEVANT_SECTIONS = (
    "world_update",
    "AnimationSystem",
    "VisionSystem",
    "MapRenderSystem",
    "UnitRenderSystem",
    "MiniMapSystem",
    "render_engine",
    "unit_visible_cull",
    "unit_batch_prepare",
    "unit_animated_draw",
    "unit_static_draw",
    "minimap_unit_refresh",
    "input_event_pump",
    "display_present",
    "fps_limiter_wait",
)


def _camera_state(world) -> Optional[Dict[str, float]]:
    camera = world.get_singleton_component(Camera)
    if camera is None:
        return None
    return {
        "offset_x": float(camera.offset_x),
        "offset_y": float(camera.offset_y),
        "zoom": float(camera.zoom),
    }


def _fog_enabled(world) -> Optional[bool]:
    fog = world.get_singleton_component(FogOfWar)
    return bool(fog.enabled) if fog is not None else None


def _fog_requirement(value: object) -> str:
    normalized = str(value if value is not None else "any").strip().lower()
    if normalized not in {"on", "off", "any"}:
        raise ValueError("require_fog must be one of: on, off, any")
    return normalized


def _camera_equal(a: Optional[Dict[str, float]], b: Optional[Dict[str, float]]) -> bool:
    if a is None or b is None:
        return a is b
    return all(abs(float(a[key]) - float(b[key])) <= 1e-9 for key in a)


def _compact_slow_frame(snapshot: object) -> Optional[Dict[str, object]]:
    if not isinstance(snapshot, dict):
        return None
    sections = []
    for section in snapshot.get("top_sections", [])[:5]:
        if not isinstance(section, dict):
            continue
        sections.append(
            {
                "name": section.get("name"),
                "self_ms": section.get("self_ms"),
                "inclusive_ms": section.get("inclusive_ms"),
                "category": section.get("category"),
            }
        )
    metrics = snapshot.get("frame_metrics", {})
    keep_metrics = {}
    if isinstance(metrics, dict):
        for key in (
            "scale_active_moving_units",
            "scale_actual_density",
            "scale_sustained_phase",
            "fog_enabled",
            "fog_toggle_this_frame",
            "vision_dirty_units",
            "vision_units_changed",
            "vision_geometry_cache_hits",
            "vision_geometry_cache_misses",
            "visible_units",
            "animated_visible_units",
            "minimap_spatial_revision",
        ):
            if key in metrics:
                keep_metrics[key] = metrics[key]
    return {
        "frame_index": snapshot.get("frame_index"),
        "frame_ms": snapshot.get("frame_ms"),
        "active_ms": snapshot.get("active_ms"),
        "present_ms": snapshot.get("present_ms"),
        "fps_limiter_wait_ms": snapshot.get("fps_limiter_wait_ms"),
        "frame_metrics": keep_metrics,
        "top_sections": sections,
    }


def _section_subset(stats: Dict[str, Any]) -> Dict[str, Dict[str, object]]:
    result: Dict[str, Dict[str, object]] = {}
    sections = stats.get("sections", {})
    if not isinstance(sections, dict):
        return result
    for name in _RELEVANT_SECTIONS:
        raw = sections.get(name)
        if not isinstance(raw, dict):
            continue
        result[name] = {
            key: raw.get(key)
            for key in (
                "category",
                "self_ms",
                "inclusive_ms",
                "max_self_ms",
                "max_inclusive_ms",
                "frame_share_pct",
            )
        }
    return result


def install_scale_experiment_measurement(harness, world, profiler) -> bool:
    """Wrap one harness instance with formal measurement commands/guards."""
    if bool(getattr(harness, "_scale_measurement_installed", False)):
        return True
    if not install_deferred_epoch_hook(profiler):
        return False

    original_handle = harness.handle_command
    harness._scale_measurement_state = None

    def _snapshot() -> Dict[str, Any]:
        get_stats = getattr(profiler, "get_stats", None)
        if not callable(get_stats):
            return {"ok": False, "error": "profiler_snapshot_unavailable"}
        stats = get_stats()
        if not stats:
            return {
                "ok": False,
                "error": "measurement_epoch_not_ready",
                "epoch_pending": measurement_epoch_pending(profiler),
            }

        state = getattr(harness, "_scale_measurement_state", None) or {}
        camera_now = _camera_state(world)
        fog_now = _fog_enabled(world)
        required_fog = state.get("required_fog", "any")
        fog_matches = (
            True
            if required_fog == "any"
            else fog_now is (required_fog == "on")
        )
        camera_start = state.get("camera_start")
        active = harness._active_moving_units()
        living = len(harness._living_units())
        density_now = active / living if living else 0.0
        min_fps = float(stats.get("min_fps", 0.0) or 0.0)
        sample_window = int(getattr(profiler, "sample_window", 0) or 0)
        metadata = stats.get("metadata", {})
        context = {}
        if isinstance(metadata, dict):
            for key, value in metadata.items():
                if (
                    key.startswith("measurement_")
                    or key.startswith("scale_")
                    or key in {"scenario", "map_id", "map_size", "initial_units", "window"}
                ):
                    context[key] = value

        return {
            "ok": True,
            "measurement_epoch": context.get("measurement_epoch"),
            "measurement_epoch_serial": context.get("measurement_epoch_serial"),
            "sample_count": stats.get("sample_count", 0),
            "sample_window": sample_window,
            "rolling_window_full": (
                int(stats.get("sample_count", 0) or 0) >= sample_window
                if sample_window > 0
                else False
            ),
            "avg_fps": stats.get("avg_fps"),
            "min_fps": stats.get("min_fps"),
            "max_fps": stats.get("max_fps"),
            "avg_frame_ms": stats.get("avg_frame_ms"),
            "p50_frame_ms": stats.get("p50_frame_ms"),
            "p95_frame_ms": stats.get("p95_frame_ms"),
            "p99_frame_ms": stats.get("p99_frame_ms"),
            "max_frame_ms": (1000.0 / min_fps if min_fps > 0.0 else None),
            "active_ms": stats.get("active_ms"),
            "present_ms": stats.get("present_ms"),
            "fps_limiter_wait_ms": stats.get("fps_limiter_wait_ms"),
            "slow_frame_count": stats.get("slow_frame_count", 0),
            "worst_slow_frame": _compact_slow_frame(stats.get("worst_slow_frame")),
            "sections": _section_subset(stats),
            "guards": {
                "required_fog": required_fog,
                "fog_enabled": fog_now,
                "fog_matches_required": fog_matches,
                "camera_start": camera_start,
                "camera_current": camera_now,
                "camera_unchanged": _camera_equal(camera_start, camera_now),
                "active_moving_units": active,
                "living_units": living,
                "actual_density": density_now,
                "execution_selection_seed": state.get("execution_selection_seed"),
                "full_prepared_units": state.get("full_prepared_units"),
                "execution_requested_units": state.get("execution_requested_units"),
            },
            "context": context,
        }

    def _handle(command: Dict[str, Any]) -> Dict[str, Any]:
        op = str(command.get("command", "")).strip()
        if op == "profile_snapshot":
            return _snapshot()

        if op != "start_sustained_batch":
            return original_handle(command)

        required_fog = _fog_requirement(command.get("require_fog", "any"))
        fog_now = _fog_enabled(world)
        if required_fog != "any":
            required_value = required_fog == "on"
            if fog_now is None:
                return {
                    "ok": False,
                    "error": "fog_state_unavailable",
                    "required_fog": required_fog,
                }
            if fog_now is not required_value:
                return {
                    "ok": False,
                    "error": "fog_state_mismatch",
                    "required_fog": required_fog,
                    "fog_enabled": fog_now,
                }

        full_batch = harness.prepared
        if full_batch is None:
            return original_handle(command)

        execution_density = float(command.get("execution_density", full_batch.density))
        if not 0.0 <= execution_density <= 1.0:
            return {
                "ok": False,
                "error": "execution_density_out_of_range",
                "execution_density": execution_density,
            }
        execution_seed = int(command.get("execution_seed", full_batch.seed))
        desired_count = min(
            len(full_batch.plans),
            int(round(full_batch.living_units_at_prepare * execution_density)),
        )
        ordered_plans = list(full_batch.plans)
        random.Random(execution_seed).shuffle(ordered_plans)
        selected_plans = ordered_plans[:desired_count]
        execution_batch = replace(
            full_batch,
            density=execution_density,
            requested_units=desired_count,
            plans=selected_plans,
        )

        camera_start = _camera_state(world)
        harness.prepared = execution_batch
        try:
            result = original_handle(command)
        finally:
            # Keep the canonical full prepared pool available for status/debug.
            harness.prepared = full_batch
        if not result.get("ok"):
            return result

        phase = str(result.get("motion_phase", command.get("phase", "synchronized")))
        experiment_kind = (
            "dynamic_world_density_curve"
            if phase == "staggered"
            else "dynamic_world_burst_resilience"
        )
        epoch_name = (
            f"{experiment_kind}.density_{execution_density:.2f}.{phase}"
        )
        epoch_metadata = {
            "scale_experiment_kind": experiment_kind,
            "scale_measurement_density": round(execution_density, 4),
            "scale_measurement_phase": phase,
            "scale_measurement_fog": fog_now,
            "scale_measurement_camera_x": (
                camera_start["offset_x"] if camera_start is not None else None
            ),
            "scale_measurement_camera_y": (
                camera_start["offset_y"] if camera_start is not None else None
            ),
            "scale_measurement_camera_zoom": (
                camera_start["zoom"] if camera_start is not None else None
            ),
            "scale_measurement_required_fog": required_fog,
            "scale_measurement_batch": result.get("batch_id"),
            "scale_measurement_duration_seconds": result.get("duration_seconds"),
            "scale_execution_selection_seed": execution_seed,
            "scale_full_prepared_units": len(full_batch.plans),
            "scale_execution_requested_units": desired_count,
        }
        scheduled = request_measurement_epoch(
            profiler,
            epoch_name,
            **epoch_metadata,
        )
        harness._scale_measurement_state = {
            "epoch_name": epoch_name,
            "experiment_kind": experiment_kind,
            "required_fog": required_fog,
            "camera_start": camera_start,
            "fog_start": fog_now,
            "density": execution_density,
            "phase": phase,
            "execution_selection_seed": execution_seed,
            "full_prepared_units": len(full_batch.plans),
            "execution_requested_units": desired_count,
        }
        result.update(
            measurement_epoch=epoch_name,
            measurement_epoch_pending=scheduled,
            experiment_kind=experiment_kind,
            required_fog=required_fog,
            fog_enabled=fog_now,
            camera_start=camera_start,
            execution_density=execution_density,
            execution_selection_seed=execution_seed,
            full_prepared_units=len(full_batch.plans),
            execution_requested_units=desired_count,
        )
        return result

    harness.handle_command = _handle
    harness._scale_measurement_installed = True
    return True
