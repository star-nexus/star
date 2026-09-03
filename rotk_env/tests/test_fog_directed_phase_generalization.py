from types import SimpleNamespace

import pygame

from framework.ecs.world import World

from rotk_env.components import Camera, FogOfWar, GameState, UIState
from rotk_env.prefabs.config import Faction, GameConfig
from rotk_env.systems.fog_surface_presenter import IncrementalFogSurfacePresenter
from rotk_env.testing.fog_directed_phase_experiment import (
    install_fog_directed_phase_experiment,
)
from rotk_env.testing.fog_directed_phase_generalization import (
    DirectedPhaseRasterCollector,
    aggregate_generalization_results,
    directed_phase_key,
)
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

    def handle_command(self, _command):
        return {"ok": False, "error": "unknown_command"}

    def update(self, _delta_time):
        pass

    def cleanup(self):
        pass

    def _active_moving_units(self):
        return self.active_units


class _Profiler:
    pass


def _surface(size=(8, 5)):
    return pygame.Surface(size, pygame.SRCALPHA)


def _observe(collector, surface, offset, rect=None):
    collector.observe(
        surface=surface,
        presentation_rect=rect,
        camera_offset=offset,
        zoom=0.15,
        visible_tiles=(),
        view_faction="wei",
        orientation="flat",
        viewport=surface.get_size(),
    )


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


def test_directed_phase_distinguishes_boundary_side_and_geometry_identity():
    common = {
        "zoom": 0.15,
        "orientation": "flat",
        "viewport": (320, 240),
        "view_faction": "wei",
    }
    exact = directed_phase_key((1240.0, 634.0), **common)
    below_integer = directed_phase_key((1249.9999999999998, 634.0), **common)

    assert exact[:2] == (0, 0)
    assert below_integer[:2] == (1999, 0)
    assert directed_phase_key((1243.3333333333333, 634.0), **common)[0] == 1333
    assert directed_phase_key((1246.6666666666666, 634.0), **common)[0] == 666
    assert exact != below_integer
    assert exact != directed_phase_key((1240.0, 634.0), **{**common, "zoom": 0.5})
    assert exact != directed_phase_key(
        (1240.0, 634.0), **{**common, "orientation": "pointy"}
    )
    assert exact != directed_phase_key(
        (1240.0, 634.0), **{**common, "viewport": (321, 240)}
    )
    assert exact != directed_phase_key(
        (1240.0, 634.0), **{**common, "view_faction": "shu"}
    )


def test_collector_records_exact_first_and_rolling_anchor_reuse_without_mutation():
    collector = DirectedPhaseRasterCollector()
    anchor = _surface()
    anchor.set_at((1, 2), (10, 20, 30, 255))
    anchor_before = pygame.image.tobytes(anchor, "RGBA")
    _observe(collector, anchor, (0.0, 0.0), pygame.Rect(1, 2, 1, 1))

    current = _surface()
    current.set_at((3, 2), (10, 20, 30, 255))
    current_before = pygame.image.tobytes(current, "RGBA")
    _observe(collector, current, (2.0, 0.0), pygame.Rect(3, 2, 1, 1))

    result = collector.result()
    assert result["camera_changing_frames"] == 1
    assert result["phase_cache_hits"] == 1
    assert result["first_anchor"]["exact_reusable_hits"] == 1
    assert result["rolling_anchor"]["exact_reusable_hits"] == 1
    comparison = result["frames"][0]["first_anchor_comparison"]
    assert comparison["translation_is_integer"] is True
    assert comparison["translation_is_even"] is True
    assert comparison["presentation_rect_translated_equivalent"] is True
    assert pygame.image.tobytes(anchor, "RGBA") == anchor_before
    assert pygame.image.tobytes(current, "RGBA") == current_before


def test_global_hard_decision_abandons_on_any_interior_mismatch():
    exact = {
        "result": {
            "first_anchor": {
                "reusable_hits": 1,
                "exact_reusable_hits": 1,
                "interior_failure_count": 0,
                "boundary_only_failure_count": 0,
            },
            "rolling_anchor": {
                "reusable_hits": 1,
                "exact_reusable_hits": 1,
                "interior_failure_count": 0,
                "boundary_only_failure_count": 0,
            },
        }
    }
    viable = aggregate_generalization_results([exact])
    assert viable["structural_recommendation"] == "PHASE_RASTER_REUSE_VIABLE"

    mismatch = {
        "result": {
            "first_anchor": {
                "reusable_hits": 1,
                "exact_reusable_hits": 0,
                "interior_failure_count": 1,
                "boundary_only_failure_count": 0,
            },
            "rolling_anchor": exact["result"]["rolling_anchor"],
        }
    }
    abandoned = aggregate_generalization_results([mismatch])
    assert abandoned["structural_recommendation"] == "ABANDON_PHASE_RASTER_REUSE"
    assert abandoned["any_claimed_reusable_hit_had_interior_mismatch"] is True
    assert abandoned["next_architecture_if_abandoned"] == (
        "camera-independent / raster-phase-aware tile geometry caching"
    )


def test_workload_start_update_stop_restores_all_experiment_state():
    world, camera, presenter, visible_tiles = _setup()
    harness = _Harness()
    observer_before = lambda **_kwargs: None
    presenter.set_full_rebuild_observer(observer_before)
    presenter.set_full_build_attribution_enabled(True)
    presenter.set_hex_corners_attribution_enabled(True)
    presenter.set_geometry_prepare_attribution_enabled(True)
    presenter.set_screen_transform_attribution_enabled(True)
    presenter.set_bounds_rect_attribution_enabled(True)
    presenter.set_fused_transform_bounds_enabled(False)
    presenter.set_precomputed_hex_corners_enabled(False)

    assert install_fog_directed_phase_experiment(harness, world, _Profiler())
    started = harness.handle_command(
        {
            "command": "start_fog_directed_phase_generalization",
            "direction": "diagonal_positive_negative",
            "start_offset_x": 10.25,
            "start_offset_y": 20.25,
            "zoom": 0.15,
        }
    )
    assert started["ok"] is True
    assert started["geometry_path_effective"] == "fused"
    assert started["corner_path_effective"] == "precomputed"
    assert (camera.offset_x, camera.offset_y, camera.zoom) == (10.25, 20.25, 0.15)

    harness.update(0.25)
    presenter.update_surface(visible_tiles, list(camera.get_offset()), camera.zoom)
    assert (camera.offset_x, camera.offset_y) == (10.25, 20.25)
    for _ in range(3):
        harness.update(0.25)
        presenter.update_surface(visible_tiles, list(camera.get_offset()), camera.zoom)

    status = harness.handle_command(
        {"command": "fog_directed_phase_generalization_status"}
    )
    assert status["completed"] is True
    assert status["camera_changed_frames"] == 3
    assert status["canonical_camera_frames"] == 3
    assert (camera.offset_x, camera.offset_y) == (138.25, -107.75)

    stopped = harness.handle_command(
        {"command": "stop_fog_directed_phase_generalization"}
    )
    assert stopped["ok"] is True
    assert stopped["camera_restored"] is True
    assert stopped["observer_restored"] is True
    assert stopped["timers_restored"] is True
    assert stopped["geometry_path_restored"] is True
    assert stopped["corner_path_restored"] is True
    assert stopped["performance_timers_enabled"] is False
    assert stopped["result"]["camera_changing_frames"] == 3
    assert (camera.offset_x, camera.offset_y, camera.zoom) == (100.0, 200.0, 1.0)
    assert presenter._full_rebuild_observer is observer_before
    snapshot = presenter.diagnostic_snapshot()
    assert snapshot["geometry_path"] == "legacy"
    assert snapshot["corner_path"] == "legacy"
    assert all(
        snapshot[field]
        for field in (
            "polygon_attribution_enabled",
            "hex_corners_attribution_enabled",
            "geometry_prepare_attribution_enabled",
            "screen_transform_attribution_enabled",
            "bounds_rect_attribution_enabled",
        )
    )
