import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame
import pytest

from framework.ecs.world import World

from rotk_env.components import FogOfWar, GameState, UIState
from rotk_env.prefabs.config import Faction, GameConfig, HexOrientation
from rotk_env.systems.fog_surface_presenter import IncrementalFogSurfacePresenter
from rotk_env.utils.fog_visibility_journal import publish_fog_visibility_delta
from rotk_env.utils.hex_utils import HexConverter


class _Renderer:
    def __init__(self, world, orientation=HexOrientation.FLAT_TOP):
        self.world = world
        self.hex_converter = HexConverter(GameConfig.HEX_SIZE, orientation)


def setup_module():
    pygame.init()


def teardown_module():
    pygame.quit()


def _world(*, visible=(), explored=()):
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


def _fresh(tiles, *, visible=(), explored=(), camera=(160.25, 120.75), zoom=1.0):
    world = _world(visible=visible, explored=explored)
    presenter = IncrementalFogSurfacePresenter(_Renderer(world))
    surface = presenter.update_surface(set(tiles), list(camera), zoom)
    return world, presenter, surface


def _reference_surface(
    tiles,
    *,
    visible,
    explored,
    camera,
    zoom,
    orientation,
):
    surface = pygame.Surface(
        (GameConfig.WINDOW_WIDTH, GameConfig.WINDOW_HEIGHT), pygame.SRCALPHA
    )
    converter = HexConverter(GameConfig.HEX_SIZE, orientation)
    for tile in tiles:
        if tile in visible:
            continue
        points = [
            (
                int(round(world_x * zoom + camera[0])),
                int(round(world_y * zoom + camera[1])),
            )
            for world_x, world_y in converter.get_hex_corners(*tile)
        ]
        color = (
            GameConfig.FOG_EXPLORED_COLOR
            if tile in explored
            else GameConfig.FOG_UNEXPLORED_COLOR
        )
        pygame.draw.polygon(surface, color, points)
    return surface


@pytest.mark.parametrize(
    "orientation", [HexOrientation.FLAT_TOP, HexOrientation.POINTY_TOP]
)
@pytest.mark.parametrize("zoom", [0.1, 0.15, 0.5, 1.0, 3.0])
@pytest.mark.parametrize(
    "camera",
    [
        (160.0, 120.0),
        (160.25, 120.75),
        (160.5, 120.5),
        (160.75, 120.25),
        (160.123456789, -20.333333333),
    ],
)
def test_full_rebuild_is_pixel_exact_across_camera_zoom_and_orientation(
    monkeypatch, orientation, zoom, camera
):
    monkeypatch.setattr(GameConfig, "WINDOW_WIDTH", 320)
    monkeypatch.setattr(GameConfig, "WINDOW_HEIGHT", 240)
    tiles = {(-1, 0), (0, 0), (1, 0), (0, 1), (3, -2)}
    visible = {(0, 0), (3, -2)}
    explored = {(1, 0), (0, 1)}
    world = _world(visible=visible, explored=explored)
    presenter = IncrementalFogSurfacePresenter(_Renderer(world, orientation))
    surface = presenter.update_surface(tiles, list(camera), zoom)
    reference = _reference_surface(
        tiles,
        visible=visible,
        explored=explored,
        camera=camera,
        zoom=zoom,
        orientation=orientation,
    )

    assert _pixels(surface) == _pixels(reference)
    alpha_bounds = surface.get_bounding_rect(min_alpha=1)
    if alpha_bounds.width == 0:
        assert presenter.presentation_rect is None
    else:
        assert presenter.presentation_rect.contains(alpha_bounds)


def test_identical_geometry_reuses_surface_and_camera_change_rebuilds(monkeypatch):
    monkeypatch.setattr(GameConfig, "WINDOW_WIDTH", 320)
    monkeypatch.setattr(GameConfig, "WINDOW_HEIGHT", 240)
    tiles = {(0, 0), (1, 0)}
    _world_value, presenter, surface = _fresh(tiles)

    assert presenter.update_surface(tiles, [160.25, 120.75], 1.0) is surface
    assert presenter.update_surface(tiles, [160.5, 120.75], 1.0) is not surface


def test_incremental_reveal_and_hide_match_fresh_canonical_surface(monkeypatch):
    monkeypatch.setattr(GameConfig, "WINDOW_WIDTH", 320)
    monkeypatch.setattr(GameConfig, "WINDOW_HEIGHT", 240)
    tiles = {(0, 0), (1, 0), (0, 1)}
    camera = [160.25, 120.75]
    world, presenter, surface = _fresh(tiles, explored=tiles, camera=camera)

    fog = world.get_singleton_component(FogOfWar)
    fog.faction_vision[Faction.WEI].add((0, 0))
    publish_fog_visibility_delta(world, {Faction.WEI: {(0, 0)}})
    patched = presenter.update_surface(tiles, camera, 1.0)
    _w, _p, expected = _fresh(
        tiles, visible={(0, 0)}, explored=tiles, camera=camera
    )
    assert patched is surface
    assert _pixels(patched) == _pixels(expected)

    fog.faction_vision[Faction.WEI].remove((0, 0))
    publish_fog_visibility_delta(world, {Faction.WEI: {(0, 0)}})
    patched = presenter.update_surface(tiles, camera, 1.0)
    _w, _p, expected = _fresh(tiles, explored=tiles, camera=camera)
    assert _pixels(patched) == _pixels(expected)


def test_all_visible_surface_is_transparent_and_needs_no_presentation_rect(monkeypatch):
    monkeypatch.setattr(GameConfig, "WINDOW_WIDTH", 320)
    monkeypatch.setattr(GameConfig, "WINDOW_HEIGHT", 240)
    tiles = {(0, 0), (1, 0)}
    _world_value, presenter, surface = _fresh(tiles, visible=tiles)

    assert surface.get_bounding_rect(min_alpha=1).width == 0
    assert presenter.presentation_rect is None


def test_presentation_rect_contains_alpha_and_bounded_blit_matches_full(monkeypatch):
    monkeypatch.setattr(GameConfig, "WINDOW_WIDTH", 320)
    monkeypatch.setattr(GameConfig, "WINDOW_HEIGHT", 240)
    tiles = {(0, 0), (1, 0), (0, 1)}
    _world_value, presenter, surface = _fresh(
        tiles, visible={(0, 0)}, explored={(1, 0)}
    )
    alpha_bounds = surface.get_bounding_rect(min_alpha=1)
    assert presenter.presentation_rect.contains(alpha_bounds)

    background = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    for y in range(background.get_height()):
        pygame.draw.line(background, (y % 251, 40, 190, 255), (0, y), (319, y))
    full = background.copy()
    full.blit(surface, (0, 0))
    bounded = background.copy()
    source = presenter.presentation_rect
    bounded.blit(surface, source.topleft, source)
    assert _pixels(bounded) == _pixels(full)


def test_newly_fogged_patch_expands_bounds_and_reveal_does_not_shrink(monkeypatch):
    monkeypatch.setattr(GameConfig, "WINDOW_WIDTH", 640)
    monkeypatch.setattr(GameConfig, "WINDOW_HEIGHT", 480)
    tiles = {(0, 0), (3, 0)}
    world, presenter, surface = _fresh(
        tiles, visible={(3, 0)}, explored=tiles, camera=(220.0, 220.0)
    )
    before = presenter.presentation_rect.copy()
    fog = world.get_singleton_component(FogOfWar)

    fog.faction_vision[Faction.WEI].remove((3, 0))
    publish_fog_visibility_delta(world, {Faction.WEI: {(3, 0)}})
    presenter.update_surface(tiles, [220.0, 220.0], 1.0)
    expanded = presenter.presentation_rect.copy()
    assert expanded.contains(surface.get_bounding_rect(min_alpha=1))
    assert expanded.right > before.right

    fog.faction_vision[Faction.WEI].add((3, 0))
    publish_fog_visibility_delta(world, {Faction.WEI: {(3, 0)}})
    presenter.update_surface(tiles, [220.0, 220.0], 1.0)
    assert presenter.presentation_rect == expanded


def test_world_corner_cache_is_camera_independent_and_geometry_sensitive():
    presenter = IncrementalFogSurfacePresenter(_Renderer(_world()))
    first = presenter._tile_world_corners((2, -3))
    assert presenter._tile_world_corners((2, -3)) is first

    presenter.renderer.hex_converter.size += 1
    size_changed = presenter._tile_world_corners((2, -3))
    assert size_changed is not first
    assert size_changed != first

    presenter.renderer.hex_converter.orientation = HexOrientation.POINTY_TOP
    orientation_changed = presenter._tile_world_corners((2, -3))
    assert orientation_changed is not size_changed
    assert orientation_changed != size_changed
