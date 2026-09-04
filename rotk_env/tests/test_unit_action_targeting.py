from types import SimpleNamespace

from rotk_env.components import UIState
from rotk_env.components.unit_action_buttons import (
    ActionConfirmDialog,
    ActionType,
    UnitActionPanel,
)
from rotk_env.prefabs.config import GameConfig
from rotk_env.systems.unit_action_button_system import UnitActionButtonSystem


class InputHandlingSystem:
    def __init__(self):
        self.calls = []

    def begin_targeting(self, action, unit_entity):
        self.calls.append((action, unit_entity))
        return True


class _World:
    def __init__(self):
        self.panel = UnitActionPanel(selected_unit=77, visible=True)
        self.ui_state = SimpleNamespace(selected_unit=77)
        self.input_system = InputHandlingSystem()
        self.systems = [self.input_system]

    def get_singleton_component(self, component_type):
        if component_type is UnitActionPanel:
            return self.panel
        if component_type is UIState:
            return self.ui_state
        if component_type is ActionConfirmDialog:
            return None
        return None


def _system(world):
    system = UnitActionButtonSystem.__new__(UnitActionButtonSystem)
    system.world = world
    system._frame_text_cache_misses = 0
    system._text_surface_cache = {}
    return system


def test_move_button_enters_target_mode_and_hides_panel():
    world = _World()
    system = _system(world)
    system._execute_action(ActionType.MOVE, 77)
    assert world.input_system.calls == [("move", 77)]
    assert world.panel.visible is False
    assert world.panel.selected_unit == 77


def test_attack_button_enters_target_mode_and_hides_panel():
    world = _World()
    system = _system(world)
    system._execute_action(ActionType.ATTACK, 77)
    assert world.input_system.calls == [("attack", 77)]
    assert world.panel.visible is False
    assert world.panel.selected_unit == 77


def test_action_panel_tracks_live_right_edge(monkeypatch):
    world = _World()
    world.panel.visible = False
    system = _system(world)
    monkeypatch.setattr(GameConfig, "WINDOW_WIDTH", 2480)
    system.update(0.0)
    assert world.panel.x == 2480 - world.panel.width - 20
    assert world.panel.x > 2000
