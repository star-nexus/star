from collections import defaultdict
import pygame
import pytest
from framework.engine.renders import RenderEngine, DrawCommand


def renderer():
    r = object.__new__(RenderEngine)
    r._screen = pygame.Surface((12, 8))
    r.current_layer = 0
    r._current_clip = None
    r._render_queue = defaultdict(list)
    return r


def test_nested_clip_is_snapshotted_and_blits_do_not_cross_clip_boundaries():
    r = renderer()
    red = pygame.Surface((12, 8)); red.fill('red')
    green = pygame.Surface((12, 8)); green.fill('green')
    clip = pygame.Rect(1, 1, 8, 6)
    with r.clip(clip):
        r.draw(red, (0, 0)); r.draw(red, (0, 0))
        with r.clip((4, 0, 7, 8)):
            r.draw(green, (0, 0)); r.draw(green, (0, 0))
    clip.update(0, 0, 1, 1)
    r.update()
    assert r.screen.get_at((2, 2))[:3] == (255, 0, 0)
    assert r.screen.get_at((5, 2))[:3] == (0, 255, 0)
    assert r.screen.get_at((10, 2))[:3] == (0, 0, 0)
    assert r.screen.get_clip() == pygame.Rect(0, 0, 12, 8)


def test_exception_restores_surface_and_enqueue_clip():
    r = renderer(); r.screen.set_clip((1, 1, 10, 6))
    def fail(screen):
        assert screen.get_clip() == pygame.Rect(2, 2, 3, 3)
        raise ValueError('paint failed')
    with pytest.raises(RuntimeError):
        with r.clip((2, 2, 3, 3)):
            r._add_command(DrawCommand(fail))
            raise RuntimeError('producer failed')
    assert r._current_clip is None
    with pytest.raises(ValueError, match='paint failed'):
        r.update()
    assert r.screen.get_clip() == pygame.Rect(1, 1, 10, 6)
