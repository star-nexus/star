import pygame
import pytest

from framework.ecs.world import World

from rotk_env.components import FogOfWar, GameState, UIState
from rotk_env.prefabs.config import Faction, GameConfig, HexOrientation
from rotk_env.systems.fog_surface_presenter import IncrementalFogSurfacePresenter
from rotk_env.utils.hex_utils import HexConverter


class _Renderer:
    def __init__(self, world, orientation=HexOrientation.FLAT_TOP, size=None):
        self.world = world
        self.hex_converter = HexConverter(size or GameConfig.HEX_SIZE, orientation)


def _world():
    world = World()
    world.add_singleton_component(GameState(current_player=Faction.WEI))
    world.add_singleton_component(UIState(view_faction=Faction.WEI))
    world.add_singleton_component(
        FogOfWar(
            faction_vision={Faction.WEI: {(0, 0)}},
            explored_tiles={Faction.WEI: {(1, -1)}},
            enabled=True,
        )
    )
    return world


@pytest.mark.parametrize(
    "orientation", [HexOrientation.FLAT_TOP, HexOrientation.POINTY_TOP]
)
@pytest.mark.parametrize("size", [1, 37.5, 50, 113])
@pytest.mark.parametrize(
    "tile", [(-101, -77), (-8, 3), (-7, 3), (0, 0), (11, -9), (90, 90)]
)
def test_cached_world_corners_are_numerically_identical_to_canonical(
    orientation, size, tile
):
    world = _world()
    renderer = _Renderer(world, orientation, size)
    presenter = IncrementalFogSurfacePresenter(renderer)

    legacy = tuple(renderer.hex_converter.get_hex_corners(*tile))
    cached = presenter._tile_world_corners(tile)

    assert cached == legacy
    assert isinstance(cached, tuple)
    assert all(isinstance(point, tuple) for point in cached)


def test_camera_and_zoom_changes_reuse_world_geometry_but_recompute_screen_points(
    monkeypatch,
):
    world = _world()
    presenter = IncrementalFogSurfacePresenter(_Renderer(world))
    surface = pygame.Surface((320, 240), pygame.SRCALPHA)
    captured = []

    def capture_polygon(_surface, _color, points):
        captured.append(tuple(points))

    monkeypatch.setattr(pygame.draw, "polygon", capture_polygon)
    first_corners = presenter._tile_world_corners((3, -2))
    before = presenter.diagnostic_snapshot()
    presenter._draw_tile_state(
        surface, (3, -2), [100.25, 80.75], 0.15, set(), set(), clear_first=False
    )
    first_points = captured.pop()
    presenter._draw_tile_state(
        surface, (3, -2), [-220.5, 310.125], 1.75, set(), set(), clear_first=False
    )
    second_points = captured.pop()
    second_corners = presenter._tile_world_corners((3, -2))
    after = presenter.diagnostic_snapshot()

    assert second_corners is first_corners
    assert first_points != second_points
    assert after["tile_world_corner_cache_entries"] == 1
    assert after["tile_world_corner_cache_misses"] - before[
        "tile_world_corner_cache_misses"
    ] == 0
    assert after["tile_world_corner_cache_hits"] - before[
        "tile_world_corner_cache_hits"
    ] == 3
    assert after["tile_world_corner_cache_resets"] == before[
        "tile_world_corner_cache_resets"
    ]


def test_geometry_signature_change_invalidates_world_corner_cache():
    world = _world()
    renderer = _Renderer(world)
    presenter = IncrementalFogSurfacePresenter(renderer)
    original = presenter._tile_world_corners((4, -3))

    renderer.hex_converter.size = 72
    size_changed = presenter._tile_world_corners((4, -3))
    after_size = presenter.diagnostic_snapshot()

    renderer.hex_converter.orientation = HexOrientation.POINTY_TOP
    orientation_changed = presenter._tile_world_corners((4, -3))
    after_orientation = presenter.diagnostic_snapshot()

    assert original != size_changed
    assert size_changed != orientation_changed
    assert after_size["tile_world_corner_cache_entries"] == 1
    assert after_size["tile_world_corner_cache_resets"] == 1
    assert after_orientation["tile_world_corner_cache_entries"] == 1
    assert after_orientation["tile_world_corner_cache_resets"] == 2
    assert after_orientation["tile_world_corner_cache_misses"] == 3


def test_legacy_world_corner_path_bypasses_cache_and_counters():
    world = _world()
    presenter = IncrementalFogSurfacePresenter(_Renderer(world))
    presenter.set_tile_world_corner_cache_enabled(False)

    first = presenter._tile_world_corners((2, 7))
    second = presenter._tile_world_corners((2, 7))
    snapshot = presenter.diagnostic_snapshot()

    assert first == second
    assert first is not second
    assert snapshot["tile_world_corner_path"] == "legacy"
    assert snapshot["tile_world_corner_cache_entries"] == 0
    assert snapshot["tile_world_corner_cache_hits"] == 0
    assert snapshot["tile_world_corner_cache_misses"] == 0


def test_rendering_does_not_mutate_cached_world_corners():
    world = _world()
    presenter = IncrementalFogSurfacePresenter(_Renderer(world))
    surface = pygame.Surface((320, 240), pygame.SRCALPHA)
    corners = presenter._tile_world_corners((-9, 12))
    value_before = tuple(corners)

    presenter._draw_tile_state(
        surface,
        (-9, 12),
        [1249.9999999999998, 634.876543211],
        0.15,
        set(),
        set(),
        clear_first=False,
    )

    assert presenter._tile_world_corners((-9, 12)) is corners
    assert corners == value_before


@pytest.mark.parametrize(
    "orientation", [HexOrientation.FLAT_TOP, HexOrientation.POINTY_TOP]
)
@pytest.mark.parametrize(
    "camera_offset",
    [
        (1240.0, 634.0),
        (1240.25, 634.25),
        (1240.5, 634.5),
        (1240.75, 634.75),
        (1249.9999999999998, 634.876543211),
    ],
)
def test_cached_and_legacy_world_corners_render_pixel_exact_fog(
    orientation, camera_offset
):
    visible_tiles = {(-2, 1), (-1, 0), (0, 0), (1, -1), (2, -2), (3, 4)}

    legacy_world = _world()
    legacy_presenter = IncrementalFogSurfacePresenter(
        _Renderer(legacy_world, orientation)
    )
    legacy_presenter.set_tile_world_corner_cache_enabled(False)
    legacy = legacy_presenter.update_surface(
        visible_tiles, list(camera_offset), 0.15
    )

    cached_world = _world()
    cached_presenter = IncrementalFogSurfacePresenter(
        _Renderer(cached_world, orientation)
    )
    cached = cached_presenter.update_surface(
        visible_tiles, list(camera_offset), 0.15
    )

    assert pygame.image.tobytes(cached, "RGBA") == pygame.image.tobytes(
        legacy, "RGBA"
    )
    assert cached_presenter.presentation_rect == legacy_presenter.presentation_rect
    snapshot = cached_presenter.diagnostic_snapshot()
    fogged_tiles = visible_tiles - {(0, 0)}
    assert snapshot["tile_world_corner_cache_entries"] == len(fogged_tiles)
    assert snapshot["tile_world_corner_cache_misses"] == len(fogged_tiles)
    assert snapshot["full_build_visible_no_fog_skipped_tiles"] == 1
