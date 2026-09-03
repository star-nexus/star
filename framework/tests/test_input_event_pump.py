import logging

import pygame

from framework.engine.events import EventBus
from framework.engine.inputs import InputSystem


def _bare_input_system() -> InputSystem:
    system = object.__new__(InputSystem)
    system.event_manager = EventBus()
    system.logger = logging.getLogger(__name__)
    system._last_window_size = None
    return system


def test_input_update_pumps_once_then_drains_without_second_pump(monkeypatch):
    system = _bare_input_system()
    calls = []

    monkeypatch.setattr(pygame.event, "pump", lambda: calls.append("pump"))

    def fake_get(*, pump=True):
        calls.append(("get", pump))
        return []

    monkeypatch.setattr(pygame.event, "get", fake_get)

    system.update()

    assert calls == ["pump", ("get", False)]
