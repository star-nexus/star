from types import SimpleNamespace

import pygame
import pytest

from framework.engine.game_engine import GameEngine


@pytest.mark.parametrize('desktop, expected', [
    ((2560, 1440), (1200, 900)),
    ((3840, 2160), (1200, 900)),
    ((1440, 900), (1200, 800)),
    ((1280, 1024), (1200, 900)),
    ((0, 0), (1200, 800)),
])
def test_auto_window_stays_compact_on_large_desktops(monkeypatch, desktop, expected):
    engine = object.__new__(GameEngine)
    monkeypatch.setattr(pygame.display, 'Info', lambda: SimpleNamespace(
        current_w=desktop[0], current_h=desktop[1]))
    assert engine._choose_window_size(None, None) == expected


def test_explicit_dimensions_remain_available(monkeypatch):
    engine = object.__new__(GameEngine)
    monkeypatch.setattr(pygame.display, 'Info', lambda: SimpleNamespace(
        current_w=2560, current_h=1440))
    assert engine._choose_window_size(1920, 1080) == (1920, 1080)
    assert engine._choose_window_size(1440, None) == (1440, 900)
    assert engine._choose_window_size(None, 1080) == (1200, 1080)
