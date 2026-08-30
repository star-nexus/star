"""Regression tests for large-map viewport culling."""

from framework import World

from rotk_env.components import MapData
from rotk_env.prefabs.config import GameConfig
from rotk_env.systems.map_render_system import MapRenderSystem


def _map_data(size: int = 33) -> MapData:
    half = size // 2
    tiles = {
        (col, row): 1
        for col in range(-half, half + 1)
        for row in range(-half, half + 1)
    }
    return MapData(width=size, height=size, tiles=tiles, map_id="culling-test")


def _renderer() -> MapRenderSystem:
    world = World()
    world.add_singleton_component(_map_data())
    renderer = MapRenderSystem()
    # Culling itself does not need pygame display/texture initialization.
    renderer.world = world
    return renderer


def test_zoomed_panned_large_map_keeps_on_screen_upper_tiles(monkeypatch):
    """A visible upper-map tile must not disappear when zooming in.

    The old q/r pre-search estimated the row around the screen origin with the
    wrong sign/spacing. At this camera position it searched only through row 8,
    even though row 10 is plainly on screen, so terrain vanished while overlays
    that did not use this culling path remained visible.
    """
    monkeypatch.setattr(GameConfig, "WINDOW_WIDTH", 1920)
    monkeypatch.setattr(GameConfig, "WINDOW_HEIGHT", 1080)
    renderer = _renderer()

    camera_offset = [960.0, 1500.0]
    zoom = 0.8
    world_x, world_y = renderer.hex_converter.hex_to_pixel(0, 10)
    screen_x = world_x * zoom + camera_offset[0]
    screen_y = world_y * zoom + camera_offset[1]
    assert 0 <= screen_x <= GameConfig.WINDOW_WIDTH
    assert 0 <= screen_y <= GameConfig.WINDOW_HEIGHT

    visible = renderer._get_visible_tiles_smart(camera_offset, zoom)
    assert (0, 10) in visible


def test_viewport_resize_invalidates_visible_tile_cache(monkeypatch):
    """Resizable windows must not reuse a culling set from the old viewport."""
    monkeypatch.setattr(GameConfig, "WINDOW_WIDTH", 1200)
    monkeypatch.setattr(GameConfig, "WINDOW_HEIGHT", 800)
    renderer = _renderer()

    camera_offset = [600.0, 400.0]
    zoom = 1.0
    small = renderer._get_visible_tiles_smart(camera_offset, zoom)
    assert (15, 0) not in small

    monkeypatch.setattr(GameConfig, "WINDOW_WIDTH", 1920)
    monkeypatch.setattr(GameConfig, "WINDOW_HEIGHT", 1080)
    large = renderer._get_visible_tiles_smart(camera_offset, zoom)
    assert (15, 0) in large
    assert len(large) > len(small)
