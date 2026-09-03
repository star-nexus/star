from collections import defaultdict
from types import SimpleNamespace

import pygame
import pytest

from framework.ecs.world import World
from framework.engine import RMS

from rotk_env.components import Camera, FogOfWar, GameState, UIState
from rotk_env.prefabs.config import Faction, GameConfig, HexOrientation
from rotk_env.systems.fog_surface_presenter import IncrementalFogSurfacePresenter
from rotk_env.testing.fog_content_bounds_feasibility import (
    alpha_support_bounds,
    alpha_support_is_contained,
    compare_bounded_composites,
    evaluate_direct_fog_content_matrix,
)
from rotk_env.testing.fog_content_bounds_experiment import (
    install_fog_content_bounds_experiment,
)
from rotk_env.testing.fog_presentation_bounds_feasibility import (
    legacy_presentation_bounds,
)
from rotk_env.utils.fog_visibility_journal import publish_fog_visibility_delta
from rotk_env.utils.hex_utils import HexConverter


class _Renderer:
    def __init__(self, world, orientation=HexOrientation.FLAT_TOP):
        self.world = world
        self.hex_converter = HexConverter(GameConfig.HEX_SIZE, orientation)


def _world(visible=(), explored=()):
    world = World()
    world.add_singleton_component(GameState(current_player=Faction.WEI))
    world.add_singleton_component(UIState(view_faction=Faction.WEI))
    world.add_singleton_component(
        FogOfWar(
            faction_vision={Faction.WEI: set(visible)},
            explored_tiles={Faction.WEI: set(explored)},
            enabled=True,
        )
    )
    return world


def _pixels(surface):
    return pygame.image.tostring(surface, "RGBA")


def _fresh_surface(
    tiles,
    visible,
    explored,
    camera,
    zoom,
    orientation=HexOrientation.FLAT_TOP,
    path="fog_content",
):
    world = _world(visible, explored)
    presenter = IncrementalFogSurfacePresenter(_Renderer(world, orientation))
    presenter.set_presentation_bounds_path(path)
    surface = presenter.update_surface(set(tiles), list(camera), zoom)
    return presenter, surface


def _set_visibility(world, presenter, tiles, camera, zoom, visible, dirty):
    fog = world.get_singleton_component(FogOfWar)
    fog.faction_vision[Faction.WEI] = set(visible)
    fog.explored_tiles[Faction.WEI].update(tiles)
    publish_fog_visibility_delta(world, {Faction.WEI: set(dirty)})
    return presenter.update_surface(set(tiles), list(camera), zoom)


def _assert_candidate_exact(presenter, surface, tiles, camera, zoom):
    assert alpha_support_is_contained(surface, presenter.presentation_rect)
    legacy_rect = legacy_presentation_bounds(
        tiles,
        presenter.renderer.hex_converter,
        camera,
        zoom,
        surface.get_size(),
    )["rect"]
    assert all(
        compare_bounded_composites(
            surface,
            legacy_rect=legacy_rect,
            candidate_rect=presenter.presentation_rect,
        ).values()
    )


def test_prior_510_cases_are_exact_under_fog_content_rendering_semantics():
    result = evaluate_direct_fog_content_matrix()

    assert result["comparison_count"] == 510
    assert result["exact_match_count"] == 510
    assert result["mismatch_count"] == 0
    assert result["supported_production_topology_mismatches"] == 0
    assert result["unsupported_synthetic_topology_mismatches"] == 0
    assert set(result["semantic_state_counts"]) == {
        "all_fogged",
        "all_visible",
        "one_visible_rest_fogged",
        "one_fogged_rest_visible",
        "mixed_explored_unexplored",
        "fog_islands",
        "visible_islands",
    }


@pytest.mark.parametrize("orientation", list(HexOrientation))
@pytest.mark.parametrize("zoom", [0.10, 0.15, 0.50, 1.00, 3.00])
@pytest.mark.parametrize(
    "camera",
    [
        (160.0, 120.0),
        (160.25, 120.25),
        (160.5, 120.5),
        (160.75, 120.75),
        (160.123456789, 120.876543211),
        (-240.625, 311.375),
    ],
)
def test_cache_on_off_bounds_paths_produce_identical_fog_pixels(
    monkeypatch, orientation, zoom, camera
):
    monkeypatch.setattr(GameConfig, "WINDOW_WIDTH", 320)
    monkeypatch.setattr(GameConfig, "WINDOW_HEIGHT", 240)
    tiles = {(q, r) for q in range(-2, 3) for r in range(-2, 3)} | {(9, -7)}
    visible = {tile for index, tile in enumerate(sorted(tiles)) if index % 3 == 0}
    explored = {tile for index, tile in enumerate(sorted(tiles)) if index % 2 == 0}

    legacy, legacy_surface = _fresh_surface(
        tiles, visible, explored, camera, zoom, orientation, "map_content_legacy"
    )
    candidate, candidate_surface = _fresh_surface(
        tiles, visible, explored, camera, zoom, orientation, "fog_content"
    )

    assert _pixels(candidate_surface) == _pixels(legacy_surface)
    _assert_candidate_exact(candidate, candidate_surface, tiles, camera, zoom)
    snapshot = candidate.diagnostic_snapshot()
    assert snapshot["presentation_bounds_path"] == "fog_content"
    assert snapshot["full_build_visible_no_fog_skipped_tiles"] == len(
        tiles.intersection(visible)
    )
    assert legacy.diagnostic_snapshot()["full_build_visible_no_fog_skipped_tiles"] == 0


def test_all_visible_has_empty_surface_none_bounds_and_no_render_command(monkeypatch):
    monkeypatch.setattr(GameConfig, "WINDOW_WIDTH", 320)
    monkeypatch.setattr(GameConfig, "WINDOW_HEIGHT", 240)
    monkeypatch.setattr(RMS, "_render_queue", defaultdict(list))
    monkeypatch.setattr(RMS, "current_layer", 0)
    tiles = {(0, 0), (1, 0), (0, 1)}
    world = _world(tiles, tiles)
    presenter = IncrementalFogSurfacePresenter(_Renderer(world))
    presenter.set_presentation_bounds_path("fog_content")

    presenter.render(tiles, [160.0, 120.0], 1.0)

    assert alpha_support_bounds(presenter.surface) is None
    assert presenter.presentation_rect is None
    assert RMS._render_queue[0] == []
    snapshot = presenter.diagnostic_snapshot()
    assert snapshot["full_build_visible_no_fog_tiles"] == len(tiles)
    assert snapshot["full_build_visible_no_fog_skipped_tiles"] == len(tiles)
    assert snapshot["full_build_polygon_draw_tiles"] == 0


def test_visibility_membership_is_checked_once_for_skipped_full_build_tiles(
    monkeypatch,
):
    monkeypatch.setattr(GameConfig, "WINDOW_WIDTH", 320)
    monkeypatch.setattr(GameConfig, "WINDOW_HEIGHT", 240)
    tiles = {(0, 0), (1, 0), (0, 1)}
    world = _world(tiles, tiles)
    presenter = IncrementalFogSurfacePresenter(_Renderer(world))
    presenter.set_presentation_bounds_path("fog_content")
    calls = 0
    original = presenter._tile_world_corners

    def counted(tile):
        nonlocal calls
        calls += 1
        return original(tile)

    monkeypatch.setattr(presenter, "_tile_world_corners", counted)
    presenter.update_surface(tiles, [160.0, 120.0], 1.0)

    assert calls == 0


def test_patch_reveal_never_shrinks_and_hide_expands_same_update(monkeypatch):
    monkeypatch.setattr(GameConfig, "WINDOW_WIDTH", 480)
    monkeypatch.setattr(GameConfig, "WINDOW_HEIGHT", 360)
    tiles = {(q, r) for q in range(-2, 3) for r in range(-2, 3)}
    center = (0, 0)
    outer = (2, 0)
    camera = (240.0, 180.0)
    world = _world(tiles - {center}, tiles)
    presenter = IncrementalFogSurfacePresenter(_Renderer(world))
    presenter.set_presentation_bounds_path("fog_content")
    surface = presenter.update_surface(tiles, list(camera), 1.0)
    initial = presenter.presentation_rect.copy()

    surface = _set_visibility(
        world, presenter, tiles, camera, 1.0, tiles, {center}
    )
    after_reveal = presenter.presentation_rect.copy()
    assert after_reveal == initial
    _assert_candidate_exact(presenter, surface, tiles, camera, 1.0)

    surface = _set_visibility(
        world, presenter, tiles, camera, 1.0, tiles - {outer}, {outer}
    )
    after_hide = presenter.presentation_rect.copy()
    assert after_hide.contains(after_reveal)
    assert after_hide != after_reveal
    _assert_candidate_exact(presenter, surface, tiles, camera, 1.0)

    reference, reference_surface = _fresh_surface(
        tiles, tiles - {outer}, tiles, camera, 1.0
    )
    assert _pixels(surface) == _pixels(reference_surface)
    assert after_hide.contains(reference.presentation_rect)


@pytest.mark.parametrize("newly_fogged", [(-3, 0), (3, 0), (0, -3), (0, 3), (-3, -3)])
def test_patch_expands_for_actual_fogged_patch_tiles_in_all_directions(
    monkeypatch, newly_fogged
):
    monkeypatch.setattr(GameConfig, "WINDOW_WIDTH", 800)
    monkeypatch.setattr(GameConfig, "WINDOW_HEIGHT", 600)
    tiles = {(0, 0), newly_fogged}
    camera = (400.0, 300.0)
    world = _world({newly_fogged}, tiles)
    presenter = IncrementalFogSurfacePresenter(_Renderer(world))
    presenter.set_presentation_bounds_path("fog_content")
    presenter.update_surface(tiles, list(camera), 1.0)
    initial = presenter.presentation_rect.copy()

    surface = _set_visibility(world, presenter, tiles, camera, 1.0, set(), {newly_fogged})

    assert presenter.presentation_rect.contains(initial)
    assert presenter.presentation_rect != initial
    _assert_candidate_exact(presenter, surface, tiles, camera, 1.0)


def test_all_visible_patch_sequence_creates_and_monotonically_expands_bounds(
    monkeypatch,
):
    monkeypatch.setattr(GameConfig, "WINDOW_WIDTH", 800)
    monkeypatch.setattr(GameConfig, "WINDOW_HEIGHT", 600)
    tiles = {(0, 0), (-3, 0), (3, 0), (0, -3), (0, 3)}
    camera = (400.0, 300.0)
    world = _world(tiles, tiles)
    presenter = IncrementalFogSurfacePresenter(_Renderer(world))
    presenter.set_presentation_bounds_path("fog_content")
    surface = presenter.update_surface(tiles, list(camera), 1.0)
    assert presenter.presentation_rect is None

    visible = set(tiles)
    previous = None
    for tile in [(0, 0), (-3, 0), (3, 0), (0, -3), (0, 3)]:
        visible.remove(tile)
        surface = _set_visibility(
            world, presenter, tiles, camera, 1.0, visible, {tile}
        )
        assert presenter.presentation_rect is not None
        if previous is not None:
            assert presenter.presentation_rect.contains(previous)
        previous = presenter.presentation_rect.copy()
        _assert_candidate_exact(presenter, surface, tiles, camera, 1.0)


def test_multiple_dirty_tiles_and_fogged_visible_toggle_matches_fresh_rebuild(
    monkeypatch,
):
    monkeypatch.setattr(GameConfig, "WINDOW_WIDTH", 480)
    monkeypatch.setattr(GameConfig, "WINDOW_HEIGHT", 360)
    tiles = {(q, r) for q in range(-2, 3) for r in range(-2, 3)}
    camera = (240.25, 180.75)
    world = _world(set(), tiles)
    presenter = IncrementalFogSurfacePresenter(_Renderer(world))
    presenter.set_presentation_bounds_path("fog_content")
    presenter.update_surface(tiles, list(camera), 0.5)

    states = [
        ({(-1, 0)}, {(-1, 0)}),
        ({(-1, 0), (0, 0)}, {(0, 0)}),
        ({(0, 0)}, {(-1, 0)}),
        (set(), {(0, 0)}),
        ({(-2, -2), (2, 2), (0, 0)}, {(-2, -2), (2, 2), (0, 0)}),
    ]
    for visible, dirty in states:
        surface = _set_visibility(
            world, presenter, tiles, camera, 0.5, visible, dirty
        )
        reference, reference_surface = _fresh_surface(
            tiles, visible, tiles, camera, 0.5
        )
        assert _pixels(surface) == _pixels(reference_surface)
        assert presenter.presentation_rect.contains(reference.presentation_rect)
        _assert_candidate_exact(presenter, surface, tiles, camera, 0.5)


def test_geometry_change_discards_stale_patch_bounds_and_rebuilds_tight(monkeypatch):
    monkeypatch.setattr(GameConfig, "WINDOW_WIDTH", 800)
    monkeypatch.setattr(GameConfig, "WINDOW_HEIGHT", 600)
    tiles = {(0, 0), (4, 0)}
    camera = (400.0, 300.0)
    world = _world({(4, 0)}, tiles)
    presenter = IncrementalFogSurfacePresenter(_Renderer(world))
    presenter.set_presentation_bounds_path("fog_content")
    presenter.update_surface(tiles, list(camera), 1.0)

    _set_visibility(world, presenter, tiles, camera, 1.0, set(), {(4, 0)})
    expanded = presenter.presentation_rect.copy()
    _set_visibility(world, presenter, tiles, camera, 1.0, {(4, 0)}, {(4, 0)})
    assert presenter.presentation_rect == expanded

    moved_camera = (401.25, 300.0)
    surface = presenter.update_surface(tiles, list(moved_camera), 1.0)
    reference, reference_surface = _fresh_surface(
        tiles, {(4, 0)}, tiles, moved_camera, 1.0
    )

    assert _pixels(surface) == _pixels(reference_surface)
    assert presenter.presentation_rect == reference.presentation_rect
    assert presenter.presentation_rect != expanded


def test_previous_clipping_counterexample_is_exact_with_visible_tile_skipped(
    monkeypatch,
):
    monkeypatch.setattr(GameConfig, "WINDOW_WIDTH", 320)
    monkeypatch.setattr(GameConfig, "WINDOW_HEIGHT", 240)
    tiles = {(0, 0), (1, 0)}
    camera = (310.0, 120.0)
    presenter, surface = _fresh_surface(
        tiles, {(1, 0)}, set(), camera, 1.0, path="fog_content"
    )

    _assert_candidate_exact(presenter, surface, tiles, camera, 1.0)
    assert presenter.diagnostic_snapshot()["full_build_visible_no_fog_skipped_tiles"] == 1


def test_presentation_bounds_control_validates_and_paths_are_independent():
    presenter = IncrementalFogSurfacePresenter(_Renderer(_world()))
    assert presenter.diagnostic_snapshot()["presentation_bounds_path"] == "fog_content"

    presenter.set_presentation_bounds_path("map_content_legacy")
    presenter.set_tile_world_corner_cache_enabled(False)
    snapshot = presenter.diagnostic_snapshot()
    assert snapshot["presentation_bounds_path"] == "map_content_legacy"
    assert snapshot["tile_world_corner_cache_enabled"] is False

    with pytest.raises(ValueError):
        presenter.set_presentation_bounds_path("global_extrema")


class _Harness:
    def __init__(self):
        self.active_units = 0

    def handle_command(self, command):
        return {"ok": False, "unhandled": command}

    def update(self, _delta_time):
        pass

    def cleanup(self):
        pass

    def _active_moving_units(self):
        return self.active_units


def test_runtime_experiment_start_update_stop_restores_observer_and_paths(
    monkeypatch,
):
    monkeypatch.setattr(GameConfig, "WINDOW_WIDTH", 320)
    monkeypatch.setattr(GameConfig, "WINDOW_HEIGHT", 240)
    world = _world()
    camera = Camera(offset_x=100.0, offset_y=120.0, zoom=1.0, speed=200.0)
    world.add_singleton_component(camera)
    presenter = IncrementalFogSurfacePresenter(_Renderer(world))
    world.systems.append(SimpleNamespace(_fog_presenter=presenter))
    tiles = {(0, 0), (1, 0)}
    presenter.update_surface(tiles, list(camera.get_offset()), camera.zoom)
    observer_before = lambda **_kwargs: None
    presenter.set_full_rebuild_observer(observer_before)
    presenter.set_full_build_attribution_enabled(True)
    presenter.set_hex_corners_attribution_enabled(True)
    presenter.set_geometry_prepare_attribution_enabled(True)
    presenter.set_screen_transform_attribution_enabled(True)
    presenter.set_bounds_rect_attribution_enabled(True)
    presenter.set_fused_transform_bounds_enabled(False)
    presenter.set_precomputed_hex_corners_enabled(False)
    presenter.set_tile_world_corner_cache_enabled(False)
    presenter.set_presentation_bounds_path("map_content_legacy")
    harness = _Harness()
    assert install_fog_content_bounds_experiment(harness, world, object())

    started = harness.handle_command(
        {
            "command": "start_fog_content_bounds_feasibility",
            "mode": "pan",
            "direction": "horizontal_positive",
            "start_offset_x": 10.25,
            "start_offset_y": 20.75,
            "zoom": 0.5,
        }
    )
    assert started["ok"] is True
    presenter.update_surface(tiles, list(camera.get_offset()), camera.zoom)
    for _ in range(3):
        harness.update(0.25)
        presenter.update_surface(tiles, list(camera.get_offset()), camera.zoom)
    harness.update(0.01)

    status = harness.handle_command(
        {"command": "fog_content_bounds_feasibility_status"}
    )
    assert status["completed"] is True
    assert status["camera_changed_frames"] == 3
    assert status["full_rebuild_comparisons"] == 4
    stopped = harness.handle_command(
        {"command": "stop_fog_content_bounds_feasibility"}
    )
    assert stopped["result"]["exact_match_count"] == 4
    assert stopped["result"]["mismatch_count"] == 0
    assert stopped["camera_restored"] is True
    assert stopped["observer_restored"] is True
    assert stopped["timers_restored"] is True
    assert stopped["geometry_path_restored"] is True
    assert stopped["corner_path_restored"] is True
    assert stopped["world_corner_path_restored"] is True
    assert stopped["presentation_bounds_path_restored"] is True
    assert (camera.offset_x, camera.offset_y, camera.zoom) == (100.0, 120.0, 1.0)
    snapshot = presenter.diagnostic_snapshot()
    assert snapshot["geometry_path"] == "legacy"
    assert snapshot["corner_path"] == "legacy"
    assert snapshot["tile_world_corner_path"] == "legacy"
    assert snapshot["presentation_bounds_path"] == "map_content_legacy"
    assert presenter._full_rebuild_observer is observer_before
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
