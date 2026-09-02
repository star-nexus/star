import os
from collections import defaultdict

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from framework.ecs import profiling
from framework.engine import RMS
from performance_profiler import PerformanceProfiler
from rotk_env.testing.render_presentation_ablation import (
    _fog_render_without_present,
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

    # A positive pixel count without the expected command must be visible in
    # formal metadata rather than silently masquerading as a valid ablation.
    wrapped = _make_terrain_draw_without_present(lambda self, camera_offset: 16)
    stats = _with_profiler(lambda: wrapped(renderer, [0.0, 0.0]))

    metadata = stats["metadata"]
    assert metadata["scale_render_terrain_present_last_suppressed_commands"] == 0
    assert metadata["scale_render_terrain_present_last_suppressed_pixels"] == 0
    assert metadata["scale_render_terrain_present_last_suppression_missed"] is True
