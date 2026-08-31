from types import SimpleNamespace

from rotk_env.components import GameState, UIState, Unit
from rotk_env.prefabs.config import Faction, GameMode
from rotk_env.systems.input_system import InputHandlingSystem


class _World:
    def __init__(self, mode=GameMode.REAL_TIME, current_player=Faction.SHU):
        self.game_state = SimpleNamespace(
            game_mode=mode,
            current_player=current_player,
        )
        self.units = {
            1: SimpleNamespace(faction=Faction.SHU),
            2: SimpleNamespace(faction=Faction.WEI),
            3: SimpleNamespace(faction=Faction.WEI),
        }

    def get_singleton_component(self, component_type):
        if component_type is GameState:
            return self.game_state
        return None

    def get_component(self, entity, component_type):
        if component_type is Unit:
            return self.units.get(entity)
        return None


def _system(world):
    system = InputHandlingSystem.__new__(InputHandlingSystem)
    system.world = world
    return system


def test_realtime_without_selection_can_focus_any_faction():
    system = _system(_World())
    ui_state = SimpleNamespace(selected_unit=None)

    # The legacy current-player check would reject Wei forever because the
    # first configured faction/current_player is Shu. Real-time interaction
    # must be able to focus any faction when nothing is selected.
    assert system._should_select_unit(2, ui_state) is True


def test_realtime_same_faction_reselects_cross_faction_remains_attack_target():
    system = _system(_World())

    ui_state = SimpleNamespace(selected_unit=2)
    assert system._should_select_unit(3, ui_state) is True

    ui_state.selected_unit = 1
    assert system._should_select_unit(2, ui_state) is False


def test_turn_based_keeps_current_player_restriction():
    system = _system(_World(mode=GameMode.TURN_BASED, current_player=Faction.SHU))
    ui_state = SimpleNamespace(selected_unit=None)

    assert system._should_select_unit(1, ui_state) is True
    assert system._should_select_unit(2, ui_state) is False


def test_realtime_tile_click_selects_any_faction_then_attacks_cross_faction(monkeypatch):
    world = _World()
    system = _system(world)
    ui_state = SimpleNamespace(selected_unit=None)

    clicked = {"entity": 2}
    system._get_unit_at_position = lambda hex_pos: clicked["entity"]

    selected_events = []
    monkeypatch.setattr(
        "rotk_env.systems.input_system.EBS.publish",
        lambda event: selected_events.append(event),
    )

    attacks = []
    system._try_attack_target = lambda attacker, target: attacks.append((attacker, target))
    system._try_move_unit = lambda unit, pos: None

    # No selected unit: Wei is selectable even though GameState.current_player is Shu.
    system._handle_tile_click((2, 3), ui_state)
    assert ui_state.selected_unit == 2
    assert attacks == []

    # Same-faction click changes focus rather than attacking.
    clicked["entity"] = 3
    system._handle_tile_click((2, 4), ui_state)
    assert ui_state.selected_unit == 3
    assert attacks == []

    # Cross-faction click preserves the old click-to-attack behavior.
    clicked["entity"] = 1
    system._handle_tile_click((2, 5), ui_state)
    assert ui_state.selected_unit == 3
    assert attacks == [(3, 1)]
