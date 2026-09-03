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
            "geometry_prepare_timing_enabled": True,
            "screen_transform_timing_enabled": True,
            "bounds_rect_timing_enabled": True,
            "geometry_path": "fused",
        }
    )
    assert started["ok"] is True
    assert started["fog_full_build_counter_start"] == 1
    assert started["polygon_timing_enabled"] is True
    assert started["hex_corners_timing_enabled"] is True
    assert started["hex_corners_timer_sanity"]["samples"] == 10
    assert started["geometry_prepare_timing_enabled"] is True
    assert started["geometry_prepare_timer_sanity"]["samples"] == 10
    assert started["screen_transform_timing_enabled"] is True
    assert started["screen_transform_timer_sanity"]["samples"] == 10
    assert started["bounds_rect_timing_enabled"] is True
    assert started["bounds_rect_timer_sanity"]["samples"] == 10
    assert started["geometry_path_requested"] == "fused"
    assert started["geometry_path_effective"] == "legacy"
    assert started["corner_path_requested"] == "precomputed"
    assert started["corner_path_effective"] == "precomputed"

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
    assert stopped["geometry_path_restored"] is True
    assert stopped["corner_path_restored"] is True
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
    hex_time_ns = stopped["full_build_attribution"][
        "full_build_hex_corners_time_ns"
    ]
    assert hex_time_ns >= 0
    assert stopped["full_build_attribution"][
        "average_hex_corners_time_per_full_rebuild_ns"
    ] == pytest.approx(hex_time_ns / 3)
    assert stopped["full_build_attribution"][
        "average_hex_corners_time_per_input_tile_ns"
    ] == pytest.approx(hex_time_ns / 3)
    assert stopped["full_build_attribution"][
        "hex_corners_fraction_of_tile_loop_time"
    ] == pytest.approx(
        hex_time_ns
        / stopped["full_build_attribution"]["full_build_tile_loop_time_ns"]
    )
    assert stopped["full_build_attribution"][
        "hex_corners_fraction_of_non_polygon_tile_loop_time"
    ] == pytest.approx(
        hex_time_ns
        / stopped["full_build_attribution"]["non_polygon_tile_loop_time_ns"]
    )
    geometry_time_ns = stopped["full_build_attribution"][
        "full_build_geometry_prepare_time_ns"
    ]
    assert geometry_time_ns >= hex_time_ns
    assert stopped["full_build_attribution"][
        "average_geometry_prepare_time_per_full_rebuild_ns"
    ] == pytest.approx(geometry_time_ns / 3)
    assert stopped["full_build_attribution"][
        "average_geometry_prepare_time_per_input_tile_ns"
    ] == pytest.approx(geometry_time_ns / 3)
    screen_time_ns = stopped["full_build_attribution"][
        "screen_transform_bounds_rect_time_ns"
    ]
    assert screen_time_ns == geometry_time_ns - hex_time_ns
    assert screen_time_ns >= 0
    direct_screen_time_ns = stopped["full_build_attribution"][
        "full_build_screen_transform_time_ns"
    ]
    assert direct_screen_time_ns >= 0
    assert stopped["full_build_attribution"][
        "average_screen_transform_time_per_full_rebuild_ns"
    ] == pytest.approx(direct_screen_time_ns / 3)
    assert stopped["full_build_attribution"][
        "average_screen_transform_time_per_input_tile_ns"
    ] == pytest.approx(direct_screen_time_ns / 3)
    assert stopped["full_build_attribution"][
        "screen_transform_fraction_of_tile_loop_time"
    ] == pytest.approx(
        direct_screen_time_ns
        / stopped["full_build_attribution"]["full_build_tile_loop_time_ns"]
    )
    assert stopped["full_build_attribution"][
        "screen_transform_fraction_of_non_polygon_tile_loop_time"
    ] == pytest.approx(
        direct_screen_time_ns
        / stopped["full_build_attribution"]["non_polygon_tile_loop_time_ns"]
    )
    bounds_rect_time_ns = stopped["full_build_attribution"][
        "full_build_bounds_rect_time_ns"
    ]
    assert bounds_rect_time_ns >= 0
    assert stopped["full_build_attribution"][
        "average_bounds_rect_time_per_full_rebuild_ns"
    ] == pytest.approx(bounds_rect_time_ns / 3)
    assert stopped["full_build_attribution"][
        "average_bounds_rect_time_per_input_tile_ns"
    ] == pytest.approx(bounds_rect_time_ns / 3)
    assert stopped["full_build_attribution"][
        "bounds_rect_fraction_of_tile_loop_time"
    ] == pytest.approx(
        bounds_rect_time_ns
        / stopped["full_build_attribution"]["full_build_tile_loop_time_ns"]
    )
    assert stopped["full_build_attribution"][
        "bounds_rect_fraction_of_non_polygon_tile_loop_time"
    ] == pytest.approx(
        bounds_rect_time_ns
        / stopped["full_build_attribution"]["non_polygon_tile_loop_time_ns"]
    )
    assert stopped["full_build_attribution"]["non_polygon_tile_loop_time_ns"] >= 0
    assert len(stopped["rebuild_frames"]) == 3
    assert {event["geometry_path"] for event in stopped["rebuild_frames"]} == {
        "legacy"
    }
    assert {event["corner_path"] for event in stopped["rebuild_frames"]} == {
        "precomputed"
    }
    assert presenter.diagnostic_snapshot()["polygon_attribution_enabled"] is False
    assert (
        presenter.diagnostic_snapshot()["hex_corners_attribution_enabled"] is False
    )
    assert (
        presenter.diagnostic_snapshot()["geometry_prepare_attribution_enabled"]
        is False
    )
    assert (
        presenter.diagnostic_snapshot()["screen_transform_attribution_enabled"]
        is False
    )
    assert (
        presenter.diagnostic_snapshot()["bounds_rect_attribution_enabled"]
        is False
    )
    assert presenter.diagnostic_snapshot()["geometry_path"] == "fused"


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
            "geometry_path": "legacy",
            "corner_path": "legacy",
            "hex_corners_timing_enabled": False,
        }
    )
    assert started["pan_target_pixels"] == 320.0
    assert started["geometry_prepare_timing_enabled"] is False
    assert started["screen_transform_timing_enabled"] is False
    assert started["bounds_rect_timing_enabled"] is False
    assert started["geometry_path_requested"] == "legacy"
    assert started["geometry_path_effective"] == "legacy"
    assert started["corner_path_requested"] == "legacy"
    assert started["corner_path_effective"] == "legacy"
    harness.update(1.0)
    for _ in range(2):
        harness.update(1.0)
        _render(presenter, camera, visible_tiles)

    assert camera.offset_x - started["camera_start"]["offset_x"] == 320.0
    stopped = harness.handle_command({"command": "stop_fog_camera_attribution"})
    assert stopped["completed"] is True
    assert stopped["camera_end"]["offset_x"] == 420.0
    assert stopped["detailed_geometry_change_counts"] == {"offset_x": 2}
    assert (
        stopped["full_build_attribution"]["full_build_geometry_prepare_time_ns"]
        == 0
    )
    assert (
        stopped["full_build_attribution"]["screen_transform_bounds_rect_time_ns"]
        is None
    )
    assert stopped["full_build_attribution"]["full_build_screen_transform_time_ns"] == 0
    assert stopped["full_build_attribution"]["full_build_bounds_rect_time_ns"] == 0
    assert stopped["geometry_path_restored"] is True
    assert stopped["corner_path_restored"] is True
    assert {event["geometry_path"] for event in stopped["rebuild_frames"]} == {
        "legacy"
    }
    assert {event["corner_path"] for event in stopped["rebuild_frames"]} == {
        "legacy"
    }
    assert presenter.diagnostic_snapshot()["geometry_path"] == "fused"
    assert presenter.diagnostic_snapshot()["corner_path"] == "precomputed"
    assert (camera.offset_x, camera.offset_y, camera.zoom) == (100.0, 200.0, 1.0)


def test_short_pan_reports_exact_world_corner_cache_deltas_and_restores_path(
    monkeypatch,
):
    world, camera, presenter, visible_tiles = _setup()
    harness = _Harness()
    profiler = _Profiler()
    monkeypatch.setattr(attribution, "request_measurement_epoch", lambda *a, **k: True)
    attribution.install_fog_camera_attribution(harness, world, profiler)

    started = harness.handle_command(
        {
            "command": "start_fog_camera_attribution",
            "mode": "short_pan",
            "geometry_path": "fused",
            "corner_path": "precomputed",
            "world_corner_path": "cached",
            "polygon_timing_enabled": True,
            "hex_corners_timing_enabled": False,
            "geometry_prepare_timing_enabled": False,
            "screen_transform_timing_enabled": False,
            "bounds_rect_timing_enabled": False,
            "timer_sanity_samples": 1,
        }
    )
    assert started["world_corner_path_requested"] == "cached"
    assert started["world_corner_path_effective"] == "cached"

    harness.update(0.25)
    _render(presenter, camera, visible_tiles)
    for _ in range(3):
        harness.update(0.25)
        _render(presenter, camera, visible_tiles)

    stopped = harness.handle_command({"command": "stop_fog_camera_attribution"})
    cache = stopped["tile_world_corner_cache"]
    assert stopped["fog_full_build_delta"] == 3
    assert cache["path_effective"] == "cached"
    assert cache["hits_delta"] == 3
    assert cache["misses_delta"] == 0
    assert cache["lookups_delta"] == 3
    assert cache["hit_ratio"] == 1.0
    assert cache["hits_per_full_rebuild"] == 1.0
    assert cache["misses_per_full_rebuild"] == 0.0
    assert cache["entries_start"] == cache["entries_end"] == 1
    assert stopped["world_corner_path_restored"] is True
    assert stopped["attribution_timers_restored"] is True
    assert stopped["full_rebuild_observer_restored"] is True
    assert presenter.diagnostic_snapshot()["tile_world_corner_path"] == "cached"


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
    assert stationary["geometry_path_requested"] == "fused"
    assert stationary["geometry_path_effective"] == "fused"
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


def test_short_pan_translation_feasibility_captures_every_camera_frame(monkeypatch):
    world, camera, presenter, visible_tiles = _setup()
    harness = _Harness()
    profiler = _Profiler()
    monkeypatch.setattr(attribution, "request_measurement_epoch", lambda *a, **k: True)
    attribution.install_fog_camera_attribution(harness, world, profiler)

    started = harness.handle_command(
        {
            "command": "start_fog_camera_attribution",
            "mode": "short_pan",
            "geometry_path": "fused",
            "corner_path": "precomputed",
            "polygon_timing_enabled": False,
            "hex_corners_timing_enabled": False,
            "geometry_prepare_timing_enabled": False,
            "screen_transform_timing_enabled": False,
            "bounds_rect_timing_enabled": False,
            "timer_sanity_samples": 1,
            "translation_feasibility_enabled": True,
            "translation_nearby_radius": 1,
        }
    )
    assert started["ok"] is True
    assert started["translation_feasibility_enabled"] is True

    harness.update(0.25)
    _render(presenter, camera, visible_tiles)
    for _ in range(3):
        harness.update(0.25)
        _render(presenter, camera, visible_tiles)

    stopped = harness.handle_command({"command": "stop_fog_camera_attribution"})
    result = stopped["translation_feasibility"]
    assert stopped["camera_changed_frames"] == 3
    assert result["total_camera_changing_frames"] == 3
    assert len(result["frames"]) == 3
    assert all(frame["camera_dx"] > 0.0 for frame in result["frames"])
    assert all(frame["camera_dy"] == 0.0 for frame in result["frames"])
    assert all(frame["candidates"] for frame in result["frames"])
    assert stopped["camera_restored"] is True
    assert presenter._full_rebuild_observer is None


def test_short_pan_phase_raster_feasibility_restores_observer_and_camera(
    monkeypatch,
):
    world, camera, presenter, visible_tiles = _setup()
    previous_observer = lambda **_kwargs: None
    presenter.set_full_rebuild_observer(previous_observer)
    harness = _Harness()
    profiler = _Profiler()
    monkeypatch.setattr(attribution, "request_measurement_epoch", lambda *a, **k: True)
    attribution.install_fog_camera_attribution(harness, world, profiler)

    started = harness.handle_command(
        {
            "command": "start_fog_camera_attribution",
            "mode": "short_pan",
            "geometry_path": "fused",
            "corner_path": "precomputed",
            "polygon_timing_enabled": False,
            "hex_corners_timing_enabled": False,
            "geometry_prepare_timing_enabled": False,
            "screen_transform_timing_enabled": False,
            "bounds_rect_timing_enabled": False,
            "timer_sanity_samples": 1,
            "phase_raster_feasibility_enabled": True,
        }
    )
    assert started["ok"] is True
    assert started["phase_raster_feasibility_enabled"] is True

    harness.update(0.25)
    _render(presenter, camera, visible_tiles)
    for _ in range(3):
        harness.update(0.25)
        _render(presenter, camera, visible_tiles)

    stopped = harness.handle_command({"command": "stop_fog_camera_attribution"})
    result = stopped["phase_raster_feasibility"]
    assert stopped["camera_changed_frames"] == 3
    assert result["total_canonical_camera_frames"] == 3
    assert len(result["observed_phase_key_sequence"]) == 3
    assert stopped["camera_restored"] is True
    assert stopped["geometry_path_restored"] is True
    assert stopped["corner_path_restored"] is True
    assert presenter._full_rebuild_observer is previous_observer
    assert harness._fog_camera_attribution_state is None


def test_timer_sanity_path_quantifies_observer_overhead():
    result = attribution.measure_polygon_timer_overhead(100)
    hex_result = attribution.measure_hex_corners_timer_overhead(100)
    geometry_result = attribution.measure_geometry_prepare_timer_overhead(100)
    screen_result = attribution.measure_screen_transform_timer_overhead(100)
    bounds_result = attribution.measure_bounds_rect_timer_overhead(100)

    assert result["samples"] == 100
    assert result["wall_time_ns"] > 0
    assert result["wall_ns_per_sample"] > 0
    assert result["measured_interval_ns"] >= 0
    assert hex_result["samples"] == 100
    assert hex_result["wall_time_ns"] > 0
    assert hex_result["wall_ns_per_sample"] > 0
    assert hex_result["measured_interval_ns"] >= 0
    assert geometry_result["samples"] == 100
    assert geometry_result["wall_time_ns"] > 0
    assert geometry_result["wall_ns_per_sample"] > 0
    assert geometry_result["measured_interval_ns"] >= 0
    assert screen_result["samples"] == 100
    assert screen_result["wall_time_ns"] > 0
    assert screen_result["wall_ns_per_sample"] > 0
    assert screen_result["measured_interval_ns"] >= 0
    assert bounds_result["samples"] == 100
    assert bounds_result["wall_time_ns"] > 0
    assert bounds_result["wall_ns_per_sample"] > 0
    assert bounds_result["measured_interval_ns"] >= 0
