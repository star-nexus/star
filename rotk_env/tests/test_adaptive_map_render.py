import os
from types import SimpleNamespace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from framework.engine import RMS
from rotk_env.components import MapData
from rotk_env.systems.fast_render_systems import FastMapRenderSystem


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


def test_camera_motion_stays_direct_then_stationary_view_rasterizes(monkeypatch):
    renderer = FastMapRenderSystem()
    renderer.world = _World(SimpleNamespace(map_id="test", tiles={}))

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
        return pygame.Surface((8, 8), pygame.SRCALPHA)

    monkeypatch.setattr(renderer, "_build_terrain_surface", fake_build)
    monkeypatch.setattr(RMS, "draw", lambda *args, **kwargs: draw_calls.append(args) or RMS)

    # Continuously changing camera state: never build a full-window raster.
    renderer._render_map_optimized(set(), [0.0, 0.0], 1.0)
    renderer._render_map_optimized(set(), [10.0, 0.0], 1.0)
    renderer._render_map_optimized(set(), [20.0, 0.0], 1.0)

    assert len(direct_calls) == 3
    assert build_calls == []

    # Second frame at the exact same camera state builds once; following frames
    # reuse that raster rather than rebuilding it.
    renderer._render_map_optimized(set(), [20.0, 0.0], 1.0)
    assert len(build_calls) == 1

    renderer._render_map_optimized(set(), [20.0, 0.0], 1.0)
    assert len(build_calls) == 1
    assert len(draw_calls) == 2
