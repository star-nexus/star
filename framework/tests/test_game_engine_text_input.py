import pygame

from framework.engine.game_engine import GameEngine


def _bare_engine() -> GameEngine:
    # Bypass the singleton constructor so these tests exercise only the text
    # input policy without creating a real SDL window or manager graph.
    return object.__new__(GameEngine)


def test_text_input_policy_calls_matching_pygame_api(monkeypatch):
    engine = _bare_engine()
    calls = []

    monkeypatch.setattr(pygame.key, "start_text_input", lambda: calls.append("start"))
    monkeypatch.setattr(pygame.key, "stop_text_input", lambda: calls.append("stop"))

    engine.set_text_input_enabled(False)
    assert calls == ["stop"]
    assert engine.text_input_enabled is False

    engine.set_text_input_enabled(True)
    assert calls == ["stop", "start"]
    assert engine.text_input_enabled is True


def test_pygame_initialization_disables_text_input_by_default(monkeypatch):
    engine = _bare_engine()
    engine.headless = True
    engine.width = 1200
    engine.height = 800
    engine.title = "test"

    calls = []
    fake_screen = object()
    fake_clock = object()

    monkeypatch.setattr(pygame, "init", lambda: None)
    monkeypatch.setattr(pygame.display, "set_mode", lambda *args, **kwargs: fake_screen)
    monkeypatch.setattr(pygame.time, "Clock", lambda: fake_clock)
    monkeypatch.setattr(
        GameEngine,
        "set_text_input_enabled",
        lambda self, enabled: calls.append(bool(enabled)),
    )

    engine._init_pygame()

    assert calls == [False]
    assert engine.screen is fake_screen
    assert engine.clock is fake_clock
