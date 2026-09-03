import os
from types import SimpleNamespace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from framework.engine import RMS
from rotk_env.prefabs.config import GameConfig
from rotk_env.systems.optimized_render_systems import MapRenderSystem
from rotk_env.systems.terrain_presentation_cache import OpaqueTerrainPresentationMixin


class _DummyBase:
    OVERSCAN_MARGIN_PX = 20

    def __init__(self):
        self._overscan_surface = None
        self._overscan_content_rect = pygame.Rect(0, 0, 0, 0)
        self._overscan_camera_offset = None
        self._overscan_build_job = None

    def _invalidate_fast_caches(self):
        self._overscan_surface = None
        self._overscan_content_rect = pygame.Rect(0, 0, 0, 0)
        self._overscan_camera_offset = None

    def _install_completed_job(self, job):
        self._overscan_surface = job.surface
        self._overscan_content_rect = job.content_rect
        self._overscan_camera_offset = job.camera_offset
        self._overscan_build_job = None

    def _install_overscan(self, map_data, camera_offset, zoom):
        return None

    def _advance_overscan_build(self):
        return False

    def _draw_overscan(self, camera_offset):
        raise AssertionError("opaque cache unexpectedly fell back to base draw")


class _Renderer(OpaqueTerrainPresentationMixin, _DummyBase):
    pass


def setup_module():
    pygame.init()
    if pygame.display.get_surface() is None:
        pygame.display.set_mode((64, 64))


def teardown_module():
    pygame.quit()


def _semantic_surface():
    surface = pygame.Surface((140, 100), pygame.SRCALPHA)
    surface.fill((0, 0, 0, 0))
    surface.fill((210, 70, 30, 255), pygame.Rect(50, 20, 15, 60))
    surface.fill((20, 160, 80, 128), pygame.Rect(65, 20, 10, 60))
    surface.fill((80, 90, 220, 64), pygame.Rect(75, 20, 5, 60))
    return surface


def test_interactive_map_renderer_uses_opaque_presentation_mixin():
    assert issubclass(MapRenderSystem, OpaqueTerrainPresentationMixin)


def test_compact_cache_is_non_srcalpha_and_pixel_equivalent(monkeypatch):
    renderer = _Renderer()
    source = _semantic_surface()
    content = pygame.Rect(50, 20, 30, 60)
    screen = pygame.display.get_surface()
    monkeypatch.setattr(RMS, "_screen", screen)

    renderer._build_terrain_present_cache(source, content)
    opaque = renderer._terrain_present_surface

    assert opaque is not None
    assert opaque.get_size() == content.size
    assert not bool(opaque.get_flags() & pygame.SRCALPHA)
    assert opaque.get_masks()[3] == 0
    assert opaque.get_pitch() == content.width * 4
    assert renderer._terrain_present_source_rect == content

    expected = pygame.Surface((100, 60)).convert(screen)
    expected.fill(renderer.TERRAIN_PRESENT_CLEAR_COLOR)
    expected.blit(source, (30, 0), content)

    actual = pygame.Surface((100, 60)).convert(screen)
    actual.fill(renderer.TERRAIN_PRESENT_CLEAR_COLOR)
    actual.blit(opaque, (30, 0))

    assert pygame.image.tobytes(actual, "RGB") == pygame.image.tobytes(expected, "RGB")


def test_draw_overscan_preserves_geometry_but_uses_compact_source(monkeypatch):
    renderer = _Renderer()
    source = _semantic_surface()
    renderer._overscan_surface = source
    renderer._overscan_content_rect = pygame.Rect(50, 20, 30, 60)
    renderer._overscan_camera_offset = (0.0, 0.0)
    renderer._build_terrain_present_cache(source, renderer._overscan_content_rect)

    monkeypatch.setattr(GameConfig, "WINDOW_WIDTH", 100)
    monkeypatch.setattr(GameConfig, "WINDOW_HEIGHT", 60)

    calls = []
    monkeypatch.setattr(
        RMS,
        "draw",
        lambda surface, dest, area=None, **kwargs: calls.append((surface, dest, area)) or RMS,
    )

    pixels = renderer._draw_overscan([0.0, 0.0])

    assert pixels == 30 * 60
    assert len(calls) == 1
    submitted, dest, area = calls[0]
    assert submitted is renderer._terrain_present_surface
    assert dest == (30, 0)
    assert area == pygame.Rect(0, 0, 30, 60)
    assert not bool(submitted.get_flags() & pygame.SRCALPHA)


def test_incremental_job_install_builds_cache_atomically(monkeypatch):
    renderer = _Renderer()
    source = _semantic_surface()
    screen = pygame.display.get_surface()
    monkeypatch.setattr(RMS, "_screen", screen)
    job = SimpleNamespace(
        surface=source,
        content_rect=pygame.Rect(50, 20, 30, 60),
        camera_offset=(0.0, 0.0),
    )

    renderer._install_completed_job(job)

    assert renderer._overscan_surface is source
    assert renderer._terrain_present_surface is not None
    assert renderer._terrain_present_source_rect == job.content_rect
    assert not bool(renderer._terrain_present_surface.get_flags() & pygame.SRCALPHA)


def test_cache_invalidation_drops_presentation_copy(monkeypatch):
    renderer = _Renderer()
    source = _semantic_surface()
    monkeypatch.setattr(RMS, "_screen", pygame.display.get_surface())
    renderer._build_terrain_present_cache(source, pygame.Rect(50, 20, 30, 60))
    assert renderer._terrain_present_surface is not None

    renderer._invalidate_fast_caches()

    assert renderer._terrain_present_surface is None
    assert renderer._terrain_present_source_rect == pygame.Rect(0, 0, 0, 0)
