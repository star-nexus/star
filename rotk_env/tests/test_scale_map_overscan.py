import os
from types import SimpleNamespace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from framework.engine import RMS
from rotk_env.components import MapData
from rotk_env.prefabs.config import GameConfig
from rotk_env.systems.scale_map_render_system import ScaleMapRenderSystem


class _World:
    def __init__(self, map_data):
        self.map_data = map_data

    def get_singleton_component(self, component_type):
        if component_type is MapData:
            return self.map_data
        return None


def setup_module():
    pygame.init()
    if pygame.display.get_surface() is None:
        pygame.display.set_mode((32, 32))


def teardown_module():
    pygame.quit()


def test_pan_reuses_overscan_and_zoom_keeps_direct_fallback(monkeypatch):
    renderer = ScaleMapRenderSystem()
    renderer.world = _World(SimpleNamespace(map_id="test", tiles={}))
    renderer.OVERSCAN_MARGIN_PX = 128

    direct_calls = []
    build_calls = []
    draw_calls = []

    monkeypatch.setattr(
        renderer,
        "_render_terrain_direct",
        lambda *args, **kwargs: direct_calls.append(args),
    )

    def fake_build(*args, **kwargs):
        build_calls.append(args)
        return pygame.Surface((8, 8), pygame.SRCALPHA), pygame.Rect(0, 0, 8, 8), 0

    monkeypatch.setattr(renderer, "_build_overscan_surface", fake_build)
    monkeypatch.setattr(
        renderer,
        "_draw_overscan",
        lambda camera_offset: draw_calls.append(tuple(camera_offset)) or 1,
    )

    # First frame at a new zoom remains on the direct path.
    renderer._render_map_optimized(set(), [0.0, 0.0], 1.0)
    assert len(direct_calls) == 1
    assert build_calls == []

    # Second frame at the same zoom builds the overscan raster once.
    renderer._render_map_optimized(set(), [0.0, 0.0], 1.0)
    assert len(build_calls) == 1
    assert len(draw_calls) == 1

    # Camera motion inside the margin reuses that same raster.
    renderer._render_map_optimized(set(), [100.0, 0.0], 1.0)
    assert len(build_calls) == 1
    assert len(direct_calls) == 1
    assert len(draw_calls) == 2

    # Crossing the margin rebuilds at the new camera anchor, but still avoids
    # hundreds of per-tile commands on that frame.
    renderer._render_map_optimized(set(), [160.0, 0.0], 1.0)
    assert len(build_calls) == 2
    assert len(direct_calls) == 1
    assert len(draw_calls) == 3

    # A new zoom does not trigger a large raster build immediately.
    renderer._render_map_optimized(set(), [160.0, 0.0], 1.1)
    assert len(build_calls) == 2
    assert len(direct_calls) == 2

    # If zoom stabilizes, the next frame installs a new overscan cache.
    renderer._render_map_optimized(set(), [160.0, 0.0], 1.1)
    assert len(build_calls) == 3
    assert len(draw_calls) == 4


def test_overscan_draw_crops_wide_empty_regions(monkeypatch):
    renderer = ScaleMapRenderSystem()
    renderer.OVERSCAN_MARGIN_PX = 20
    monkeypatch.setattr(GameConfig, "WINDOW_WIDTH", 100)
    monkeypatch.setattr(GameConfig, "WINDOW_HEIGHT", 60)

    renderer._overscan_surface = pygame.Surface((140, 100), pygame.SRCALPHA)
    renderer._overscan_camera_offset = (0.0, 0.0)
    # Pretend the actual terrain occupies only a narrow central strip.
    renderer._overscan_content_rect = pygame.Rect(50, 20, 30, 60)

    calls = []
    monkeypatch.setattr(
        RMS,
        "draw",
        lambda surface, dest, area=None, **kwargs: calls.append((dest, area)) or RMS,
    )

    pixels = renderer._draw_overscan([0.0, 0.0])

    assert len(calls) == 1
    dest, area = calls[0]
    assert dest == (30, 0)
    assert area == pygame.Rect(50, 20, 30, 60)
    assert pixels == 30 * 60
