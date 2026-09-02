"""Deterministic camera pan/zoom stress for Scale Test Harness.

This is testing instrumentation only. It drives the real Camera singleton from the
ScaleHarness main-thread update so render/cache behaviour is exercised exactly as
interactive input would, without nondeterministic mouse gestures.
"""

from __future__ import annotations

from typing import Any, Dict

from ..components import Camera
from . import scale_experiment_measurement_base as _measurement_base
from .profiler_epoch import request_measurement_epoch

# Export rebuild/cache-build timers in formal profiler snapshots. This module is
# imported only when Scale Test Harness is enabled, so normal runtime profiling is
# untouched.
_TERRAIN_STRESS_SECTIONS = (
    "map_overscan_build_step",
    "map_terrain_opaque_present_cache_build",
)
for _section in _TERRAIN_STRESS_SECTIONS:
    if _section not in _measurement_base._RELEVANT_SECTIONS:
        _measurement_base._RELEVANT_SECTIONS += (_section,)

# Relative to the camera state captured at stress start. Pan steps deliberately
# cross the 256 px overscan margin; zoom steps are held long enough for the
# verified two-stable-frame overscan rebuild policy to engage.
_CAMERA_PATTERN = (
    (0.0, 0.0, 1.00),
    (320.0, 0.0, 1.00),
    (-320.0, 0.0, 1.00),
    (0.0, 320.0, 1.00),
    (0.0, -320.0, 1.00),
    (0.0, 0.0, 1.25),
    (0.0, 0.0, 1.00),
    (320.0, 160.0, 0.85),
    (0.0, 0.0, 1.00),
)


def install_scale_camera_stress(harness, world, profiler) -> bool:
    if bool(getattr(harness, "_scale_camera_stress_installed", False)):
        return True

    original_handle = harness.handle_command
    original_update = getattr(harness, "update", None)
    original_cleanup = getattr(harness, "cleanup", None)
    harness._scale_camera_stress_state = None

    def _camera():
        return world.get_singleton_component(Camera)

    def _apply_step(state: Dict[str, Any], index: int) -> None:
        camera = _camera()
        if camera is None:
            return
        dx, dy, zoom_scale = _CAMERA_PATTERN[index]
        camera.offset_x = float(state["start_x"]) + dx
        camera.offset_y = float(state["start_y"]) + dy
        camera.zoom = max(0.05, min(3.0, float(state["start_zoom"]) * zoom_scale))
        state["step_index"] = index
        state["transitions"] = int(state.get("transitions", 0)) + 1
        setter = getattr(profiler, "set_metadata", None)
        if callable(setter):
            setter(
                scale_camera_stress_active=True,
                scale_camera_stress_step_index=index,
                scale_camera_stress_transitions=state["transitions"],
                scale_camera_stress_camera_x=float(camera.offset_x),
                scale_camera_stress_camera_y=float(camera.offset_y),
                scale_camera_stress_camera_zoom=float(camera.zoom),
            )

    def _start(command: Dict[str, Any]) -> Dict[str, Any]:
        if isinstance(getattr(harness, "_scale_camera_stress_state", None), dict):
            return {"ok": False, "error": "camera_stress_already_active"}
        camera = _camera()
        if camera is None:
            return {"ok": False, "error": "camera_unavailable"}
        step_seconds = float(command.get("step_seconds", 0.75))
        if step_seconds < 0.1:
            return {
                "ok": False,
                "error": "camera_stress_step_too_short",
                "step_seconds": step_seconds,
            }

        state = {
            "active": True,
            "elapsed": 0.0,
            "step_seconds": step_seconds,
            "step_index": -1,
            "transitions": 0,
            "start_x": float(camera.offset_x),
            "start_y": float(camera.offset_y),
            "start_zoom": float(camera.zoom),
        }
        harness._scale_camera_stress_state = state
        _apply_step(state, 0)

        epoch_name = "terrain_camera_stress"
        measurement_state = getattr(harness, "_scale_measurement_state", None)
        if not isinstance(measurement_state, dict):
            measurement_state = {}
            harness._scale_measurement_state = measurement_state
        measurement_state.update(
            epoch_name=epoch_name,
            experiment_kind="terrain_camera_stress",
            camera_start={
                "offset_x": state["start_x"],
                "offset_y": state["start_y"],
                "zoom": state["start_zoom"],
            },
        )

        scheduled = request_measurement_epoch(
            profiler,
            epoch_name,
            scale_experiment_kind="terrain_camera_stress",
            scale_camera_stress_active=True,
            scale_camera_stress_step_seconds=step_seconds,
            scale_camera_stress_pattern_steps=len(_CAMERA_PATTERN),
            scale_camera_stress_start_x=state["start_x"],
            scale_camera_stress_start_y=state["start_y"],
            scale_camera_stress_start_zoom=state["start_zoom"],
        )
        return {
            "ok": True,
            "camera_stress": True,
            "measurement_epoch": epoch_name,
            "measurement_epoch_pending": scheduled,
            "step_seconds": step_seconds,
            "pattern_steps": len(_CAMERA_PATTERN),
            "camera_start": measurement_state["camera_start"],
        }

    def _stop(command: Dict[str, Any]) -> Dict[str, Any]:
        state = getattr(harness, "_scale_camera_stress_state", None)
        restore = bool(command.get("restore", True))
        camera = _camera()
        if isinstance(state, dict) and restore and camera is not None:
            camera.offset_x = float(state["start_x"])
            camera.offset_y = float(state["start_y"])
            camera.zoom = float(state["start_zoom"])
        transitions = int(state.get("transitions", 0)) if isinstance(state, dict) else 0
        harness._scale_camera_stress_state = None
        setter = getattr(profiler, "set_metadata", None)
        if callable(setter):
            setter(
                scale_camera_stress_active=False,
                scale_camera_stress_transitions=transitions,
            )
        return {
            "ok": True,
            "camera_stress": False,
            "restored": restore,
            "transitions": transitions,
        }

    def _handle(command: Dict[str, Any]) -> Dict[str, Any]:
        op = str(command.get("command", "")).strip()
        if op == "start_camera_stress":
            return _start(command)
        if op == "stop_camera_stress":
            return _stop(command)
        if op == "camera_stress_status":
            state = getattr(harness, "_scale_camera_stress_state", None)
            return {"ok": True, "camera_stress": dict(state) if isinstance(state, dict) else None}
        return original_handle(command)

    harness.handle_command = _handle

    if callable(original_update):
        def _update(delta_time: float) -> None:
            state = getattr(harness, "_scale_camera_stress_state", None)
            if isinstance(state, dict) and bool(state.get("active")):
                state["elapsed"] = float(state.get("elapsed", 0.0)) + max(0.0, float(delta_time))
                index = int(state["elapsed"] / state["step_seconds"]) % len(_CAMERA_PATTERN)
                if index != int(state.get("step_index", -1)):
                    _apply_step(state, index)
                metric = getattr(profiler, "set_frame_metric", None)
                if callable(metric):
                    metric("camera_stress_active", 1)
                    metric("camera_stress_step_index", index)
                    metric("camera_stress_transitions", int(state.get("transitions", 0)))
            original_update(delta_time)

        harness.update = _update

    if callable(original_cleanup):
        def _cleanup() -> None:
            state = getattr(harness, "_scale_camera_stress_state", None)
            if isinstance(state, dict):
                _stop({"restore": True})
            original_cleanup()

        harness.cleanup = _cleanup

    harness._scale_camera_stress_installed = True
    return True


__all__ = ["install_scale_camera_stress"]
