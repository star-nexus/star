from types import SimpleNamespace

import pytest

from framework.ecs.world import World

from rotk_env.components import Camera, FogOfWar, GameState, UIState
from rotk_env.prefabs.config import Faction, GameConfig
from rotk_env.systems.fog_surface_presenter import IncrementalFogSurfacePresenter
from rotk_env.testing import fog_camera_attribution as attribution
from rotk_env.utils.hex_utils import HexConverter


class _Renderer:
    def __init__(self, world):
        self.world = world
        self.hex_converter = HexConverter(
            GameConfig.HEX_SIZE, GameConfig.HEX_ORIENTATION
        )


class _Harness:
    def __init__(self):
        self.active_units = 0
        self.update_calls = 0
        self.cleanup_calls = 0

    def handle_command(self, command):
        if command.get("command") == "profile_snapshot":
            return {"ok": True, "sections": {}}
        return {"ok": False, "error": "unknown_command"}

    def update(self, _delta_time):
        self.update_calls += 1

    def cleanup(self):
        self.cleanup_calls += 1

    def _active_moving_units(self):
        return self.active_units


class _Profiler:
    def __init__(self):
        self.metadata = {}
        self.frame_metrics = {}

    def set_metadata(self, **values):
        self.metadata.update(values)

    def set_frame_metric(self, key, value):
        self.frame_metrics[key] = value


def _setup():
    world = World()
    camera = Camera(offset_x=100.0, offset_y=200.0, zoom=1.0, speed=200.0)
    world.add_singleton_component(camera)
    world.add_singleton_component(GameState(current_player=Faction.WEI))
    world.add_singleton_component(UIState(view_faction=Faction.WEI))
    world.add_singleton_component(
        FogOfWar(
            faction_vision={Faction.WEI: set()},
            explored_tiles={Faction.WEI: set()},
            enabled=True,
        )
    )
    presenter = IncrementalFogSurfacePresenter(_Renderer(world))
    world.systems.append(SimpleNamespace(_fog_presenter=presenter))
    visible_tiles = {(0, 0)}
    presenter.update_surface(visible_tiles, list(camera.get_offset()), camera.zoom)
    return world, camera, presenter, visible_tiles


def _render(presenter, camera, visible_tiles):
    presenter.update_surface(visible_tiles, list(camera.get_offset()), camera.zoom)


def test_short_pan_uses_continuous_camera_semantics_and_exact_counter_deltas(
    monkeypatch,
):
    world, camera, presenter, visible_tiles = _setup()
    harness = _Harness()
    profiler = _Profiler()
    monkeypatch.setattr(attribution, "request_measurement_epoch", lambda *a, **k: True)

    assert attribution.install_fog_camera_attribution(harness, world, profiler)
    started = harness.handle_command(
        {
            "command": "start_fog_camera_attribution",
            "mode": "short_pan",
            "timer_sanity_samples": 10,
        }
    )
    assert started["ok"] is True
    assert started["fog_full_build_counter_start"] == 1

    # The start frame is deliberately held so the deferred profiler epoch can
    # begin before the first production-style camera increment.
    harness.update(0.25)
    _render(presenter, camera, visible_tiles)
    assert camera.offset_x == 100.0

    for _ in range(3):
        harness.update(0.25)
        _render(presenter, camera, visible_tiles)

    status = harness.handle_command({"command": "fog_camera_attribution_status"})
    assert status["completed"] is True
    assert camera.offset_x == 228.0

    stopped = harness.handle_command({"command": "stop_fog_camera_attribution"})
    assert stopped["ok"] is True
    assert stopped["camera_restored"] is True
    assert (camera.offset_x, camera.offset_y, camera.zoom) == (100.0, 200.0, 1.0)
    assert stopped["total_frames"] == 3
    assert stopped["camera_changed_frames"] == 3
    assert stopped["offset_x_changed_frames"] == 3
    assert stopped["offset_y_changed_frames"] == 0
    assert stopped["zoom_changed_frames"] == 0
    assert stopped["fog_full_build_counter_start"] == 1
    assert stopped["fog_full_build_counter_end"] == 4
    assert stopped["fog_full_build_delta"] == 3
    assert stopped["rebuilds_per_camera_changed_frame"] == 1.0
    assert stopped["coarse_full_build_reason_counts"] == {
        "view_geometry_changed": 3
    }
    assert stopped["detailed_geometry_change_counts"] == {"offset_x": 3}
    assert stopped["geometry_change_detail_counts"] == {"offset_x": 3}
    assert stopped["full_build_attribution"]["full_build_input_tiles"] == 3
    assert stopped["full_build_attribution"]["non_polygon_tile_loop_time_ns"] >= 0
    assert len(stopped["rebuild_frames"]) == 3
    assert presenter.diagnostic_snapshot()["polygon_attribution_enabled"] is False


def test_long_pan_crosses_256_pixels_and_stops_at_deterministic_target(monkeypatch):
    world, camera, presenter, visible_tiles = _setup()
    harness = _Harness()
    profiler = _Profiler()
    monkeypatch.setattr(attribution, "request_measurement_epoch", lambda *a, **k: True)
    attribution.install_fog_camera_attribution(harness, world, profiler)

    started = harness.handle_command(
        {
            "command": "start_fog_camera_attribution",
            "mode": "long_pan",
            "timer_sanity_samples": 10,
        }
    )
    assert started["pan_target_pixels"] == 320.0
    harness.update(1.0)
    for _ in range(2):
        harness.update(1.0)
        _render(presenter, camera, visible_tiles)

    assert camera.offset_x - started["camera_start"]["offset_x"] == 320.0
    stopped = harness.handle_command({"command": "stop_fog_camera_attribution"})
    assert stopped["completed"] is True
    assert stopped["camera_end"]["offset_x"] == 420.0
    assert stopped["detailed_geometry_change_counts"] == {"offset_x": 2}
    assert (camera.offset_x, camera.offset_y, camera.zoom) == (100.0, 200.0, 1.0)


def test_stationary_and_zoom_epochs_complete_and_restore(monkeypatch):
    world, camera, presenter, visible_tiles = _setup()
    harness = _Harness()
    profiler = _Profiler()
    monkeypatch.setattr(attribution, "request_measurement_epoch", lambda *a, **k: True)
    attribution.install_fog_camera_attribution(harness, world, profiler)

    stationary = harness.handle_command(
        {
            "command": "start_fog_camera_attribution",
            "mode": "stationary",
            "stationary_frames": 2,
            "timer_sanity_samples": 10,
        }
    )
    assert stationary["ok"] is True
    harness.update(0.1)
    for _ in range(2):
        harness.update(0.1)
        _render(presenter, camera, visible_tiles)
    stationary_stop = harness.handle_command(
        {"command": "stop_fog_camera_attribution"}
    )
    assert stationary_stop["completed"] is True
    assert stationary_stop["total_frames"] == 2
    assert stationary_stop["camera_changed_frames"] == 0
    assert stationary_stop["fog_full_build_delta"] == 0
    assert stationary_stop["rebuilds_per_camera_changed_frame"] is None

    zoom = harness.handle_command(
        {
            "command": "start_fog_camera_attribution",
            "mode": "zoom",
            "timer_sanity_samples": 10,
        }
    )
    assert zoom["ok"] is True
    harness.update(0.1)
    for _ in range(3):
        harness.update(0.1)
        _render(presenter, camera, visible_tiles)
    assert camera.zoom == pytest.approx(1.5)
    zoom_stop = harness.handle_command({"command": "stop_fog_camera_attribution"})
    assert zoom_stop["completed"] is True
    assert zoom_stop["zoom_changed_frames"] == 3
    assert zoom_stop["detailed_geometry_change_counts"] == {"zoom": 3}
    assert (camera.offset_x, camera.offset_y, camera.zoom) == (100.0, 200.0, 1.0)


def test_timer_sanity_path_quantifies_observer_overhead():
    result = attribution.measure_polygon_timer_overhead(100)

    assert result["samples"] == 100
    assert result["wall_time_ns"] > 0
    assert result["wall_ns_per_sample"] > 0
    assert result["measured_interval_ns"] >= 0
