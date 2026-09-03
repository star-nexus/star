from collections import defaultdict

import pygame

from framework.ecs.world import World
from framework.engine import RMS

from rotk_env.components import FogOfWar, GameState, UIState
from rotk_env.prefabs.config import Faction, GameConfig
from rotk_env.systems import fog_surface_presenter as fog_presenter_module
from rotk_env.systems.fog_surface_presenter import (
    FOG_GEOMETRY_BITS,
    IncrementalFogSurfacePresenter,
)
from rotk_env.utils.fog_visibility_journal import (
    FogVisibilityChangeJournal,
    publish_fog_visibility_delta,
)
from rotk_env.utils.hex_utils import HexConverter


class _Renderer:
    def __init__(self, world):
        self.world = world
        self.hex_converter = HexConverter(
            GameConfig.HEX_SIZE, GameConfig.HEX_ORIENTATION
        )


def _world():
    world = World()
    world.add_singleton_component(GameState(current_player=Faction.WEI))
    world.add_singleton_component(UIState(view_faction=Faction.WEI))
    world.add_singleton_component(
        FogOfWar(
            faction_vision={Faction.WEI: set()},
            explored_tiles={Faction.WEI: set()},
            enabled=True,
        )
    )
    return world


def _center(renderer, tile, camera_offset, zoom):
    x, y = renderer.hex_converter.hex_to_pixel(*tile)
    return (
        int(round(x * zoom + camera_offset[0])),
        int(round(y * zoom + camera_offset[1])),
    )


def test_incremental_patch_matches_authoritative_fog_state():
    world = _world()
    renderer = _Renderer(world)
    presenter = IncrementalFogSurfacePresenter(renderer)
    tile = (0, 0)
    visible_tiles = {tile}
    camera = [120.0, 120.0]
    zoom = 1.0
    pixel = _center(renderer, tile, camera, zoom)

    surface = presenter.update_surface(visible_tiles, camera, zoom)
    assert surface is not None
    assert surface.get_at(pixel)[3] > 0
    assert presenter.full_builds == 1

    fog = world.get_singleton_component(FogOfWar)
    fog.faction_vision[Faction.WEI].add(tile)
    fog.explored_tiles[Faction.WEI].add(tile)
    publish_fog_visibility_delta(world, {Faction.WEI: {tile}})

    same_surface = presenter.update_surface(visible_tiles, camera, zoom)
    assert same_surface is surface
    assert same_surface.get_at(pixel)[3] == 0
    assert presenter.full_builds == 1
    assert presenter.patch_updates == 1

    fog.faction_vision[Faction.WEI].remove(tile)
    publish_fog_visibility_delta(world, {Faction.WEI: {tile}})
    presenter.update_surface(visible_tiles, camera, zoom)
    assert presenter.surface.get_at(pixel)[3] == GameConfig.FOG_EXPLORED_COLOR[3]
    assert presenter.patch_updates == 2


def test_camera_change_forces_full_rebuild_not_incremental_patch():
    world = _world()
    renderer = _Renderer(world)
    presenter = IncrementalFogSurfacePresenter(renderer)
    tile = (0, 0)

    presenter.update_surface({tile}, [120.0, 120.0], 1.0)
    publish_fog_visibility_delta(world, {Faction.WEI: {tile}})
    presenter.update_surface({tile}, [121.0, 120.0], 1.0)

    assert presenter.full_builds == 2
    assert presenter.patch_updates == 0


def test_identical_geometry_reuses_surface_and_diagnostic_counter():
    world = _world()
    presenter = IncrementalFogSurfacePresenter(_Renderer(world))
    visible_tiles = {(0, 0), (1, 0)}

    surface = presenter.update_surface(visible_tiles, [120.0, 80.0], 1.0)
    before = presenter.diagnostic_snapshot()
    reused = presenter.update_surface(visible_tiles, [120.0, 80.0], 1.0)
    after = presenter.diagnostic_snapshot()

    assert reused is surface
    assert before["full_builds"] == after["full_builds"] == 1
    assert after["full_build_reason_counts"] == {"initial": 1}


def test_offset_change_reports_offset_geometry_invalidation():
    world = _world()
    presenter = IncrementalFogSurfacePresenter(_Renderer(world))
    presenter.set_full_build_attribution_enabled(True, clear_events=True)

    presenter.update_surface({(0, 0)}, [120.0, 80.0], 1.0)
    presenter.update_surface({(0, 0)}, [121.0, 82.0], 1.0)
    snapshot = presenter.diagnostic_snapshot()
    event = snapshot["attribution_events"][-1]

    assert event["coarse_reason"] == "view_geometry_changed"
    assert event["geometry_change_detail"] == ["offset_x", "offset_y"]
    assert event["geometry_change_mask"] == (
        FOG_GEOMETRY_BITS["offset_x"] | FOG_GEOMETRY_BITS["offset_y"]
    )
    assert event["camera_dx"] == 1.0
    assert event["camera_dy"] == 2.0
    assert event["zoom_delta"] == 0.0
    assert snapshot["geometry_change_component_counts"] == {
        "offset_x": 1,
        "offset_y": 1,
    }
    assert snapshot["geometry_change_detail_counts"] == {"offset_x|offset_y": 1}


def test_zoom_change_reports_zoom_geometry_invalidation():
    world = _world()
    presenter = IncrementalFogSurfacePresenter(_Renderer(world))
    presenter.set_full_build_attribution_enabled(True, clear_events=True)

    presenter.update_surface({(0, 0)}, [120.0, 80.0], 1.0)
    presenter.update_surface({(0, 0)}, [120.0, 80.0], 1.25)
    event = presenter.diagnostic_snapshot()["attribution_events"][-1]

    assert event["geometry_change_detail"] == ["zoom"]
    assert event["geometry_change_mask"] == FOG_GEOMETRY_BITS["zoom"]
    assert event["camera_dx"] == 0.0
    assert event["camera_dy"] == 0.0
    assert event["zoom_delta"] == 0.25


def test_geometry_key_rounding_uses_existing_safe_precision_thresholds():
    world = _world()
    presenter = IncrementalFogSurfacePresenter(_Renderer(world))
    visible_tiles = {(0, 0)}

    surface = presenter.update_surface(visible_tiles, [120.0, 80.0], 1.0)
    same_rounded_key = presenter.update_surface(
        visible_tiles, [120.0004, 80.0004], 1.000004
    )
    changed_rounded_key = presenter.update_surface(
        visible_tiles, [120.0006, 80.0004], 1.000006
    )

    assert same_rounded_key is surface
    assert changed_rounded_key is not surface
    assert presenter.full_builds == 2


def test_gated_polygon_attribution_preserves_pixels_and_counts_tiles():
    visible_tiles = {(0, 0), (0, 1), (1, 0)}
    camera = [160.0, 120.0]

    baseline_world = _world()
    baseline_presenter = IncrementalFogSurfacePresenter(_Renderer(baseline_world))
    baseline_world.get_singleton_component(FogOfWar).faction_vision[
        Faction.WEI
    ].add((0, 0))
    baseline = baseline_presenter.update_surface(visible_tiles, camera, 1.0)

    attributed_world = _world()
    attributed_presenter = IncrementalFogSurfacePresenter(_Renderer(attributed_world))
    attributed_world.get_singleton_component(FogOfWar).faction_vision[
        Faction.WEI
    ].add((0, 0))
    attributed_presenter.set_full_build_attribution_enabled(True, clear_events=True)
    attributed_presenter.set_hex_corners_attribution_enabled(True)
    attributed_presenter.set_geometry_prepare_attribution_enabled(True)
    attributed_presenter.set_screen_transform_attribution_enabled(True)
    attributed_presenter.set_bounds_rect_attribution_enabled(True)
    attributed = attributed_presenter.update_surface(visible_tiles, camera, 1.0)
    snapshot = attributed_presenter.diagnostic_snapshot()

    assert pygame.image.tostring(attributed, "RGBA") == pygame.image.tostring(
        baseline, "RGBA"
    )
    assert snapshot["full_build_input_tiles"] == 3
    assert snapshot["full_build_visible_no_fog_tiles"] == 1
    assert snapshot["full_build_polygon_draw_tiles"] == 2
    assert snapshot["full_build_polygon_time_ns"] >= 0
    assert snapshot["full_build_hex_corners_time_ns"] >= 0
    assert (
        snapshot["full_build_geometry_prepare_time_ns"]
        >= snapshot["full_build_hex_corners_time_ns"]
    )
    assert snapshot["full_build_screen_transform_time_ns"] >= 0
    assert snapshot["full_build_bounds_rect_time_ns"] >= 0


def test_detailed_attribution_timing_is_disabled_during_normal_runtime(monkeypatch):
    world = _world()
    presenter = IncrementalFogSurfacePresenter(_Renderer(world))

    def fail_if_timed():
        raise AssertionError("attribution timer must be disabled")

    monkeypatch.setattr(
        fog_presenter_module.time, "perf_counter_ns", fail_if_timed
    )

    presenter.update_surface({(0, 0), (1, 0)}, [160.0, 120.0], 1.0)
    snapshot = presenter.diagnostic_snapshot()

    assert snapshot["hex_corners_attribution_enabled"] is False
    assert snapshot["full_build_hex_corners_time_ns"] == 0
    assert snapshot["full_build_hex_corners_time_ms"] == 0.0
    assert snapshot["geometry_prepare_attribution_enabled"] is False
    assert snapshot["full_build_geometry_prepare_time_ns"] == 0
    assert snapshot["full_build_geometry_prepare_time_ms"] == 0.0
    assert snapshot["screen_transform_attribution_enabled"] is False
    assert snapshot["full_build_screen_transform_time_ns"] == 0
    assert snapshot["full_build_screen_transform_time_ms"] == 0.0
    assert snapshot["bounds_rect_attribution_enabled"] is False
    assert snapshot["full_build_bounds_rect_time_ns"] == 0
    assert snapshot["full_build_bounds_rect_time_ms"] == 0.0


def test_gated_hex_corners_attribution_records_exact_cumulative_deltas():
    world = _world()
    presenter = IncrementalFogSurfacePresenter(_Renderer(world))
    visible_tiles = {(0, 0), (0, 1), (1, 0)}
    presenter.set_hex_corners_attribution_enabled(True, clear_events=True)
    presenter.set_geometry_prepare_attribution_enabled(True)

    before = presenter.diagnostic_snapshot()
    presenter.update_surface(visible_tiles, [160.0, 120.0], 1.0)
    after_first = presenter.diagnostic_snapshot()
    first_event = after_first["attribution_events"][-1]
    first_delta = (
        after_first["full_build_hex_corners_time_ns"]
        - before["full_build_hex_corners_time_ns"]
    )

    assert first_delta == first_event["hex_corners_time_ns"]
    assert first_delta >= 0
    assert first_event["hex_corners_time_ms"] == first_delta / 1_000_000.0
    first_geometry_delta = (
        after_first["full_build_geometry_prepare_time_ns"]
        - before["full_build_geometry_prepare_time_ns"]
    )
    assert first_geometry_delta == first_event["geometry_prepare_time_ns"]
    assert first_geometry_delta >= first_delta
    assert after_first["polygon_attribution_enabled"] is False

    presenter.update_surface(visible_tiles, [161.0, 120.0], 1.0)
    after_second = presenter.diagnostic_snapshot()
    second_event = after_second["attribution_events"][-1]
    second_delta = (
        after_second["full_build_hex_corners_time_ns"]
        - after_first["full_build_hex_corners_time_ns"]
    )

    assert second_delta == second_event["hex_corners_time_ns"]
    assert second_delta >= 0
    second_geometry_delta = (
        after_second["full_build_geometry_prepare_time_ns"]
        - after_first["full_build_geometry_prepare_time_ns"]
    )
    assert second_geometry_delta == second_event["geometry_prepare_time_ns"]
    assert second_geometry_delta >= second_delta


def test_disabled_geometry_prepare_timer_records_zero_with_other_attribution():
    world = _world()
    presenter = IncrementalFogSurfacePresenter(_Renderer(world))
    presenter.set_full_build_attribution_enabled(True, clear_events=True)
    presenter.set_hex_corners_attribution_enabled(True)

    presenter.update_surface({(0, 0), (1, 0)}, [160.0, 120.0], 1.0)
    snapshot = presenter.diagnostic_snapshot()
    event = snapshot["attribution_events"][-1]

    assert snapshot["geometry_prepare_attribution_enabled"] is False
    assert snapshot["full_build_geometry_prepare_time_ns"] == 0
    assert event["geometry_prepare_time_ns"] == 0
    assert event["geometry_prepare_time_ms"] == 0.0


def test_gated_screen_transform_attribution_records_exact_cumulative_deltas():
    world = _world()
    presenter = IncrementalFogSurfacePresenter(_Renderer(world))
    visible_tiles = {(0, 0), (0, 1), (1, 0)}
    presenter.set_screen_transform_attribution_enabled(True, clear_events=True)

    before = presenter.diagnostic_snapshot()
    presenter.update_surface(visible_tiles, [160.0, 120.0], 1.0)
    after_first = presenter.diagnostic_snapshot()
    first_event = after_first["attribution_events"][-1]
    first_delta = (
        after_first["full_build_screen_transform_time_ns"]
        - before["full_build_screen_transform_time_ns"]
    )

    assert first_delta == first_event["screen_transform_time_ns"]
    assert first_delta >= 0
    assert first_event["screen_transform_time_ms"] == first_delta / 1_000_000.0
    assert after_first["polygon_attribution_enabled"] is False
    assert after_first["hex_corners_attribution_enabled"] is False
    assert after_first["geometry_prepare_attribution_enabled"] is False

    presenter.update_surface(visible_tiles, [161.0, 120.0], 1.0)
    after_second = presenter.diagnostic_snapshot()
    second_event = after_second["attribution_events"][-1]
    second_delta = (
        after_second["full_build_screen_transform_time_ns"]
        - after_first["full_build_screen_transform_time_ns"]
    )

    assert second_delta == second_event["screen_transform_time_ns"]
    assert second_delta >= 0


def test_disabled_screen_transform_timer_records_zero_with_other_attribution():
    world = _world()
    presenter = IncrementalFogSurfacePresenter(_Renderer(world))
    presenter.set_full_build_attribution_enabled(True, clear_events=True)

    presenter.update_surface({(0, 0), (1, 0)}, [160.0, 120.0], 1.0)
    snapshot = presenter.diagnostic_snapshot()
    event = snapshot["attribution_events"][-1]

    assert snapshot["screen_transform_attribution_enabled"] is False
    assert snapshot["full_build_screen_transform_time_ns"] == 0
    assert event["screen_transform_time_ns"] == 0
    assert event["screen_transform_time_ms"] == 0.0


def test_gated_bounds_rect_attribution_records_exact_cumulative_deltas():
    world = _world()
    presenter = IncrementalFogSurfacePresenter(_Renderer(world))
    visible_tiles = {(0, 0), (0, 1), (1, 0)}
    presenter.set_bounds_rect_attribution_enabled(True, clear_events=True)

    before = presenter.diagnostic_snapshot()
    presenter.update_surface(visible_tiles, [160.0, 120.0], 1.0)
    after_first = presenter.diagnostic_snapshot()
    first_event = after_first["attribution_events"][-1]
    first_delta = (
        after_first["full_build_bounds_rect_time_ns"]
        - before["full_build_bounds_rect_time_ns"]
    )

    assert first_delta == first_event["bounds_rect_time_ns"]
    assert first_delta >= 0
    assert first_event["bounds_rect_time_ms"] == first_delta / 1_000_000.0
    assert after_first["polygon_attribution_enabled"] is False
    assert after_first["hex_corners_attribution_enabled"] is False
    assert after_first["geometry_prepare_attribution_enabled"] is False
    assert after_first["screen_transform_attribution_enabled"] is False

    presenter.update_surface(visible_tiles, [161.0, 120.0], 1.0)
    after_second = presenter.diagnostic_snapshot()
    second_event = after_second["attribution_events"][-1]
    second_delta = (
        after_second["full_build_bounds_rect_time_ns"]
        - after_first["full_build_bounds_rect_time_ns"]
    )

    assert second_delta == second_event["bounds_rect_time_ns"]
    assert second_delta >= 0


def test_disabled_bounds_rect_timer_records_zero_with_other_attribution():
    world = _world()
    presenter = IncrementalFogSurfacePresenter(_Renderer(world))
    presenter.set_full_build_attribution_enabled(True, clear_events=True)

    presenter.update_surface({(0, 0), (1, 0)}, [160.0, 120.0], 1.0)
    snapshot = presenter.diagnostic_snapshot()
    event = snapshot["attribution_events"][-1]

    assert snapshot["bounds_rect_attribution_enabled"] is False
    assert snapshot["full_build_bounds_rect_time_ns"] == 0
    assert event["bounds_rect_time_ns"] == 0
    assert event["bounds_rect_time_ms"] == 0.0


def test_history_gap_falls_back_to_authoritative_full_rebuild():
    world = _world()
    setattr(
        world,
        "_fog_visibility_change_journal",
        FogVisibilityChangeJournal(max_events=8),
    )
    renderer = _Renderer(world)
    presenter = IncrementalFogSurfacePresenter(renderer)
    visible_tiles = {(0, 0)}

    presenter.update_surface(visible_tiles, [120.0, 120.0], 1.0)
    for index in range(12):
        publish_fog_visibility_delta(world, {Faction.WEI: {(index, 0)}})

    presenter.update_surface(visible_tiles, [120.0, 120.0], 1.0)
    assert presenter.full_builds == 2
    assert presenter.patch_updates == 0


def test_presentation_bounds_include_currently_transparent_visible_tiles(monkeypatch):
    monkeypatch.setattr(GameConfig, "WINDOW_WIDTH", 320)
    monkeypatch.setattr(GameConfig, "WINDOW_HEIGHT", 240)

    world = _world()
    renderer = _Renderer(world)
    presenter = IncrementalFogSurfacePresenter(renderer)
    tile = (0, 0)
    camera = [160.0, 120.0]
    pixel = _center(renderer, tile, camera, 1.0)
    fog = world.get_singleton_component(FogOfWar)

    # Start with the tile fully visible, so its fog pixels are transparent.
    fog.faction_vision[Faction.WEI].add(tile)
    surface = presenter.update_surface({tile}, camera, 1.0)
    rect = presenter.presentation_rect
    assert surface is not None
    assert rect is not None
    assert rect.collidepoint(pixel)
    assert surface.get_at(pixel)[3] == 0

    # A later semantic patch can make the same tile fogged without changing view
    # geometry. The precomputed map-content bound must still cover it.
    fog.faction_vision[Faction.WEI].remove(tile)
    publish_fog_visibility_delta(world, {Faction.WEI: {tile}})
    presenter.update_surface({tile}, camera, 1.0)

    assert presenter.presentation_rect == rect
    assert presenter.surface.get_at(pixel)[3] > 0
    assert presenter.presentation_rect.collidepoint(pixel)


def test_bounded_composite_is_pixel_identical_to_full_surface_blit(monkeypatch):
    monkeypatch.setattr(GameConfig, "WINDOW_WIDTH", 320)
    monkeypatch.setattr(GameConfig, "WINDOW_HEIGHT", 240)

    world = _world()
    renderer = _Renderer(world)
    presenter = IncrementalFogSurfacePresenter(renderer)
    visible_tiles = {(0, 0), (0, 1), (1, 0)}
    camera = [160.0, 120.0]

    surface = presenter.update_surface(visible_tiles, camera, 1.0)
    rect = presenter.presentation_rect
    assert surface is not None
    assert rect is not None
    assert rect.width * rect.height < surface.get_width() * surface.get_height()

    expected = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    expected.fill((17, 31, 47, 255))
    actual = expected.copy()

    expected.blit(surface, (0, 0))
    actual.blit(surface, rect.topleft, area=rect)

    assert pygame.image.tostring(actual, "RGBA") == pygame.image.tostring(
        expected, "RGBA"
    )


def test_render_queues_only_content_bounded_fog_blit(monkeypatch):
    monkeypatch.setattr(GameConfig, "WINDOW_WIDTH", 320)
    monkeypatch.setattr(GameConfig, "WINDOW_HEIGHT", 240)
    monkeypatch.setattr(RMS, "_render_queue", defaultdict(list))
    monkeypatch.setattr(RMS, "current_layer", 0)

    world = _world()
    renderer = _Renderer(world)
    presenter = IncrementalFogSurfacePresenter(renderer)
    visible_tiles = {(0, 0), (0, 1), (1, 0)}
    camera = [160.0, 120.0]

    presenter.render(visible_tiles, camera, 1.0)

    commands = RMS._render_queue[0]
    assert len(commands) == 1
    command = commands[0]
    rect = presenter.presentation_rect
    assert rect is not None
    assert command.surface is presenter.surface
    assert command.area == rect
    assert command.dest == rect.topleft
    assert command.batchable is False
