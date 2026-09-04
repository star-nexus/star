import os
from types import SimpleNamespace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from framework.engine import RMS
from rotk_env.components import MapData, Terrain
from rotk_env.prefabs.config import GameConfig, TerrainType
from rotk_env.systems.window_map_render_system import WindowMapRenderSystem


class _World:
    def __init__(self, map_data, components=None):
        self.map_data = map_data
        self.components = components or {}

    def get_singleton_component(self, component_type):
        if component_type is MapData:
            return self.map_data
        return None

    def get_component(self, entity, component_type):
        component = self.components.get(entity)
        return component if isinstance(component, component_type) else None


def setup_module():
    pygame.init()
    if pygame.display.get_surface() is None:
        pygame.display.set_mode((32, 32))


def teardown_module():
    pygame.quit()


def test_pan_reuses_overscan_and_zoom_keeps_direct_fallback(monkeypatch):
    renderer = WindowMapRenderSystem()
    renderer.world = _World(SimpleNamespace(map_id="test", tiles={}))
    renderer.OVERSCAN_MARGIN_PX = 128
    monkeypatch.setattr(GameConfig, "WINDOW_WIDTH", 100)
    monkeypatch.setattr(GameConfig, "WINDOW_HEIGHT", 60)

    direct_calls = []
    draw_calls = []

    monkeypatch.setattr(
        renderer,
        "_render_terrain_direct",
        lambda *args, **kwargs: direct_calls.append(args),
    )

    monkeypatch.setattr(
        renderer,
        "_draw_overscan",
        lambda camera_offset: draw_calls.append(tuple(camera_offset)) or 1,
    )

    # First frame at a new zoom remains on the direct path.
    renderer._render_map_optimized(set(), [0.0, 0.0], 1.0)
    assert len(direct_calls) == 1
    assert renderer._overscan_build_count == 0

    # An empty-map staging job completes immediately on the second stable frame.
    renderer._render_map_optimized(set(), [0.0, 0.0], 1.0)
    assert renderer._overscan_build_count == 1
    assert len(draw_calls) == 1

    # Camera motion inside the margin reuses that same raster.
    renderer._render_map_optimized(set(), [100.0, 0.0], 1.0)
    assert renderer._overscan_build_count == 1
    assert len(direct_calls) == 1
    assert len(draw_calls) == 2

    # Crossing the margin creates another staging build.
    renderer._render_map_optimized(set(), [160.0, 0.0], 1.0)
    assert renderer._overscan_build_count == 2
    assert len(direct_calls) == 1
    assert len(draw_calls) == 3

    # A new zoom does not trigger a large raster build immediately.
    renderer._render_map_optimized(set(), [160.0, 0.0], 1.1)
    assert renderer._overscan_build_count == 2
    assert len(direct_calls) == 2

    # If zoom stabilizes, the next frame installs a new overscan cache.
    renderer._render_map_optimized(set(), [160.0, 0.0], 1.1)
    assert renderer._overscan_build_count == 3
    assert len(draw_calls) == 4


def test_overscan_build_is_incremental_and_uses_direct_fallback(monkeypatch):
    tiles = {(q, 0): q for q in range(6)}
    components = {entity: Terrain(TerrainType.PLAIN) for entity in tiles.values()}
    renderer = WindowMapRenderSystem()
    renderer.world = _World(SimpleNamespace(map_id="test", tiles=tiles), components)
    renderer.OVERSCAN_MARGIN_PX = 10
    renderer.OVERSCAN_BUILD_MAX_ITEMS_PER_STEP = 1
    renderer.OVERSCAN_BUILD_BUDGET_MS = 100.0
    monkeypatch.setattr(GameConfig, "WINDOW_WIDTH", 100)
    monkeypatch.setattr(GameConfig, "WINDOW_HEIGHT", 60)

    direct_calls = []
    monkeypatch.setattr(
        renderer,
        "_render_terrain_direct",
        lambda *args, **kwargs: direct_calls.append(args),
    )
    monkeypatch.setattr(renderer, "_draw_overscan", lambda _offset: 1)

    renderer._render_map_optimized(set(tiles), [0.0, 0.0], 1.0)
    renderer._render_map_optimized(set(tiles), [0.0, 0.0], 1.0)

    assert renderer._overscan_build_count == 0
    assert renderer._overscan_build_job is not None
    assert len(direct_calls) == 2

    for _ in range(20):
        renderer._render_map_optimized(set(tiles), [0.0, 0.0], 1.0)
        if renderer._overscan_build_count:
            break

    assert renderer._overscan_build_count == 1
    assert renderer._overscan_build_job is None


def test_pan_rebuild_fallback_draws_only_tiles_outside_cached_overlap(monkeypatch):
    map_data = SimpleNamespace(map_id="test", tiles={(20, 20): 1, (100, 20): 2})
    renderer = WindowMapRenderSystem()
    renderer.world = _World(map_data)
    renderer.OVERSCAN_MARGIN_PX = 20
    monkeypatch.setattr(GameConfig, "WINDOW_WIDTH", 100)
    monkeypatch.setattr(GameConfig, "WINDOW_HEIGHT", 60)
    monkeypatch.setattr(GameConfig, "HEX_SIZE", 5)
    monkeypatch.setattr(renderer.hex_converter, "hex_to_pixel", lambda q, r: (q, r))

    renderer._overscan_surface = pygame.Surface((140, 100), pygame.SRCALPHA)
    renderer._overscan_content_rect = renderer._overscan_surface.get_rect()
    renderer._overscan_camera_offset = (0.0, 0.0)
    renderer._overscan_zoom_key = renderer._zoom_cache_key(1.0)
    renderer._overscan_map_key = renderer._map_cache_key(map_data)
    renderer._overscan_viewport = (100, 60)

    direct_calls = []
    monkeypatch.setattr(
        renderer,
        "_render_terrain_direct",
        lambda _map, tiles, *_args: direct_calls.append(set(tiles)),
    )
    monkeypatch.setattr(renderer, "_draw_overscan", lambda _offset: 1)

    direct_count = renderer._render_direct_outside_cached_overlap(
        map_data,
        set(map_data.tiles),
        [30.0, 0.0],
        1.0,
    )

    assert direct_count == 1
    assert direct_calls == [{(100, 20)}]


def test_overscan_draw_crops_wide_empty_regions(monkeypatch):
    renderer = WindowMapRenderSystem()
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
