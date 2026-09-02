import os
from collections import defaultdict

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from framework.ecs import profiling
from framework.engine import RMS
from performance_profiler import PerformanceProfiler
from rotk_env.testing.render_presentation_ablation import (
    _capture_terrain_surface_state,
    _fog_render_without_present,
    _make_terrain_draw_variant,
    _make_terrain_draw_without_present,
)


def setup_module():
    pygame.init()
    if pygame.display.get_surface() is None:
        pygame.display.set_mode((32, 32))


def teardown_module():
    pygame.quit()


def _with_profiler(fn):
    profiler = PerformanceProfiler(sample_window=10)
    profiler.enabled = True
    previous = profiling.get_profiler()
    profiling.set_profiler(profiler)
    try:
        profiler.start_frame()
        fn()
        profiler.end_frame()
    finally:
        profiling.set_profiler(previous)
    return profiler.get_stats()


def test_fog_ablation_keeps_surface_update_but_does_not_enqueue_present(monkeypatch):
    surface = pygame.Surface((10, 5), pygame.SRCALPHA)

    class DummyPresenter:
        def __init__(self):
            self.calls = 0
            self.presentation_rect = pygame.Rect(2, 1, 4, 3)

        def update_surface(self, visible_tiles, camera_offset, zoom):
            self.calls += 1
            return surface

    presenter = DummyPresenter()
    monkeypatch.setattr(RMS, "_render_queue", defaultdict(list))
    monkeypatch.setattr(RMS, "current_layer", 0)

    stats = _with_profiler(
        lambda: _fog_render_without_present(presenter, set(), [0.0, 0.0], 1.0)
    )

    assert presenter.calls == 1
    assert sum(len(commands) for commands in RMS._render_queue.values()) == 0
    metadata = stats["metadata"]
    assert metadata["scale_render_ablate_fog_present"] is True
    assert metadata["scale_render_fog_present_last_suppressed_pixels"] == 12


def test_terrain_ablation_removes_only_new_overscan_command(monkeypatch):
    overscan = pygame.Surface((20, 10), pygame.SRCALPHA)
    unrelated = pygame.Surface((2, 2), pygame.SRCALPHA)

    class DummyRenderer:
        _overscan_surface = overscan

    renderer = DummyRenderer()
    monkeypatch.setattr(RMS, "_render_queue", defaultdict(list))
    monkeypatch.setattr(RMS, "current_layer", 0)

    # Existing queue content must survive the ablation.
    RMS.draw(unrelated, (0, 0))
    existing = RMS._render_queue[0][0]

    def original(self, camera_offset):
        RMS.draw(self._overscan_surface, (3, 4), area=pygame.Rect(1, 2, 5, 6))
        return 30

    wrapped = _make_terrain_draw_without_present(original)
    stats = _with_profiler(lambda: wrapped(renderer, [0.0, 0.0]))

    commands = RMS._render_queue[0]
    assert commands == [existing]
    metadata = stats["metadata"]
    assert metadata["scale_render_ablate_terrain_present"] is True
    assert metadata["scale_render_terrain_present_last_suppressed_commands"] == 1
    assert metadata["scale_render_terrain_present_last_suppressed_pixels"] == 30
    assert metadata["scale_render_terrain_present_last_suppression_missed"] is False


def test_terrain_ablation_exposes_suppression_miss(monkeypatch):
    class DummyRenderer:
        _overscan_surface = pygame.Surface((4, 4), pygame.SRCALPHA)

    renderer = DummyRenderer()
    monkeypatch.setattr(RMS, "_render_queue", defaultdict(list))
    monkeypatch.setattr(RMS, "current_layer", 0)

    wrapped = _make_terrain_draw_without_present(lambda self, camera_offset: 16)
    stats = _with_profiler(lambda: wrapped(renderer, [0.0, 0.0]))

    metadata = stats["metadata"]
    assert metadata["scale_render_terrain_present_last_suppressed_commands"] == 0
    assert metadata["scale_render_terrain_present_last_suppressed_pixels"] == 0
    assert metadata["scale_render_terrain_present_last_suppression_missed"] is True


def test_terrain_alpha_diagnostics_count_final_content_alpha(monkeypatch):
    screen = pygame.display.get_surface()
    surface = pygame.Surface((4, 2), pygame.SRCALPHA)
    surface.fill((0, 0, 0, 0))
    for point in ((0, 0), (1, 0), (2, 0)):
        surface.set_at(point, (10, 20, 30, 255))
    for point in ((3, 0), (0, 1)):
        surface.set_at(point, (10, 20, 30, 128))

    class DummyRenderer:
        _overscan_surface = surface
        _overscan_content_rect = pygame.Rect(0, 0, 4, 2)

    renderer = DummyRenderer()
    monkeypatch.setattr(RMS, "_screen", screen)

    stats = _with_profiler(
        lambda: _capture_terrain_surface_state(renderer, build_opaque=False)
    )
    metadata = stats["metadata"]

    assert metadata["scale_render_terrain_source_srcalpha"] is True
    assert metadata["scale_render_terrain_alpha_total_pixels"] == 8
    assert metadata["scale_render_terrain_alpha_opaque_pixels"] == 3
    assert metadata["scale_render_terrain_alpha_partial_pixels"] == 2
    assert metadata["scale_render_terrain_alpha_transparent_pixels"] == 3
    assert metadata["scale_render_terrain_alpha_opaque_ratio"] == 3 / 8


def test_opaque_flatten_variant_preserves_area_blit_pixels(monkeypatch):
    screen = pygame.display.get_surface()
    source = pygame.Surface((6, 4), pygame.SRCALPHA)
    source.fill((0, 0, 0, 0))
    source.set_at((2, 1), (220, 40, 20, 255))
    source.set_at((3, 1), (20, 200, 50, 128))
    source.set_at((2, 2), (40, 60, 220, 64))
    source.set_at((3, 2), (80, 90, 100, 0))

    class DummyRenderer:
        _overscan_surface = source
        _overscan_content_rect = pygame.Rect(1, 1, 4, 2)

    renderer = DummyRenderer()
    monkeypatch.setattr(RMS, "_screen", screen)
    _with_profiler(
        lambda: _capture_terrain_surface_state(renderer, build_opaque=True)
    )

    opaque = renderer._star_terrain_opaque_surface
    assert not bool(opaque.get_flags() & pygame.SRCALPHA)
    assert opaque.get_bitsize() == screen.get_bitsize()
    assert opaque.get_masks() == screen.get_masks()

    monkeypatch.setattr(RMS, "_render_queue", defaultdict(list))
    monkeypatch.setattr(RMS, "current_layer", 0)

    original_area = pygame.Rect(2, 1, 2, 2)
    destination = (3, 2)

    def original(self, camera_offset):
        RMS.draw(self._overscan_surface, destination, area=original_area)
        return original_area.width * original_area.height

    wrapped = _make_terrain_draw_variant(original, "opaque_flatten")
    stats = _with_profiler(lambda: wrapped(renderer, [0.0, 0.0]))
    command = RMS._render_queue[0][-1]

    assert command.surface is opaque
    assert command.dest == destination
    assert command.area == pygame.Rect(1, 0, 2, 2)
    assert stats["metadata"][
        "scale_render_terrain_present_variant_last_replacement_missed"
    ] is False

    expected = pygame.Surface((8, 6)).convert(screen)
    expected.fill((135, 141, 106))
    expected.blit(source, destination, original_area)

    actual = pygame.Surface((8, 6)).convert(screen)
    actual.fill((135, 141, 106))
    command.execute(actual)

    assert pygame.image.tobytes(actual, "RGB") == pygame.image.tobytes(expected, "RGB")
