from types import SimpleNamespace

import pygame
import pytest

from framework.ecs.world import World

from rotk_env.components import Camera, FogOfWar, GameState, MapData, UIState
from rotk_env.prefabs.config import Faction, GameConfig, HexOrientation
from rotk_env.systems.fog_surface_presenter import IncrementalFogSurfacePresenter
from rotk_env.systems.map_render_system import MapRenderSystem
from rotk_env.testing.fog_presentation_bounds_experiment import (
    install_fog_presentation_bounds_experiment,
)
from rotk_env.testing.fog_presentation_bounds_feasibility import (
    PresentationBoundsCollector,
    candidate_presentation_bounds,
    classify_mismatch,
    evaluate_direct_correctness_matrix,
    legacy_presentation_bounds,
)
from rotk_env.utils.hex_utils import HexConverter


TILE_SHAPES = {
    "empty": set(),
    "single": {(0, 0)},
    "two_adjacent": {(0, 0), (1, 0)},
    "small_cluster": {(0, 0), (1, 0), (0, 1), (-1, 0), (0, -1)},
    "rectangular_grid": {(q, r) for q in range(-3, 4) for r in range(-2, 3)},
    "sparse": {(-20, -10), (-3, 7), (0, 0), (8, -12), (24, 15)},
    "disconnected": {(-8, -8), (-8, -7), (12, 11), (13, 11)},
}
CAMERA_OFFSETS = (
    (1240.0, 634.0),
    (1240.25, 634.25),
    (1240.5, 634.5),
    (1240.75, 634.75),
    (1240.123456789, 634.876543211),
    (-340.625, -211.375),
    (8640.0, 4634.5),
)
ZOOMS = (0.10, 0.15, 0.50, 1.00, 3.00)
ORIENTATIONS = (HexOrientation.FLAT_TOP, HexOrientation.POINTY_TOP)


@pytest.mark.parametrize("orientation", ORIENTATIONS)
@pytest.mark.parametrize("zoom", ZOOMS)
@pytest.mark.parametrize("camera_offset", CAMERA_OFFSETS)
@pytest.mark.parametrize("shape", TILE_SHAPES)
def test_world_extrema_candidate_matches_or_classifies_matrix_counterexample(
    orientation, zoom, camera_offset, shape
):
    converter = HexConverter(GameConfig.HEX_SIZE, orientation)
    tiles = TILE_SHAPES[shape]
    viewport = (2480, 1268)

    legacy = legacy_presentation_bounds(
        tiles, converter, camera_offset, zoom, viewport
    )
    candidate = candidate_presentation_bounds(
        tiles, converter, camera_offset, zoom, viewport
    )

    assert candidate["unclipped_rect"] == legacy["unclipped_rect"]
    if candidate["rect"] != legacy["rect"]:
        categories = classify_mismatch(
            visible_tiles=frozenset(tiles),
            legacy_rect=legacy["rect"],
            recomputed_legacy_rect=legacy["rect"],
            recomputed_legacy_unclipped=legacy["unclipped_rect"],
            candidate_rect=candidate["rect"],
            candidate_unclipped=candidate["unclipped_rect"],
            set_changed=False,
        )
        assert "VIEWPORT_CLIPPING" in categories


@pytest.mark.parametrize("orientation", ORIENTATIONS)
def test_representative_91_by_91_production_map_is_exact(orientation):
    converter = HexConverter(GameConfig.HEX_SIZE, orientation)
    tiles = {(q, r) for q in range(-45, 46) for r in range(-45, 46)}
    legacy = legacy_presentation_bounds(
        tiles, converter, (1240.123456789, 634.876543211), 0.15, (2480, 1268)
    )
    candidate = candidate_presentation_bounds(
        tiles, converter, (1240.123456789, 634.876543211), 0.15, (2480, 1268)
    )
    assert candidate["rect"] == legacy["rect"]
    assert candidate["unclipped_rect"] == legacy["unclipped_rect"]


def test_direct_matrix_retains_exact_counts_and_counterexamples():
    result = evaluate_direct_correctness_matrix()
    assert result["comparison_count"] == 510
    assert result["exact_match_count"] == 454
    assert result["mismatch_count"] == 56
    assert result["supported_production_topology_mismatches"] > 0
    assert result["unsupported_synthetic_topology_mismatches"] > 0
    assert result["mismatch_category_counts"]["VIEWPORT_CLIPPING"] == 56


def test_actual_culling_produces_supported_contiguous_clipping_counterexample(
    monkeypatch,
):
    monkeypatch.setattr(GameConfig, "WINDOW_WIDTH", 320)
    monkeypatch.setattr(GameConfig, "WINDOW_HEIGHT", 240)
    world = World()
    world.add_singleton_component(
        MapData(width=2, height=1, tiles={(0, 0): 1, (1, 0): 2})
    )
    renderer = MapRenderSystem()
    renderer.world = world
    camera = (310.0, 120.0)
    visible_tiles = renderer._get_visible_tiles_smart(list(camera), 1.0)
    assert visible_tiles == {(0, 0), (1, 0)}

    legacy = legacy_presentation_bounds(
        visible_tiles, renderer.hex_converter, camera, 1.0, (320, 240)
    )
    candidate = candidate_presentation_bounds(
        visible_tiles, renderer.hex_converter, camera, 1.0, (320, 240)
    )
    assert legacy["rect"] == pygame.Rect(260, 77, 60, 87)
    assert candidate["rect"] == pygame.Rect(260, 33, 60, 131)
    assert candidate["rect"] != legacy["rect"]


VIEWPORT_CASES = (
    ("map_inside", {(0, 0)}, (160.0, 120.0), 0.5, (320, 240)),
    ("viewport_inside", {(q, r) for q in range(-8, 9) for r in range(-8, 9)}, (160.0, 120.0), 1.0, (320, 240)),
    ("left_clip", {(0, 0), (1, 0)}, (-10.0, 120.0), 1.0, (320, 240)),
    ("right_clip", {(0, 0), (1, 0)}, (310.0, 120.0), 1.0, (320, 240)),
    ("top_clip", {(0, 0), (0, 1)}, (160.0, -10.0), 1.0, (320, 240)),
    ("bottom_clip", {(0, 0), (0, 1)}, (160.0, 230.0), 1.0, (320, 240)),
    ("top_left_clip", {(0, 0)}, (-10.0, -10.0), 1.0, (320, 240)),
    ("bottom_right_clip", {(0, 0)}, (330.0, 250.0), 1.0, (320, 240)),
    ("fully_outside", {(0, 0), (1, 0)}, (900.0, 700.0), 1.0, (320, 240)),
)


@pytest.mark.parametrize("orientation", ORIENTATIONS)
@pytest.mark.parametrize("_name,tiles,camera_offset,zoom,viewport", VIEWPORT_CASES)
def test_viewport_clipping_relations_match_or_are_classified(
    orientation, _name, tiles, camera_offset, zoom, viewport
):
    converter = HexConverter(GameConfig.HEX_SIZE, orientation)
    legacy = legacy_presentation_bounds(
        tiles, converter, camera_offset, zoom, viewport
    )
    candidate = candidate_presentation_bounds(
        tiles, converter, camera_offset, zoom, viewport
    )
    assert candidate["unclipped_rect"] == legacy["unclipped_rect"]
    if candidate["rect"] != legacy["rect"]:
        categories = classify_mismatch(
            visible_tiles=frozenset(tiles),
            legacy_rect=legacy["rect"],
            recomputed_legacy_rect=legacy["rect"],
            recomputed_legacy_unclipped=legacy["unclipped_rect"],
            candidate_rect=candidate["rect"],
            candidate_unclipped=candidate["unclipped_rect"],
            set_changed=False,
        )
        assert "VIEWPORT_CLIPPING" in categories


def test_candidate_rejects_non_positive_zoom():
    converter = HexConverter(GameConfig.HEX_SIZE, HexOrientation.FLAT_TOP)
    with pytest.raises(ValueError, match="positive zoom"):
        candidate_presentation_bounds({(0, 0)}, converter, (0.0, 0.0), 0.0, (10, 10))


def test_collector_detects_set_identity_and_content_changes_without_mutation():
    converter = HexConverter(GameConfig.HEX_SIZE, HexOrientation.FLAT_TOP)
    collector = PresentationBoundsCollector(converter)
    viewport = (320, 240)
    camera = (160.25, 120.75)
    first = {(0, 0), (1, 0)}
    first_before = set(first)

    def observe(tiles):
        legacy = legacy_presentation_bounds(tiles, converter, camera, 1.0, viewport)
        collector.observe(
            surface=pygame.Surface(viewport, pygame.SRCALPHA),
            presentation_rect=legacy["rect"],
            camera_offset=camera,
            zoom=1.0,
            visible_tiles=tiles,
            view_faction=Faction.WEI,
            orientation=HexOrientation.FLAT_TOP,
            viewport=viewport,
        )

    observe(first)
    observe(first)
    replacement = set(first)
    observe(replacement)
    changed = set(first) | {(2, 0)}
    observe(changed)
    result = collector.result()

    assert first == first_before
    assert result["full_rebuild_comparisons"] == 4
    assert result["exact_match_count"] == 4
    assert result["visible_tiles_object_change_frames"] == 2
    assert result["visible_tiles_set_change_frames"] == 1
    assert result["exact_on_set_change_frames"] == 1


def test_mismatch_classifier_distinguishes_required_causes():
    tiles = frozenset({(0, 0), (20, 20)})
    categories = classify_mismatch(
        visible_tiles=tiles,
        legacy_rect=pygame.Rect(0, 0, 10, 10),
        recomputed_legacy_rect=pygame.Rect(0, 0, 10, 10),
        recomputed_legacy_unclipped=pygame.Rect(-2, -2, 12, 12),
        candidate_rect=pygame.Rect(0, 0, 9, 10),
        candidate_unclipped=pygame.Rect(-1, -2, 11, 12),
        set_changed=True,
    )
    assert "ROUNDING_OR_EXTREMA" in categories
    assert "SPARSE_OR_DISCONNECTED_TILE_SET" in categories
    assert "VISIBLE_TILE_SET_CHANGE" in categories


class _Renderer:
    def __init__(self, world):
        self.world = world
        self.hex_converter = HexConverter(GameConfig.HEX_SIZE, GameConfig.HEX_ORIENTATION)


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


def test_workload_start_update_stop_restores_all_state(monkeypatch):
    monkeypatch.setattr(GameConfig, "WINDOW_WIDTH", 320)
    monkeypatch.setattr(GameConfig, "WINDOW_HEIGHT", 240)
    world = World()
    camera = Camera(offset_x=100.0, offset_y=120.0, zoom=1.0, speed=200.0)
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
    visible_tiles = {(0, 0), (1, 0)}
    presenter.update_surface(visible_tiles, list(camera.get_offset()), camera.zoom)
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
    harness = _Harness()
    assert install_fog_presentation_bounds_experiment(harness, world, object())

    started = harness.handle_command(
        {
            "command": "start_fog_presentation_bounds_feasibility",
            "mode": "pan",
            "direction": "horizontal_positive",
            "start_offset_x": 10.25,
            "start_offset_y": 20.75,
            "zoom": 0.5,
        }
    )
    assert started["ok"] is True
    harness.update(0.25)
    presenter.update_surface(visible_tiles, list(camera.get_offset()), camera.zoom)
    for _ in range(3):
        harness.update(0.25)
        presenter.update_surface(visible_tiles, list(camera.get_offset()), camera.zoom)
    harness.update(0.01)

    status = harness.handle_command(
        {"command": "fog_presentation_bounds_feasibility_status"}
    )
    assert status["completed"] is True
    assert status["camera_changed_frames"] == 3
    assert status["full_rebuild_comparisons"] == 4
    stopped = harness.handle_command(
        {"command": "stop_fog_presentation_bounds_feasibility"}
    )
    assert stopped["result"]["exact_match_count"] == 4
    assert stopped["camera_restored"] is True
    assert stopped["observer_restored"] is True
    assert stopped["timers_restored"] is True
    assert stopped["geometry_path_restored"] is True
    assert stopped["corner_path_restored"] is True
    assert stopped["world_corner_path_restored"] is True
    assert (camera.offset_x, camera.offset_y, camera.zoom) == (100.0, 120.0, 1.0)
    snapshot = presenter.diagnostic_snapshot()
    assert snapshot["geometry_path"] == "legacy"
    assert snapshot["corner_path"] == "legacy"
    assert snapshot["tile_world_corner_path"] == "legacy"
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
