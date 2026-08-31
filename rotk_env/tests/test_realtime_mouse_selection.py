from types import SimpleNamespace

from rotk_env.components import GameState, Player, Unit
from rotk_env.prefabs.config import Faction, GameMode, PlayerType
from rotk_env.systems.input_system import InputHandlingSystem


class _Query:
    def __init__(self, entities):
        self._entities = entities

    def with_component(self, component_type):
        return self

    def entities(self):
        return list(self._entities)


class _World:
    def __init__(
        self,
        *,
        mode=GameMode.REAL_TIME,
        current_player=Faction.WEI,
        human_factions=(Faction.WEI,),
    ):
        self.game_state = SimpleNamespace(
            game_mode=mode,
            current_player=current_player,
        )
        self.units = {
            1: SimpleNamespace(faction=Faction.SHU),
            2: SimpleNamespace(faction=Faction.WEI),
            3: SimpleNamespace(faction=Faction.WEI),
            4: SimpleNamespace(faction=Faction.WU),
        }
        self.players = {}
        for index, faction in enumerate((Faction.WEI, Faction.SHU, Faction.WU), start=101):
            self.players[index] = SimpleNamespace(
                faction=faction,
                player_type=(
                    PlayerType.HUMAN if faction in human_factions else PlayerType.AI
                ),
            )

    def query(self):
        return _Query(self.players)

    def get_singleton_component(self, component_type):
        if component_type is GameState:
            return self.game_state
        return None

    def get_component(self, entity, component_type):
        if component_type is Unit:
            return self.units.get(entity)
        if component_type is Player:
            return self.players.get(entity)
        return None


def _system(world):
    system = InputHandlingSystem.__new__(InputHandlingSystem)
    system.world = world
    return system


def test_realtime_human_vs_two_ai_only_allows_wei_manual_selection():
    system = _system(_World(human_factions=(Faction.WEI,)))

    assert system._should_select_unit(2) is True
    assert system._should_select_unit(1) is False
    assert system._should_select_unit(4) is False


def test_realtime_three_kingdoms_agent_preset_has_no_manual_unit_selection():
    system = _system(_World(human_factions=()))

    assert system._should_select_unit(1) is False
    assert system._should_select_unit(2) is False
    assert system._should_select_unit(4) is False


def test_turn_based_requires_human_slot_and_current_turn():
    system = _system(
        _World(
            mode=GameMode.TURN_BASED,
            current_player=Faction.WEI,
            human_factions=(Faction.WEI,),
        )
    )
    assert system._should_select_unit(2) is True
    assert system._should_select_unit(1) is False

    system.world.game_state.current_player = Faction.SHU
    assert system._should_select_unit(2) is False
    assert system._should_select_unit(1) is False


def test_realtime_tile_click_selects_human_and_attacks_ai(monkeypatch):
    world = _World(human_factions=(Faction.WEI,))
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

    # Human Wei can be focused.
    system._handle_tile_click((2, 3), ui_state)
    assert ui_state.selected_unit == 2
    assert attacks == []

    # Another Human Wei changes focus rather than attacking.
    clicked["entity"] = 3
    system._handle_tile_click((2, 4), ui_state)
    assert ui_state.selected_unit == 3
    assert attacks == []

    # AI Shu remains an attack target, not a manually selectable unit.
    clicked["entity"] = 1
    system._handle_tile_click((2, 5), ui_state)
    assert ui_state.selected_unit == 3
    assert attacks == [(3, 1)]


def test_realtime_ai_unit_click_with_no_human_selection_is_ignored(monkeypatch):
    system = _system(_World(human_factions=(Faction.WEI,)))
    ui_state = SimpleNamespace(selected_unit=None)
    system._get_unit_at_position = lambda hex_pos: 1
    monkeypatch.setattr(
        "rotk_env.systems.input_system.EBS.publish",
        lambda event: None,
    )

    system._handle_tile_click((1, 1), ui_state)
    assert ui_state.selected_unit is None
