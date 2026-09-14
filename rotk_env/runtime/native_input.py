"""Existing local input/panels with gameplay writes redirected to Rust commands.

Mount on a prepared presentation World after removing its simulation systems.
Keep the historical class names used by renderer/panel discovery. In particular,
do not re-create UI entities after importing the native external-ID stream.
"""

from rotk_env.components import Camera, HexPosition, InputState, MapData, UIState, UIButtonCollection
from rotk_env.components.unit_action_buttons import UnitActionPanel, ActionConfirmDialog
from rotk_env.prefabs.config import GameConfig
from rotk_env.systems.input_system import InputHandlingSystem as _CoordinateInput
from rotk_env.systems.window_input_system import InputHandlingSystem as _WindowInput
from rotk_env.systems.unit_action_button_system import UnitActionButtonSystem as _ActionButtons
from rotk_env.systems.ui_button_system import UIButtonSystem as _Toolbar


class _NativeInput:
    def __init__(self, controls):
        super().__init__()
        self.controls = controls

    def initialize(self, world):
        if world is not self.controls.presentation.world:
            raise ValueError("Input must use the native presentation World")
        if any(world.get_singleton_component(cls) is None for cls in (Camera, InputState, UIState)):
            raise ValueError("Prepare camera and UI before native handoff")
        self.world = world
        fit = self._zoom_to_fit_map(world.get_singleton_component(MapData))
        self.min_zoom = min(0.5, max(0.15, fit * 0.75))
        self._window_size = (GameConfig.WINDOW_WIDTH, GameConfig.WINDOW_HEIGHT)

    def _end_current_turn(self):
        self.controls.finish_turn()

    def _set_fog_enabled(self, ui_state, enabled):
        self.controls.execute("set_fog", enabled=enabled)
        if ui_state is not None and not enabled:
            ui_state.view_faction = None


class InputHandlingSystem(_NativeInput, _WindowInput):
    """Window picking/targeting remains Python; accepted commands execute in Rust."""

    def _try_move_unit(self, unit_entity, target_pos):
        return self.controls.execute("move", unit_id=unit_entity, position=target_pos)

    def _try_attack_target(self, attacker_entity, target_entity):
        return self.controls.execute("attack", unit_id=attacker_entity, target_id=target_entity)


class CoordinateInputHandlingSystem(_NativeInput, _CoordinateInput):
    """Retain the dummy input path, including its methods' None return values."""

    def _try_move_unit(self, unit_entity, target_pos):
        self.controls.execute("move", unit_id=unit_entity, position=target_pos)

    def _try_attack_target(self, attacker_entity, target_entity):
        self.controls.execute("attack", unit_id=attacker_entity, target_id=target_entity)


class UnitActionButtonSystem(_ActionButtons):
    def __init__(self, controls):
        super().__init__()
        self.controls = controls

    def initialize(self, world):
        if world is not self.controls.presentation.world:
            raise ValueError("Action panel must use the native presentation World")
        if any(world.get_singleton_component(cls) is None for cls in (UnitActionPanel, ActionConfirmDialog)):
            raise ValueError("Prepare action panel before native handoff")
        self.world = world

    def _execute_wait_action(self, unit_entity):
        self.controls.execute("wait", unit_id=unit_entity)

    def _execute_garrison_action(self, unit_entity):
        self.controls.execute("garrison", unit_id=unit_entity)

    def _execute_capture_action(self, unit_entity):
        position = self.world.get_component(unit_entity, HexPosition)
        if position is not None:
            self.controls.start_capture(unit_entity, (position.col, position.row))

    def _execute_fortify_action(self, unit_entity):
        position = self.world.get_component(unit_entity, HexPosition)
        if position is not None:
            self.controls.execute("fortify", unit_id=unit_entity, position=(position.col, position.row))


class UIButtonSystem(_Toolbar):
    def __init__(self, controls):
        super().__init__()
        self.controls = controls

    def initialize(self, world):
        if world is not self.controls.presentation.world:
            raise ValueError("Toolbar must use the native presentation World")
        if world.get_singleton_component(UIButtonCollection) is None:
            raise ValueError("Prepare toolbar entities before native handoff")
        self.world = world

    def _end_turn(self):
        self.controls.execute("toolbar_end_turn")
