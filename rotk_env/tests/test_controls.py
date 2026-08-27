"""Shared keymap: F1 help, CLI epilog, and Game Over hit-test stay in sync."""

import pygame

from rotk_env.components.game_over import GameOverButton
from rotk_env.prefabs.controls import (
    KEY_BINDINGS,
    binding_for_key,
    format_cli_controls,
    help_panel_lines,
)
from rotk_env.systems.input_system import InputHandlingSystem


def test_help_panel_matches_live_keymap():
    text = "\n".join(help_panel_lines())
    assert "F1 - Toggle help" in text
    assert "H - Toggle hex orientation" in text
    assert "H - Toggle Help" not in text
    assert "Middle Mouse" not in text
    assert "Left click" in text
    assert "Right click" in text


def test_cli_controls_match_live_keymap():
    text = format_cli_controls()
    assert "F1: Toggle help" in text
    assert "Middle Mouse" not in text
    assert "WASD / arrows" in text


def test_every_key_binding_has_an_input_action():
    for binding in KEY_BINDINGS:
        assert hasattr(InputHandlingSystem, f"_action_{binding.action}")
    assert binding_for_key(pygame.K_F1).action == "toggle_help"
    assert binding_for_key(pygame.K_h).action == "toggle_hex_orientation"
    assert binding_for_key(pygame.K_s) is None


def test_game_over_button_contains_without_pygame_rect():
    btn = GameOverButton(action="quit", label="Quit", x=10, y=20, w=100, h=40)
    assert btn.contains((10, 20))
    assert btn.contains((109, 59))
    assert not btn.contains((9, 20))
    assert not btn.contains((110, 20))
    assert not btn.contains((10, 60))
