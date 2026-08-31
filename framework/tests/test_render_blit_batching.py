import os
from collections import defaultdict

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from framework.engine.renders import BlitCommand, RenderEngine


def setup_module():
    pygame.init()
    if pygame.display.get_surface() is None:
        pygame.display.set_mode((32, 32))


def teardown_module():
    pygame.quit()


def _bare_renderer() -> RenderEngine:
    # Bypass the singleton constructor: this test must not mutate the global RMS
    # queue/screen used by other renderer tests in the same process.
    renderer = object.__new__(RenderEngine)
    renderer._screen = pygame.Surface((16, 8), pygame.SRCALPHA)
    renderer.current_layer = 0
    renderer._render_queue = defaultdict(list)
    renderer._initialized = True
    return renderer


def test_consecutive_plain_blits_use_batch_path(monkeypatch):
    renderer = _bare_renderer()
    left = pygame.Surface((4, 4), pygame.SRCALPHA)
    right = pygame.Surface((4, 4), pygame.SRCALPHA)
    left.fill((255, 0, 0, 255))
    right.fill((0, 255, 0, 255))

    renderer.draw(left, (0, 0))
    renderer.draw(right, (4, 0))

    def should_not_execute_individually(self, screen):
        raise AssertionError("consecutive plain blits should be submitted as one batch")

    monkeypatch.setattr(BlitCommand, "execute", should_not_execute_individually)
    renderer.update()

    assert renderer.screen.get_at((1, 1))[:3] == (255, 0, 0)
    assert renderer.screen.get_at((5, 1))[:3] == (0, 255, 0)
    assert not renderer._render_queue
