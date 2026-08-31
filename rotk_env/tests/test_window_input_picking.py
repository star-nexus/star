from types import SimpleNamespace

from rotk_env.components import (
    Camera,
    FogOfWar,
    GameState,
    HexPosition,
    MapData,
    Player,
    UIState,
    Unit,
    UnitCount,
)
from rotk_env.components.unit_action_buttons import UnitActionPanel
from rotk_env.prefabs.config import Faction, GameMode, PlayerType, UnitType
from rotk_env.systems.scale_input_system import InputHandlingSystem
from rotk_env.utils.hex_utils import HexConverter


class _Query:
    def __init__(self, entities):
        self._entities = list(entities)

    def with_all(self, *component_types):
        return self

    def with_component(self, component_type):
        return self

    def entities(self):
        return list(self._entities)


class _World:
    def __init__(self):
        self.camera = Camera(offset_x=800.0, offset_y=600.0, zoom=1.0)
        self.fog = FogOfWar(enabled=True)
        self.game_state = SimpleNamespace(
            game_mode=GameMode.REAL_TIME,
            current_player=Faction.WEI,
        )
        self.ui_state = UIState()
        self.map_data = MapData(width=51, height=51, tiles={})
        self.action_panel = UnitActionPanel()
        self.players = {
            101: SimpleNamespace(faction=Faction.WEI, player_type=PlayerType.HUMAN),
            102: SimpleNamespace(faction=Faction.SHU, player_type=PlayerType.AI),
            103: SimpleNamespace(faction=Faction.WU, player_type=PlayerType.AI),
        }
        # Two tokens on the same committed hex exercise the old query-order
        # failure: the AI entity appears first, but the HUMAN token must remain
        # recoverable by the interactive picker.
        self.units = {
            1: SimpleNamespace(faction=Faction.SHU, unit_type=UnitType.INFANTRY),
            2: SimpleNamespace(faction=Faction.WEI, unit_type=UnitType.INFANTRY),
        }
        self.positions = {
            1: HexPosition(3, 4),
            2: HexPosition(3, 4),
        }
        self.counts = {
            1: SimpleNamespace(current_count=100),
            2: SimpleNamespace(current_count=100),
        }
        self.systems = []

    def query(self):
        return _Query(list(self.units) + list(self.players))

    def get_singleton_component(self, component_type):
        if component_type is Camera:
            return self.camera
        if component_type is FogOfWar:
            return self.fog
        if component_type is GameState:
            return self.game_state
        if component_type is UIState:
            return self.ui_state
        if component_type is MapData:
            return self.map_data
        if component_type is UnitActionPanel:
            return self.action_panel
        return None

    def get_component(self, entity, component_type):
        if component_type is Unit:
            return self.units.get(entity)
        if component_type is HexPosition:
            return self.positions.get(entity)
        if component_type is UnitCount:
            return self.counts.get(entity)
        if component_type is Player:
            return self.players.get(entity)
        return None


def _system(world):
    system = InputHandlingSystem.__new__(InputHandlingSystem)
    system.world = world
    system.hex_converter = HexConverter()
    system._targeting_action = None
    system._targeting_unit = None
    return system


def _screen_center(system, world, hex_pos):
    world_x, world_y = system.hex_converter.hex_to_pixel(*hex_pos)
    return (
        int(round(world_x * world.camera.zoom + world.camera.offset_x)),
        int(round(world_y * world.camera.zoom + world.camera.offset_y)),
    )


def test_fog_then_zoom_keeps_human_unit_pickable():
    world = _World()
    system = _system(world)

    # Reproduce the reported ordering: key 1 disables fog, then + zooms in.
    world.fog.enabled = False
    world.camera.zoom = 2.25
    screen_pos = _screen_center(system, world, (3, 4))

    assert system._screen_to_hex(screen_pos) == (3, 4)
    assert system._get_visible_unit_at_screen_position(screen_pos) == 2
    assert system._get_unit_at_position((3, 4)) == 2


def test_zoom_then_fog_keeps_human_unit_pickable():
    world = _World()
    system = _system(world)

    world.camera.zoom = 2.4
    world.fog.enabled = False
    screen_pos = _screen_center(system, world, (3, 4))

    assert system._get_visible_unit_at_screen_position(screen_pos) == 2


def test_move_target_mode_executes_empty_tile_and_refreshes_panel(monkeypatch):
    world = _World()
    system = _system(world)
    world.ui_state.selected_unit = 2
    world.action_panel.selected_unit = 2
    world.action_panel.visible = False

    system._should_select_unit = lambda entity: entity == 2
    system._get_unit_at_position = lambda pos: None
    moves = []
    system._try_move_unit = lambda entity, pos: (
        moves.append((entity, pos)) or {"success": True}
    )
    monkeypatch.setattr(
        "rotk_env.systems.scale_input_system.EBS.publish", lambda event: None
    )

    assert system.begin_targeting("move", 2) is True
    system._handle_tile_click((5, 6), world.ui_state, clicked_unit=None)

    assert moves == [(2, (5, 6))]
    assert system._targeting_action is None
    assert system._targeting_unit is None
    assert world.action_panel.selected_unit is None


def test_hex_to_screen_includes_zoom():
    world = _World()
    system = _system(world)
    world.camera.zoom = 2.0

    world_x, world_y = system.hex_converter.hex_to_pixel(2, -1)
    expected = (
        world_x * 2.0 + world.camera.offset_x,
        world_y * 2.0 + world.camera.offset_y,
    )
    assert system._hex_to_screen((2, -1)) == expected
