"""Continuous camera-only attribution for Fog full-surface rebuilds.

Installed only with the Scale Test Harness. The workload keeps units stationary,
requires Fog to be enabled, drives the production Camera singleton on the main
thread, and restores the exact starting camera state on stop or cleanup.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

from ..components import Camera, FogOfWar
from . import scale_experiment_measurement_base as _measurement_base
from .profiler_epoch import request_measurement_epoch

EXPERIMENT_ID = "2026-09-camera-fog-full-rebuild"
MODES = {"stationary", "short_pan", "long_pan", "zoom"}
GEOMETRY_PATHS = {"fused", "legacy"}
PAN_TARGETS = {"short_pan": 128.0, "long_pan": 320.0}
ZOOM_TARGET_DELTA = 0.5

for _section in (
    "fog_full_build_surface_allocate",
    "fog_full_build_tile_loop",
):
    if _section not in _measurement_base._RELEVANT_SECTIONS:
        _measurement_base._RELEVANT_SECTIONS += (_section,)


def measure_polygon_timer_overhead(samples: int = 20_000) -> Dict[str, object]:
    """Measure the gated perf-counter pair used around polygon calls."""
    return _measure_direct_timer_overhead(samples)


def measure_hex_corners_timer_overhead(samples: int = 20_000) -> Dict[str, object]:
    """Measure the gated perf-counter pair used around ``get_hex_corners``."""
    return _measure_direct_timer_overhead(samples)


def measure_geometry_prepare_timer_overhead(
    samples: int = 20_000,
) -> Dict[str, object]:
    """Measure the gated perf-counter pair used around geometry preparation."""
    return _measure_direct_timer_overhead(samples)


def measure_screen_transform_timer_overhead(
    samples: int = 20_000,
) -> Dict[str, object]:
    """Measure the gated perf-counter pair used around point conversion."""
    return _measure_direct_timer_overhead(samples)


def measure_bounds_rect_timer_overhead(samples: int = 20_000) -> Dict[str, object]:
    """Measure the gated perf-counter pair used around bounds and Rect."""
    return _measure_direct_timer_overhead(samples)


def _measure_direct_timer_overhead(samples: int) -> Dict[str, object]:
    samples = max(1, int(samples))
    measured_ns = 0
    wall_start_ns = time.perf_counter_ns()
    for _ in range(samples):
        start_ns = time.perf_counter_ns()
        measured_ns += time.perf_counter_ns() - start_ns
    wall_ns = time.perf_counter_ns() - wall_start_ns
    return {
        "samples": samples,
        "wall_time_ns": wall_ns,
        "wall_ns_per_sample": wall_ns / samples,
        "measured_interval_ns": measured_ns,
        "measured_interval_ns_per_sample": measured_ns / samples,
    }


def _counter_delta(end: object, start: object) -> Dict[str, int]:
    end_counts = end if isinstance(end, dict) else {}
    start_counts = start if isinstance(start, dict) else {}
    return {
        str(key): int(end_counts.get(key, 0)) - int(start_counts.get(key, 0))
        for key in sorted(set(end_counts) | set(start_counts), key=str)
        if int(end_counts.get(key, 0)) - int(start_counts.get(key, 0)) != 0
    }


def _find_fog_presenter(world):
    for system in getattr(world, "systems", ()):
        presenter = getattr(system, "_fog_presenter", None)
        if presenter is not None and callable(
            getattr(presenter, "diagnostic_snapshot", None)
        ):
            return presenter
    return None


def install_fog_camera_attribution(harness, world, profiler) -> bool:
    """Add start/status/stop commands for the Fog camera attribution run."""
    if bool(getattr(harness, "_fog_camera_attribution_installed", False)):
        return True

    original_handle = harness.handle_command
    original_update = getattr(harness, "update", None)
    original_cleanup = getattr(harness, "cleanup", None)
    harness._fog_camera_attribution_state = None

    def _camera() -> Optional[Camera]:
        return world.get_singleton_component(Camera)

    def _moving_units() -> int:
        active = getattr(harness, "_active_moving_units", None)
        return int(active()) if callable(active) else 0

    def _publish_state(state: Dict[str, Any], changed: Dict[str, bool]) -> None:
        metric = getattr(profiler, "set_frame_metric", None)
        if callable(metric):
            metric("fog_camera_attribution_active", 1)
            metric("fog_camera_attribution_mode", state["mode"])
            metric("fog_camera_attribution_total_frames", state["total_frames"])
            metric("fog_camera_attribution_camera_changed", int(changed["camera"]))
            metric("fog_camera_attribution_offset_x_changed", int(changed["offset_x"]))
            metric("fog_camera_attribution_offset_y_changed", int(changed["offset_y"]))
            metric("fog_camera_attribution_zoom_changed", int(changed["zoom"]))

    def _start(command: Dict[str, Any]) -> Dict[str, Any]:
        if isinstance(getattr(harness, "_fog_camera_attribution_state", None), dict):
            return {"ok": False, "error": "fog_camera_attribution_already_active"}
        if isinstance(getattr(harness, "_scale_camera_stress_state", None), dict):
            return {"ok": False, "error": "terrain_camera_stress_active"}

        mode = str(command.get("mode", "")).strip().lower().replace("-", "_")
        if mode not in MODES:
            return {
                "ok": False,
                "error": "invalid_fog_camera_attribution_mode",
                "modes": sorted(MODES),
            }
        geometry_path = str(command.get("geometry_path", "fused")).strip().lower()
        if geometry_path not in GEOMETRY_PATHS:
            return {
                "ok": False,
                "error": "invalid_fog_geometry_path",
                "geometry_paths": sorted(GEOMETRY_PATHS),
            }
        camera = _camera()
        if camera is None:
            return {"ok": False, "error": "camera_unavailable"}
        fog = world.get_singleton_component(FogOfWar)
        if fog is None or not fog.enabled:
            return {"ok": False, "error": "fog_must_be_enabled"}
        active_units = _moving_units()
        if active_units:
            return {
                "ok": False,
                "error": "units_must_be_stationary",
                "active_moving_units": active_units,
            }
        presenter = _find_fog_presenter(world)
        if presenter is None:
            return {"ok": False, "error": "fog_presenter_unavailable"}
        if getattr(presenter, "surface", None) is None:
            return {"ok": False, "error": "fog_surface_uninitialized"}

        stationary_frames = max(1, int(command.get("stationary_frames", 120)))
        timer_samples = max(1, int(command.get("timer_sanity_samples", 20_000)))
        polygon_timing_enabled = bool(command.get("polygon_timing_enabled", True))
        hex_corners_timing_enabled = bool(
            command.get("hex_corners_timing_enabled", True)
        )
        geometry_prepare_timing_enabled = bool(
            command.get("geometry_prepare_timing_enabled", False)
        )
        screen_transform_timing_enabled = bool(
            command.get("screen_transform_timing_enabled", False)
        )
        bounds_rect_timing_enabled = bool(
            command.get("bounds_rect_timing_enabled", False)
        )
        presenter_before = presenter.diagnostic_snapshot()
        fused_transform_bounds_enabled_before = bool(
            presenter_before["fused_transform_bounds_enabled"]
        )
        start_camera = {
            "offset_x": float(camera.offset_x),
            "offset_y": float(camera.offset_y),
            "zoom": float(camera.zoom),
        }
        zoom_direction = 1.0 if camera.zoom <= 2.5 else -1.0
        presenter.set_full_build_attribution_enabled(
            polygon_timing_enabled, clear_events=True
        )
        presenter.set_hex_corners_attribution_enabled(
            hex_corners_timing_enabled
        )
        presenter.set_geometry_prepare_attribution_enabled(
            geometry_prepare_timing_enabled
        )
        presenter.set_screen_transform_attribution_enabled(
            screen_transform_timing_enabled
        )
        presenter.set_bounds_rect_attribution_enabled(bounds_rect_timing_enabled)
        presenter.set_fused_transform_bounds_enabled(geometry_path == "fused")
        start_snapshot = presenter.diagnostic_snapshot()
        state = {
            "active": True,
            "completed": False,
            "just_started": True,
            "mode": mode,
            "stationary_frames": stationary_frames,
            "total_frames": 0,
            "camera_changed_frames": 0,
            "offset_x_changed_frames": 0,
            "offset_y_changed_frames": 0,
            "zoom_changed_frames": 0,
            "start_camera": start_camera,
            "zoom_direction": zoom_direction,
            "fog_start": start_snapshot,
            "timer_sanity": measure_polygon_timer_overhead(timer_samples),
            "hex_corners_timer_sanity": measure_hex_corners_timer_overhead(
                timer_samples
            ),
            "geometry_prepare_timer_sanity": (
                measure_geometry_prepare_timer_overhead(timer_samples)
            ),
            "screen_transform_timer_sanity": (
                measure_screen_transform_timer_overhead(timer_samples)
            ),
            "bounds_rect_timer_sanity": measure_bounds_rect_timer_overhead(
                timer_samples
            ),
            "polygon_timing_enabled": polygon_timing_enabled,
            "hex_corners_timing_enabled": hex_corners_timing_enabled,
            "geometry_prepare_timing_enabled": geometry_prepare_timing_enabled,
            "screen_transform_timing_enabled": screen_transform_timing_enabled,
            "bounds_rect_timing_enabled": bounds_rect_timing_enabled,
            "geometry_path_requested": geometry_path,
            "geometry_path_effective": start_snapshot["geometry_path"],
            "fused_transform_bounds_enabled_before": (
                fused_transform_bounds_enabled_before
            ),
            "active_moving_units_start": active_units,
            "max_active_moving_units": active_units,
            "unit_movement_frames": 0,
            "fog_enabled_start": True,
            "fog_disabled_frames": 0,
            "aborted_reason": None,
        }
        harness._fog_camera_attribution_state = state

        epoch_name = f"fog_camera_attribution.{mode}"
        measurement_state = getattr(harness, "_scale_measurement_state", None)
        if not isinstance(measurement_state, dict):
            measurement_state = {}
            harness._scale_measurement_state = measurement_state
        measurement_state.update(
            epoch_name=epoch_name,
            experiment_kind=EXPERIMENT_ID,
            required_fog="on",
            camera_start=dict(start_camera),
        )
        scheduled = request_measurement_epoch(
            profiler,
            epoch_name,
            scale_experiment_kind=EXPERIMENT_ID,
            scale_fog_camera_attribution_mode=mode,
            scale_fog_camera_attribution_active=True,
            scale_fog_camera_start_x=start_camera["offset_x"],
            scale_fog_camera_start_y=start_camera["offset_y"],
            scale_fog_camera_start_zoom=start_camera["zoom"],
        )
        return {
            "ok": True,
            "experiment": EXPERIMENT_ID,
            "mode": mode,
            "measurement_epoch": epoch_name,
            "measurement_epoch_pending": scheduled,
            "camera_start": start_camera,
            "stationary_frames": stationary_frames if mode == "stationary" else None,
            "pan_target_pixels": PAN_TARGETS.get(mode),
            "zoom_target_delta": (
                zoom_direction * ZOOM_TARGET_DELTA if mode == "zoom" else None
            ),
            "fog_full_build_counter_start": start_snapshot["full_builds"],
            "timer_sanity": state["timer_sanity"],
            "hex_corners_timer_sanity": state["hex_corners_timer_sanity"],
            "geometry_prepare_timer_sanity": state[
                "geometry_prepare_timer_sanity"
            ],
            "screen_transform_timer_sanity": state[
                "screen_transform_timer_sanity"
            ],
            "bounds_rect_timer_sanity": state["bounds_rect_timer_sanity"],
            "polygon_timing_enabled": state["polygon_timing_enabled"],
            "hex_corners_timing_enabled": state["hex_corners_timing_enabled"],
            "geometry_prepare_timing_enabled": state[
                "geometry_prepare_timing_enabled"
            ],
            "screen_transform_timing_enabled": state[
                "screen_transform_timing_enabled"
            ],
            "bounds_rect_timing_enabled": state["bounds_rect_timing_enabled"],
            "geometry_path_requested": state["geometry_path_requested"],
            "geometry_path_effective": state["geometry_path_effective"],
        }

    def _finish_result(
        state: Dict[str, Any], end_snapshot: Dict[str, object]
    ) -> Dict[str, Any]:
        start_snapshot = state["fog_start"]
        start_builds = int(start_snapshot["full_builds"])
        end_builds = int(end_snapshot["full_builds"])
        build_delta = end_builds - start_builds
        camera_changed_frames = int(state["camera_changed_frames"])
        cumulative_fields = (
            "full_build_input_tiles",
            "full_build_visible_no_fog_tiles",
            "full_build_polygon_draw_tiles",
            "full_build_tile_loop_time_ns",
            "full_build_polygon_time_ns",
            "full_build_hex_corners_time_ns",
            "full_build_geometry_prepare_time_ns",
            "full_build_screen_transform_time_ns",
            "full_build_bounds_rect_time_ns",
        )
        attribution = {
            name: int(end_snapshot[name]) - int(start_snapshot[name])
            for name in cumulative_fields
        }
        attribution["full_build_polygon_time_ms"] = (
            attribution["full_build_polygon_time_ns"] / 1_000_000.0
        )
        attribution["full_build_tile_loop_time_ms"] = (
            attribution["full_build_tile_loop_time_ns"] / 1_000_000.0
        )
        attribution["full_build_hex_corners_time_ms"] = (
            attribution["full_build_hex_corners_time_ns"] / 1_000_000.0
        )
        attribution["full_build_geometry_prepare_time_ms"] = (
            attribution["full_build_geometry_prepare_time_ns"] / 1_000_000.0
        )
        attribution["full_build_screen_transform_time_ms"] = (
            attribution["full_build_screen_transform_time_ns"] / 1_000_000.0
        )
        attribution["full_build_bounds_rect_time_ms"] = (
            attribution["full_build_bounds_rect_time_ns"] / 1_000_000.0
        )
        attribution["non_polygon_tile_loop_time_ns"] = max(
            0,
            attribution["full_build_tile_loop_time_ns"]
            - attribution["full_build_polygon_time_ns"],
        )
        attribution["non_polygon_tile_loop_time_ms"] = (
            attribution["non_polygon_tile_loop_time_ns"] / 1_000_000.0
        )
        attribution["average_hex_corners_time_per_full_rebuild_ns"] = (
            attribution["full_build_hex_corners_time_ns"] / build_delta
            if build_delta
            else None
        )
        attribution["average_hex_corners_time_per_full_rebuild_ms"] = (
            attribution["full_build_hex_corners_time_ms"] / build_delta
            if build_delta
            else None
        )
        input_tiles = attribution["full_build_input_tiles"]
        attribution["average_hex_corners_time_per_input_tile_ns"] = (
            attribution["full_build_hex_corners_time_ns"] / input_tiles
            if input_tiles
            else None
        )
        tile_loop_time_ns = attribution["full_build_tile_loop_time_ns"]
        attribution["hex_corners_fraction_of_tile_loop_time"] = (
            attribution["full_build_hex_corners_time_ns"] / tile_loop_time_ns
            if tile_loop_time_ns
            else None
        )
        non_polygon_time_ns = attribution["non_polygon_tile_loop_time_ns"]
        attribution["hex_corners_fraction_of_non_polygon_tile_loop_time"] = (
            attribution["full_build_hex_corners_time_ns"] / non_polygon_time_ns
            if non_polygon_time_ns
            else None
        )
        attribution["average_geometry_prepare_time_per_full_rebuild_ns"] = (
            attribution["full_build_geometry_prepare_time_ns"] / build_delta
            if build_delta
            else None
        )
        attribution["average_geometry_prepare_time_per_full_rebuild_ms"] = (
            attribution["full_build_geometry_prepare_time_ms"] / build_delta
            if build_delta
            else None
        )
        attribution["average_geometry_prepare_time_per_input_tile_ns"] = (
            attribution["full_build_geometry_prepare_time_ns"] / input_tiles
            if input_tiles
            else None
        )
        attribution["geometry_prepare_fraction_of_tile_loop_time"] = (
            attribution["full_build_geometry_prepare_time_ns"] / tile_loop_time_ns
            if tile_loop_time_ns
            else None
        )
        attribution["geometry_prepare_fraction_of_non_polygon_tile_loop_time"] = (
            attribution["full_build_geometry_prepare_time_ns"]
            / non_polygon_time_ns
            if non_polygon_time_ns
            else None
        )
        attribution["average_screen_transform_time_per_full_rebuild_ns"] = (
            attribution["full_build_screen_transform_time_ns"] / build_delta
            if build_delta
            else None
        )
        attribution["average_screen_transform_time_per_full_rebuild_ms"] = (
            attribution["full_build_screen_transform_time_ms"] / build_delta
            if build_delta
            else None
        )
        attribution["average_screen_transform_time_per_input_tile_ns"] = (
            attribution["full_build_screen_transform_time_ns"] / input_tiles
            if input_tiles
            else None
        )
        attribution["screen_transform_fraction_of_tile_loop_time"] = (
            attribution["full_build_screen_transform_time_ns"] / tile_loop_time_ns
            if tile_loop_time_ns
            else None
        )
        attribution["screen_transform_fraction_of_non_polygon_tile_loop_time"] = (
            attribution["full_build_screen_transform_time_ns"]
            / non_polygon_time_ns
            if non_polygon_time_ns
            else None
        )
        attribution["average_bounds_rect_time_per_full_rebuild_ns"] = (
            attribution["full_build_bounds_rect_time_ns"] / build_delta
            if build_delta
            else None
        )
        attribution["average_bounds_rect_time_per_full_rebuild_ms"] = (
            attribution["full_build_bounds_rect_time_ms"] / build_delta
            if build_delta
            else None
        )
        attribution["average_bounds_rect_time_per_input_tile_ns"] = (
            attribution["full_build_bounds_rect_time_ns"] / input_tiles
            if input_tiles
            else None
        )
        attribution["bounds_rect_fraction_of_tile_loop_time"] = (
            attribution["full_build_bounds_rect_time_ns"] / tile_loop_time_ns
            if tile_loop_time_ns
            else None
        )
        attribution["bounds_rect_fraction_of_non_polygon_tile_loop_time"] = (
            attribution["full_build_bounds_rect_time_ns"] / non_polygon_time_ns
            if non_polygon_time_ns
            else None
        )
        if (
            state["hex_corners_timing_enabled"]
            and state["geometry_prepare_timing_enabled"]
        ):
            screen_time_ns = (
                attribution["full_build_geometry_prepare_time_ns"]
                - attribution["full_build_hex_corners_time_ns"]
            )
            attribution["screen_transform_bounds_rect_time_ns"] = screen_time_ns
            attribution["screen_transform_bounds_rect_time_ms"] = (
                screen_time_ns / 1_000_000.0
            )
            attribution[
                "average_screen_transform_bounds_rect_time_per_full_rebuild_ns"
            ] = screen_time_ns / build_delta if build_delta else None
            attribution[
                "average_screen_transform_bounds_rect_time_per_full_rebuild_ms"
            ] = (
                attribution["screen_transform_bounds_rect_time_ms"] / build_delta
                if build_delta
                else None
            )
            attribution[
                "average_screen_transform_bounds_rect_time_per_input_tile_ns"
            ] = screen_time_ns / input_tiles if input_tiles else None
            attribution[
                "screen_transform_bounds_rect_fraction_of_non_polygon_tile_loop_time"
            ] = (
                screen_time_ns / non_polygon_time_ns
                if non_polygon_time_ns
                else None
            )
        else:
            attribution["screen_transform_bounds_rect_time_ns"] = None
            attribution["screen_transform_bounds_rect_time_ms"] = None
            attribution[
                "average_screen_transform_bounds_rect_time_per_full_rebuild_ns"
            ] = None
            attribution[
                "average_screen_transform_bounds_rect_time_per_full_rebuild_ms"
            ] = None
            attribution[
                "average_screen_transform_bounds_rect_time_per_input_tile_ns"
            ] = None
            attribution[
                "screen_transform_bounds_rect_fraction_of_non_polygon_tile_loop_time"
            ] = None
        return {
            "total_frames": int(state["total_frames"]),
            "camera_changed_frames": camera_changed_frames,
            "offset_x_changed_frames": int(state["offset_x_changed_frames"]),
            "offset_y_changed_frames": int(state["offset_y_changed_frames"]),
            "zoom_changed_frames": int(state["zoom_changed_frames"]),
            "fog_full_build_counter_start": start_builds,
            "fog_full_build_counter_end": end_builds,
            "fog_full_build_delta": build_delta,
            "rebuilds_per_camera_changed_frame": (
                build_delta / camera_changed_frames
                if camera_changed_frames
                else None
            ),
            "coarse_full_build_reason_counts": _counter_delta(
                end_snapshot["full_build_reason_counts"],
                start_snapshot["full_build_reason_counts"],
            ),
            "detailed_geometry_change_counts": _counter_delta(
                end_snapshot["geometry_change_component_counts"],
                start_snapshot["geometry_change_component_counts"],
            ),
            "geometry_change_detail_counts": _counter_delta(
                end_snapshot["geometry_change_detail_counts"],
                start_snapshot["geometry_change_detail_counts"],
            ),
            "full_build_attribution": attribution,
            "rebuild_frames": end_snapshot["attribution_events"],
        }

    def _stop() -> Dict[str, Any]:
        state = getattr(harness, "_fog_camera_attribution_state", None)
        if not isinstance(state, dict):
            return {"ok": False, "error": "fog_camera_attribution_not_active"}

        presenter = _find_fog_presenter(world)
        camera = _camera()
        end_camera = (
            {
                "offset_x": float(camera.offset_x),
                "offset_y": float(camera.offset_y),
                "zoom": float(camera.zoom),
            }
            if camera is not None
            else None
        )
        end_snapshot = (
            presenter.diagnostic_snapshot() if presenter is not None else state["fog_start"]
        )
        profile_snapshot = original_handle({"command": "profile_snapshot"})
        if presenter is not None:
            presenter.set_full_build_attribution_enabled(False)
            presenter.set_hex_corners_attribution_enabled(False)
            presenter.set_geometry_prepare_attribution_enabled(False)
            presenter.set_screen_transform_attribution_enabled(False)
            presenter.set_bounds_rect_attribution_enabled(False)
            presenter.set_fused_transform_bounds_enabled(
                state["fused_transform_bounds_enabled_before"]
            )

        geometry_path_restored = bool(
            presenter is not None
            and bool(
                presenter.diagnostic_snapshot()["fused_transform_bounds_enabled"]
            )
            == state["fused_transform_bounds_enabled_before"]
        )

        restored = False
        if camera is not None:
            camera.offset_x = float(state["start_camera"]["offset_x"])
            camera.offset_y = float(state["start_camera"]["offset_y"])
            camera.zoom = float(state["start_camera"]["zoom"])
            restored = True
        harness._fog_camera_attribution_state = None

        setter = getattr(profiler, "set_metadata", None)
        if callable(setter):
            setter(
                scale_fog_camera_attribution_active=False,
                scale_fog_camera_attribution_completed=bool(state["completed"]),
            )
        result = {
            "ok": True,
            "experiment": EXPERIMENT_ID,
            "mode": state["mode"],
            "completed": bool(state["completed"]),
            "camera_start": dict(state["start_camera"]),
            "camera_end": end_camera,
            "camera_restored": restored,
            "active_moving_units_start": state["active_moving_units_start"],
            "active_moving_units_end": _moving_units(),
            "max_active_moving_units": state["max_active_moving_units"],
            "unit_movement_frames": state["unit_movement_frames"],
            "fog_enabled_start": state["fog_enabled_start"],
            "fog_enabled_end": bool(
                getattr(world.get_singleton_component(FogOfWar), "enabled", False)
            ),
            "fog_disabled_frames": state["fog_disabled_frames"],
            "aborted_reason": state["aborted_reason"],
            "timer_sanity": state["timer_sanity"],
            "hex_corners_timer_sanity": state["hex_corners_timer_sanity"],
            "geometry_prepare_timer_sanity": state[
                "geometry_prepare_timer_sanity"
            ],
            "screen_transform_timer_sanity": state[
                "screen_transform_timer_sanity"
            ],
            "bounds_rect_timer_sanity": state["bounds_rect_timer_sanity"],
            "polygon_timing_enabled": state["polygon_timing_enabled"],
            "hex_corners_timing_enabled": state["hex_corners_timing_enabled"],
            "geometry_prepare_timing_enabled": state[
                "geometry_prepare_timing_enabled"
            ],
            "screen_transform_timing_enabled": state[
                "screen_transform_timing_enabled"
            ],
            "bounds_rect_timing_enabled": state["bounds_rect_timing_enabled"],
            "geometry_path_requested": state["geometry_path_requested"],
            "geometry_path_effective": state["geometry_path_effective"],
            "geometry_path_restored": geometry_path_restored,
            "profile_snapshot": profile_snapshot,
        }
        result.update(_finish_result(state, end_snapshot))
        return result

    def _status() -> Dict[str, Any]:
        state = getattr(harness, "_fog_camera_attribution_state", None)
        if not isinstance(state, dict):
            return {"ok": True, "active": False, "completed": False}
        return {
            "ok": True,
            "active": True,
            "completed": bool(state["completed"]),
            "mode": state["mode"],
            "total_frames": int(state["total_frames"]),
            "camera_changed_frames": int(state["camera_changed_frames"]),
        }

    def _handle(command: Dict[str, Any]) -> Dict[str, Any]:
        op = str(command.get("command", "")).strip()
        if op == "start_fog_camera_attribution":
            return _start(command)
        if op == "stop_fog_camera_attribution":
            return _stop()
        if op == "fog_camera_attribution_status":
            return _status()
        return original_handle(command)

    harness.handle_command = _handle

    if callable(original_update):

        def _update(delta_time: float) -> None:
            original_update(delta_time)
            state = getattr(harness, "_fog_camera_attribution_state", None)
            if not isinstance(state, dict) or not bool(state.get("active")):
                return
            if bool(state.get("just_started")):
                state["just_started"] = False
                return
            if bool(state.get("completed")):
                return

            active_units = _moving_units()
            state["max_active_moving_units"] = max(
                int(state["max_active_moving_units"]), active_units
            )
            fog = world.get_singleton_component(FogOfWar)
            fog_enabled = bool(fog is not None and fog.enabled)
            if active_units or not fog_enabled:
                state["unit_movement_frames"] += int(active_units > 0)
                state["fog_disabled_frames"] += int(not fog_enabled)
                state["aborted_reason"] = (
                    "units_became_active" if active_units else "fog_became_disabled"
                )
                state["completed"] = True
                return

            camera = _camera()
            if camera is None:
                state["completed"] = True
                return
            before = (
                float(camera.offset_x),
                float(camera.offset_y),
                float(camera.zoom),
            )
            dt = max(0.0, float(delta_time))
            mode = state["mode"]
            if mode in PAN_TARGETS:
                displacement = before[0] - float(state["start_camera"]["offset_x"])
                remaining = max(0.0, PAN_TARGETS[mode] - displacement)
                camera_dt = min(dt, remaining / max(float(camera.speed), 1e-12))
                camera.move(camera.speed * camera_dt, 0.0)
            elif mode == "zoom":
                start_zoom = float(state["start_camera"]["zoom"])
                target_zoom = start_zoom + (
                    float(state["zoom_direction"]) * ZOOM_TARGET_DELTA
                )
                remaining = abs(target_zoom - before[2])
                camera_dt = min(dt, remaining / 2.0)
                if float(state["zoom_direction"]) > 0.0:
                    camera.zoom = min(camera.zoom + 2.0 * camera_dt, 3.0)
                else:
                    camera.zoom = max(camera.zoom - 2.0 * camera_dt, 0.5)

            after = (
                float(camera.offset_x),
                float(camera.offset_y),
                float(camera.zoom),
            )
            changed = {
                "offset_x": after[0] != before[0],
                "offset_y": after[1] != before[1],
                "zoom": after[2] != before[2],
            }
            changed["camera"] = any(changed.values())
            state["total_frames"] += 1
            for key in ("camera", "offset_x", "offset_y", "zoom"):
                if changed[key]:
                    state[f"{key}_changed_frames"] += 1

            if mode == "stationary":
                state["completed"] = (
                    state["total_frames"] >= state["stationary_frames"]
                )
            elif mode in PAN_TARGETS:
                displacement = after[0] - float(state["start_camera"]["offset_x"])
                state["completed"] = displacement >= PAN_TARGETS[mode]
            else:
                zoom_delta = after[2] - float(state["start_camera"]["zoom"])
                target_delta = float(state["zoom_direction"]) * ZOOM_TARGET_DELTA
                state["completed"] = (
                    zoom_delta >= target_delta
                    if target_delta > 0.0
                    else zoom_delta <= target_delta
                )
            _publish_state(state, changed)

        harness.update = _update

    if callable(original_cleanup):

        def _cleanup() -> None:
            if isinstance(
                getattr(harness, "_fog_camera_attribution_state", None), dict
            ):
                _stop()
            original_cleanup()

        harness.cleanup = _cleanup

    harness._fog_camera_attribution_installed = True
    return True


__all__ = [
    "EXPERIMENT_ID",
    "MODES",
    "install_fog_camera_attribution",
    "measure_bounds_rect_timer_overhead",
    "measure_geometry_prepare_timer_overhead",
    "measure_hex_corners_timer_overhead",
    "measure_polygon_timer_overhead",
    "measure_screen_transform_timer_overhead",
]
