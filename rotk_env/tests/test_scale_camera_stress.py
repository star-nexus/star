import os

import pygame

from rotk_env.components import Camera
from rotk_env.systems.terrain_presentation_cache import OpaqueTerrainPresentationMixin
from rotk_env.testing import scale_camera_stress as camera_stress


class _World:
    def __init__(self, camera):
        self.camera = camera

    def get_singleton_component(self, component_type):
        return self.camera if component_type is Camera else None


class _Harness:
    def __init__(self):
        self._scale_measurement_state = {"required_fog": "on", "density": 1.0}
        self.update_calls = 0
        self.cleanup_calls = 0

    def handle_command(self, command):
        return {"ok": False, "error": "unknown", "command": command.get("command")}

    def update(self, delta_time):
        self.update_calls += 1

    def cleanup(self):
        self.cleanup_calls += 1


class _Profiler:
    def __init__(self):
        self.metadata = {}
        self.frame_metrics = {}

    def set_metadata(self, **kwargs):
        self.metadata.update(kwargs)

    def set_frame_metric(self, key, value):
        self.frame_metrics[key] = value


class _PresentationBase:
    def __init__(self):
        pass

    def _invalidate_fast_caches(self):
        pass

    def _draw_overscan(self, camera_offset):
        return 7


class _PresentationRenderer(OpaqueTerrainPresentationMixin, _PresentationBase):
    pass


def test_camera_stress_steps_and_restores_camera(monkeypatch):
    camera = Camera(offset_x=100.0, offset_y=200.0, zoom=0.2)
    world = _World(camera)
    harness = _Harness()
    profiler = _Profiler()
    monkeypatch.setattr(camera_stress, "request_measurement_epoch", lambda *a, **k: True)

    assert camera_stress.install_scale_camera_stress(harness, world, profiler)
    started = harness.handle_command(
        {"command": "start_camera_stress", "step_seconds": 0.5}
    )
    assert started["ok"] is True
    assert (camera.offset_x, camera.offset_y, camera.zoom) == (100.0, 200.0, 0.2)

    harness.update(0.51)
    assert camera.offset_x == 420.0
    assert camera.offset_y == 200.0
    assert camera.zoom == 0.2
    assert profiler.metadata["scale_camera_stress_transitions"] >= 2

    stopped = harness.handle_command({"command": "stop_camera_stress", "restore": True})
    assert stopped["ok"] is True
    assert (camera.offset_x, camera.offset_y, camera.zoom) == (100.0, 200.0, 0.2)
    assert profiler.metadata["scale_camera_stress_active"] is False


def test_legacy_terrain_presentation_mode_is_explicit_ab_escape_hatch(monkeypatch):
    monkeypatch.setenv("STAR_TERRAIN_PRESENTATION_MODE", "legacy_alpha")
    renderer = _PresentationRenderer()
    assert renderer._terrain_present_mode == "legacy_alpha"
    assert renderer._draw_overscan([0.0, 0.0]) == 7


def test_invalid_terrain_presentation_mode_fails_fast(monkeypatch):
    monkeypatch.setenv("STAR_TERRAIN_PRESENTATION_MODE", "not-a-mode")
    try:
        _PresentationRenderer()
    except ValueError as exc:
        assert "STAR_TERRAIN_PRESENTATION_MODE" in str(exc)
    else:
        raise AssertionError("invalid terrain presentation mode was accepted")
