from types import SimpleNamespace

from rotk_env.components.unit_action_buttons import ActionType, UnitActionPanel
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
        self.input_system = InputHandlingSystem()
        self.systems = [self.input_system]

    def get_singleton_component(self, component_type):
        if component_type is UnitActionPanel:
            return self.panel
        return None


def _system(world):
    system = UnitActionButtonSystem.__new__(UnitActionButtonSystem)
    system.world = world
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
