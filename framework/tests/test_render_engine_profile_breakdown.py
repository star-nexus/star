import os
from collections import defaultdict

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame
import pytest

from framework.ecs import profiling
from framework.engine import renders as renders_module
from framework.engine.renders import RenderEngine
from performance_profiler import PerformanceProfiler


def setup_module():
    pygame.init()
    if pygame.display.get_surface() is None:
        pygame.display.set_mode((32, 32))


def teardown_module():
    pygame.quit()


def _bare_renderer() -> RenderEngine:
    renderer = object.__new__(RenderEngine)
    renderer._screen = pygame.Surface((20, 8), pygame.SRCALPHA)
    renderer.current_layer = 0
    renderer._render_queue = defaultdict(list)
    renderer._initialized = True
    return renderer


def _profile_update(renderer: RenderEngine):
    profiler = PerformanceProfiler(sample_window=10)
    profiler.enabled = True
    previous = profiling.get_profiler()
    profiling.set_profiler(profiler)
    try:
        profiler.start_frame()
        with profiler.time_system("render_engine", category="render"):
            renderer.update()
        profiler.end_frame()
    finally:
        profiling.set_profiler(previous)
    return profiler.get_stats()


def test_render_engine_breakdown_preserves_semantics_and_closes_parent_budget():
    renderer = _bare_renderer()
    red = pygame.Surface((4, 4), pygame.SRCALPHA)
    green = pygame.Surface((4, 4), pygame.SRCALPHA)
    red.fill((255, 0, 0, 255))
    green.fill((0, 255, 0, 255))

    # Two consecutive plain blits form one batch run.
    renderer.draw(red, (0, 0))
    renderer.draw(green, (4, 0))
    # Geometry is an ordering barrier.
    renderer.rect((0, 0, 255, 255), pygame.Rect(8, 0, 2, 2))
    # A lone plain blit is still a batchable run, but executes singly.
    renderer.draw(red, (10, 0))
    # area != None preserves the existing non-batch blit path.
    renderer.draw(green, (14, 0), area=pygame.Rect(0, 0, 2, 2))

    stats = _profile_update(renderer)

    assert not renderer._render_queue
    assert renderer.screen.get_at((1, 1))[:3] == (255, 0, 0)
    assert renderer.screen.get_at((5, 1))[:3] == (0, 255, 0)
    assert renderer.screen.get_at((8, 1))[:3] == (0, 0, 255)
    assert renderer.screen.get_at((11, 1))[:3] == (255, 0, 0)
    assert renderer.screen.get_at((14, 1))[:3] == (0, 255, 0)

    sections = stats["sections"]
    for name in (
        "render_engine",
        "render_queue_prepare",
        "render_queue_submit",
        "render_batch_pack",
        "render_batch_blits",
        "render_scalar_execute",
        "render_queue_clear",
    ):
        assert name in sections

    parent = sections["render_engine"]
    direct_children = sum(
        sections[name]["inclusive_ms"]
        for name in (
            "render_queue_prepare",
            "render_queue_submit",
            "render_queue_clear",
        )
    )
    assert parent["inclusive_ms"] == pytest.approx(
        parent["self_ms"] + direct_children,
        abs=0.01,
    )

    submit = sections["render_queue_submit"]
    submit_children = sum(
        sections[name]["inclusive_ms"]
        for name in (
            "render_batch_pack",
            "render_batch_blits",
            "render_scalar_execute",
        )
    )
    assert submit["inclusive_ms"] == pytest.approx(
        submit["self_ms"] + submit_children,
        abs=0.01,
    )

    metadata = stats["metadata"]
    assert metadata["scale_render_queue_last_commands"] == 5
    assert metadata["scale_render_queue_last_layers"] == 1
    assert metadata["scale_render_queue_last_batch_runs"] == 2
    assert metadata["scale_render_queue_last_simple_blits"] == 3
    assert metadata["scale_render_queue_last_blit_batches"] == 1
    assert metadata["scale_render_queue_last_scalar_commands"] == 2
    assert metadata["scale_render_queue_last_max_batch_size"] == 2
    assert metadata["scale_render_pixel_metrics_enabled"] is False


def test_optional_pixel_metrics_measure_source_and_screen_clipped_work(monkeypatch):
    renderer = _bare_renderer()
    left = pygame.Surface((4, 4), pygame.SRCALPHA)
    right = pygame.Surface((4, 4), pygame.SRCALPHA)
    left.fill((255, 0, 0, 255))
    right.fill((0, 255, 0, 255))

    # Both are plain blits in one batch. Half of each surface falls outside the
    # 20x8 screen, so 32 source pixels become 16 screen-clipped pixels.
    renderer.draw(left, (-2, 0))
    renderer.draw(right, (18, 0))

    monkeypatch.setattr(renders_module, "_RENDER_PIXEL_METRICS_ENABLED", True)
    stats = _profile_update(renderer)
    metadata = stats["metadata"]

    assert metadata["scale_render_pixel_metrics_enabled"] is True
    assert metadata["scale_render_queue_last_plain_blit_source_pixels"] == 32
    assert metadata["scale_render_queue_last_plain_blit_clipped_pixels"] == 16
    assert metadata["scale_render_queue_last_plain_blit_max_surface_pixels"] == 16
    assert metadata["scale_render_queue_last_plain_blit_max_batch_source_pixels"] == 32
    assert metadata["scale_render_queue_last_plain_blit_max_batch_clipped_pixels"] == 16
