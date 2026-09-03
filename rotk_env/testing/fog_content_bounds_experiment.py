"""Harness adapter for Fog-content bounds correctness workloads."""

from __future__ import annotations

import math
from typing import Any, Dict, Optional, Tuple

from ..components import Camera, FogOfWar
from .fog_content_bounds_feasibility import FogContentBoundsCollector

EXPERIMENT_ID = "fog_content_bounds_feasibility_v1"
PAN_TARGET_PIXELS = 128.0
DIRECTIONS: Dict[str, Tuple[int, int]] = {
    "horizontal_positive": (1, 0),
    "horizontal_negative": (-1, 0),
    "vertical_positive": (0, 1),
    "vertical_negative": (0, -1),
    "diagonal_positive_positive": (1, 1),
    "diagonal_positive_negative": (1, -1),
}
_TIMER_FIELDS = (
    ("polygon_attribution_enabled", "set_full_build_attribution_enabled"),
    ("hex_corners_attribution_enabled", "set_hex_corners_attribution_enabled"),
    ("geometry_prepare_attribution_enabled", "set_geometry_prepare_attribution_enabled"),
    ("screen_transform_attribution_enabled", "set_screen_transform_attribution_enabled"),
    ("bounds_rect_attribution_enabled", "set_bounds_rect_attribution_enabled"),
)


def _find_fog_presenter(world):
    for system in getattr(world, "systems", ()):
        presenter = getattr(system, "_fog_presenter", None)
        if presenter is not None and callable(
            getattr(presenter, "diagnostic_snapshot", None)
        ):
            return presenter
    return None


def install_fog_content_bounds_experiment(harness, world, profiler) -> bool:
    """Install isolated start/status/stop commands on the scale harness."""
    del profiler
    if bool(getattr(harness, "_fog_content_bounds_experiment_installed", False)):
        return True

    original_handle = harness.handle_command
    original_update = getattr(harness, "update", None)
    original_cleanup = getattr(harness, "cleanup", None)
    harness._fog_content_bounds_experiment_state = None

    def _camera() -> Optional[Camera]:
        return world.get_singleton_component(Camera)

    def _moving_units() -> int:
        active = getattr(harness, "_active_moving_units", None)
        return int(active()) if callable(active) else 0

    def _restore(state: Dict[str, Any], presenter, camera) -> Dict[str, bool]:
        if presenter is not None:
            presenter.set_full_rebuild_observer(state["observer_before"])
            for field, setter_name in _TIMER_FIELDS:
                getattr(presenter, setter_name)(state[field + "_before"])
            presenter.set_fused_transform_bounds_enabled(
                state["fused_transform_bounds_enabled_before"]
            )
            presenter.set_precomputed_hex_corners_enabled(
                state["precomputed_hex_corner_offsets_enabled_before"]
            )
            presenter.set_tile_world_corner_cache_enabled(
                state["tile_world_corner_cache_enabled_before"]
            )
            presenter.set_presentation_bounds_path(
                state["presentation_bounds_path_before"]
            )
        camera_restored = False
        if camera is not None:
            camera.offset_x = state["original_camera"]["offset_x"]
            camera.offset_y = state["original_camera"]["offset_y"]
            camera.zoom = state["original_camera"]["zoom"]
            camera_restored = True
        if presenter is not None:
            presenter.reset()
        snapshot = presenter.diagnostic_snapshot() if presenter is not None else {}
        return {
            "camera_restored": camera_restored,
            "observer_restored": presenter is not None
            and presenter._full_rebuild_observer is state["observer_before"],
            "timers_restored": all(
                bool(snapshot.get(field)) == bool(state[field + "_before"])
                for field, _setter in _TIMER_FIELDS
            ),
            "geometry_path_restored": bool(
                snapshot.get("fused_transform_bounds_enabled")
            )
            == state["fused_transform_bounds_enabled_before"],
            "corner_path_restored": bool(
                snapshot.get("precomputed_hex_corner_offsets_enabled")
            )
            == state["precomputed_hex_corner_offsets_enabled_before"],
            "world_corner_path_restored": bool(
                snapshot.get("tile_world_corner_cache_enabled")
            )
            == state["tile_world_corner_cache_enabled_before"],
            "presentation_bounds_path_restored": snapshot.get(
                "presentation_bounds_path"
            )
            == state["presentation_bounds_path_before"],
        }

    def _start(command: Dict[str, Any]) -> Dict[str, Any]:
        if isinstance(
            getattr(harness, "_fog_content_bounds_experiment_state", None), dict
        ):
            return {"ok": False, "error": "fog_content_bounds_already_active"}
        for active_name in (
            "_fog_presentation_bounds_experiment_state",
            "_fog_directed_phase_experiment_state",
            "_fog_camera_attribution_state",
            "_scale_camera_stress_state",
        ):
            if isinstance(getattr(harness, active_name, None), dict):
                return {"ok": False, "error": active_name.lstrip("_") + "_active"}

        mode = str(command.get("mode", "pan")).strip().lower()
        direction_name = str(
            command.get("direction", "horizontal_positive")
        ).strip().lower()
        if mode not in {"pan", "zoom"}:
            return {"ok": False, "error": "invalid_mode", "modes": ["pan", "zoom"]}
        if mode == "pan" and direction_name not in DIRECTIONS:
            return {
                "ok": False,
                "error": "invalid_direction",
                "directions": sorted(DIRECTIONS),
            }
        try:
            start_x = float(command["start_offset_x"])
            start_y = float(command["start_offset_y"])
            start_zoom = float(command["zoom"])
            target_zoom = float(command.get("target_zoom", 0.50))
        except (KeyError, TypeError, ValueError):
            return {"ok": False, "error": "invalid_camera_start_or_zoom"}
        if start_zoom <= 0.0 or target_zoom <= 0.0:
            return {"ok": False, "error": "zoom_must_be_positive"}
        if mode == "zoom" and math.isclose(start_zoom, target_zoom):
            return {"ok": False, "error": "zoom_target_must_differ"}

        camera = _camera()
        fog = world.get_singleton_component(FogOfWar)
        presenter = _find_fog_presenter(world)
        active_units = _moving_units()
        if camera is None:
            return {"ok": False, "error": "camera_unavailable"}
        if fog is None or not fog.enabled:
            return {"ok": False, "error": "fog_must_be_enabled"}
        if active_units:
            return {
                "ok": False,
                "error": "units_must_be_stationary",
                "active_moving_units": active_units,
            }
        if presenter is None or presenter.surface is None:
            return {"ok": False, "error": "fog_surface_uninitialized"}

        snapshot = presenter.diagnostic_snapshot()
        collector = FogContentBoundsCollector(presenter)
        state: Dict[str, Any] = {
            "active": True,
            "completed": False,
            "target_reached": False,
            "anchor_ready": False,
            "mode": mode,
            "direction": direction_name if mode == "pan" else None,
            "direction_vector": DIRECTIONS.get(direction_name, (0, 0)),
            "target_pixels": PAN_TARGET_PIXELS,
            "target_zoom": target_zoom,
            "start_camera": {
                "offset_x": start_x,
                "offset_y": start_y,
                "zoom": start_zoom,
            },
            "original_camera": {
                "offset_x": float(camera.offset_x),
                "offset_y": float(camera.offset_y),
                "zoom": float(camera.zoom),
            },
            "camera_changed_frames": 0,
            "active_moving_units_start": active_units,
            "max_active_moving_units": active_units,
            "unit_movement_frames": 0,
            "fog_disabled_frames": 0,
            "aborted_reason": None,
            "collector": collector,
            "observer_before": presenter._full_rebuild_observer,
            "fused_transform_bounds_enabled_before": bool(
                snapshot["fused_transform_bounds_enabled"]
            ),
            "precomputed_hex_corner_offsets_enabled_before": bool(
                snapshot["precomputed_hex_corner_offsets_enabled"]
            ),
            "tile_world_corner_cache_enabled_before": bool(
                snapshot["tile_world_corner_cache_enabled"]
            ),
            "presentation_bounds_path_before": snapshot["presentation_bounds_path"],
        }
        for field, _setter in _TIMER_FIELDS:
            state[field + "_before"] = bool(snapshot[field])

        def _observe(**kwargs) -> None:
            collector.observe(**kwargs)
            state["anchor_ready"] = True

        for _field, setter_name in _TIMER_FIELDS:
            getattr(presenter, setter_name)(False)
        presenter.set_fused_transform_bounds_enabled(True)
        presenter.set_precomputed_hex_corners_enabled(True)
        presenter.set_tile_world_corner_cache_enabled(True)
        presenter.set_presentation_bounds_path("fog_content")
        presenter.set_full_rebuild_observer(_observe)
        camera.offset_x = start_x
        camera.offset_y = start_y
        camera.zoom = start_zoom
        presenter.reset()
        harness._fog_content_bounds_experiment_state = state
        return {
            "ok": True,
            "experiment": EXPERIMENT_ID,
            "mode": mode,
            "direction": state["direction"],
            "camera_start": dict(state["start_camera"]),
            "camera_original": dict(state["original_camera"]),
            "pan_target_pixels": PAN_TARGET_PIXELS if mode == "pan" else None,
            "target_zoom": target_zoom if mode == "zoom" else None,
            "presentation_bounds_path_effective": "fog_content",
            "performance_timers_enabled": False,
        }

    def _status() -> Dict[str, Any]:
        state = getattr(harness, "_fog_content_bounds_experiment_state", None)
        if not isinstance(state, dict):
            return {"ok": True, "active": False, "completed": False}
        return {
            "ok": True,
            "active": True,
            "completed": bool(state["completed"]),
            "anchor_ready": bool(state["anchor_ready"]),
            "camera_changed_frames": int(state["camera_changed_frames"]),
            "full_rebuild_comparisons": len(state["collector"].comparisons),
            "aborted_reason": state["aborted_reason"],
        }

    def _stop() -> Dict[str, Any]:
        state = getattr(harness, "_fog_content_bounds_experiment_state", None)
        if not isinstance(state, dict):
            return {"ok": False, "error": "fog_content_bounds_not_active"}
        camera = _camera()
        presenter = _find_fog_presenter(world)
        end_camera = (
            {
                "offset_x": float(camera.offset_x),
                "offset_y": float(camera.offset_y),
                "zoom": float(camera.zoom),
            }
            if camera is not None
            else None
        )
        result = state["collector"].result()
        restored = _restore(state, presenter, camera)
        harness._fog_content_bounds_experiment_state = None
        response = {
            "ok": True,
            "experiment": EXPERIMENT_ID,
            "completed": bool(state["completed"]),
            "mode": state["mode"],
            "direction": state["direction"],
            "camera_start": dict(state["start_camera"]),
            "camera_end": end_camera,
            "camera_original": dict(state["original_camera"]),
            "camera_changed_frames": int(state["camera_changed_frames"]),
            "active_moving_units_start": state["active_moving_units_start"],
            "active_moving_units_end": _moving_units(),
            "max_active_moving_units": state["max_active_moving_units"],
            "unit_movement_frames": state["unit_movement_frames"],
            "fog_disabled_frames": state["fog_disabled_frames"],
            "aborted_reason": state["aborted_reason"],
            "geometry_path_effective": "fused",
            "corner_path_effective": "precomputed",
            "world_corner_path_effective": "cached",
            "presentation_bounds_path_effective": "fog_content",
            "performance_timers_enabled": False,
            "result": result,
        }
        response.update(restored)
        return response

    def _handle(command: Dict[str, Any]) -> Dict[str, Any]:
        operation = str(command.get("command", "")).strip()
        if operation == "start_fog_content_bounds_feasibility":
            return _start(command)
        if operation == "fog_content_bounds_feasibility_status":
            return _status()
        if operation == "stop_fog_content_bounds_feasibility":
            return _stop()
        return original_handle(command)

    harness.handle_command = _handle

    if callable(original_update):

        def _update(delta_time: float) -> None:
            original_update(delta_time)
            state = getattr(harness, "_fog_content_bounds_experiment_state", None)
            if (
                not isinstance(state, dict)
                or not state["active"]
                or state["completed"]
                or not state["anchor_ready"]
            ):
                return
            active_units = _moving_units()
            state["max_active_moving_units"] = max(
                state["max_active_moving_units"], active_units
            )
            fog = world.get_singleton_component(FogOfWar)
            if active_units or fog is None or not fog.enabled:
                state["unit_movement_frames"] += int(active_units > 0)
                state["fog_disabled_frames"] += int(fog is None or not fog.enabled)
                state["aborted_reason"] = (
                    "units_became_active" if active_units else "fog_became_disabled"
                )
                state["completed"] = True
                return
            camera = _camera()
            if camera is None:
                state["aborted_reason"] = "camera_unavailable"
                state["completed"] = True
                return
            if state["target_reached"]:
                state["completed"] = True
                return
            before = (
                float(camera.offset_x),
                float(camera.offset_y),
                float(camera.zoom),
            )
            if state["mode"] == "pan":
                direction_x, direction_y = state["direction_vector"]
                start = state["start_camera"]
                traveled = max(
                    abs(float(camera.offset_x) - start["offset_x"])
                    if direction_x
                    else 0.0,
                    abs(float(camera.offset_y) - start["offset_y"])
                    if direction_y
                    else 0.0,
                )
                remaining = max(0.0, state["target_pixels"] - traveled)
                speed = max(float(camera.speed), 1e-12)
                delta = speed * min(
                    max(0.0, float(delta_time)), remaining / speed
                )
                camera.move(direction_x * delta, direction_y * delta)
                state["target_reached"] = math.isclose(
                    max(
                        abs(float(camera.offset_x) - start["offset_x"])
                        if direction_x
                        else 0.0,
                        abs(float(camera.offset_y) - start["offset_y"])
                        if direction_y
                        else 0.0,
                    ),
                    state["target_pixels"],
                    rel_tol=0.0,
                    abs_tol=1e-9,
                )
            else:
                target = state["target_zoom"]
                zoom_delta = 2.0 * max(0.0, float(delta_time))
                camera.zoom = (
                    min(camera.zoom + zoom_delta, target)
                    if target > camera.zoom
                    else max(camera.zoom - zoom_delta, target)
                )
                state["target_reached"] = math.isclose(
                    float(camera.zoom), target, rel_tol=0.0, abs_tol=1e-9
                )
            after = (
                float(camera.offset_x),
                float(camera.offset_y),
                float(camera.zoom),
            )
            if after != before:
                state["camera_changed_frames"] += 1

        harness.update = _update

    if callable(original_cleanup):

        def _cleanup() -> None:
            if isinstance(
                getattr(harness, "_fog_content_bounds_experiment_state", None),
                dict,
            ):
                _stop()
            original_cleanup()

        harness.cleanup = _cleanup

    harness._fog_content_bounds_experiment_installed = True
    return True


__all__ = [
    "DIRECTIONS",
    "EXPERIMENT_ID",
    "PAN_TARGET_PIXELS",
    "install_fog_content_bounds_experiment",
]
