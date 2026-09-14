"""Input event and panel integration over native-derived facts, without a window."""

import pygame
import pytest
from types import SimpleNamespace

pytest.importorskip("star_native")
from rotk_env import components as c
from rotk_env.prefabs.config import Faction, GameMode, PlayerType
from rotk_env.runtime.bootstrap import export_initial_state, encode
from rotk_env.runtime.local_controls import LocalControls
from rotk_env.runtime.native import RustRuntime
from rotk_env.runtime import native_input as ni
from rotk_env.runtime.world_presentation import WorldPresentation, _UNIT_COLUMNS
from rotk_env.systems.input_system import InputHandlingSystem as CoordinateInput
from rotk_env.systems.window_input_system import InputHandlingSystem as WindowInput
from rotk_env.systems.unit_action_button_system import UnitActionButtonSystem as ActionButtons
from rotk_env.systems.ui_button_system import UIButtonSystem as Toolbar
from rotk_env.tests.test_native_combat_presentation import make
from rotk_env.tests.test_native_lifecycle import snapshot
from rotk_env.tests.test_native_request_batch import frozen
from rotk_env.tests.test_native_world_presentation import detached_world


@pytest.fixture
def fonts(monkeypatch):
    # Input contracts do not assert glyphs or pixels; Cocoa probes use real fonts.
    original = pygame.font.Font
    monkeypatch.setattr(pygame.font, "Font", lambda path, size: original(None, size))


def assert_display(source, display):
    for uid in source.query().with_component(c.Unit).ordered_entities():
        for cls in _UNIT_COLUMNS.values():
            assert encode(display.get_component(uid, cls)) == encode(source.get_component(uid, cls))
    for cls in (c.GameState, c.TurnManager, c.FogOfWar):
        assert encode(display.get_singleton_component(cls)) == encode(source.get_singleton_component(cls))


@pytest.mark.parametrize("display_mode", ["dummy", "window"])
@pytest.mark.parametrize("mode", [GameMode.REAL_TIME, GameMode.TURN_BASED])
@pytest.mark.parametrize("threads", [1, 2, 4])
def test_input_clicks_panels_turn_and_fog_read_native_writes_immediately(display_mode, mode, threads, frozen, fonts):
    source, (a, b, enemy), llm = make(display_mode, mode, "ranged", critical=True)
    llm.enabled = False
    # Enemy is AI-controlled, so clicks dispatch attack instead of selecting it.
    for pid in source.query().with_component(c.Player).entities():
        player = source.get_component(pid, c.Player)
        if player.faction == Faction.SHU: player.player_type = PlayerType.AI
    source.add_singleton_component(c.TurnManager(list(source.query().with_component(c.Player).ordered_entities())))
    old_input = WindowInput() if display_mode == "window" else CoordinateInput()
    source.add_system(old_input)
    old_buttons = ActionButtons(); source.add_system(old_buttons)
    old_toolbar = Toolbar(); source.add_system(old_toolbar)
    initial = export_initial_state(source, display=display_mode)
    display = detached_world(source)
    presentation = WorldPresentation(display)
    try:
        with RustRuntime(initial, threads=threads) as native:
            controls = LocalControls(native, presentation, initial)
            controls.refresh()
            input_type = ni.InputHandlingSystem if display_mode == "window" else ni.CoordinateInputHandlingSystem
            inputs = input_type(controls)
            buttons = ni.UnitActionButtonSystem(controls)
            toolbar = ni.UIButtonSystem(controls)
            count = display.entity_counter
            ui = display.get_singleton_component(c.UIState)
            camera = display.get_singleton_component(c.Camera)
            camera.zoom = .7
            for system in (inputs, buttons, toolbar): display.add_system(system)
            assert display.entity_counter == count
            assert display.get_singleton_component(c.Camera) is camera and camera.zoom == .7
            assert display.get_singleton_component(c.UIState) is ui
            old_ui = source.get_singleton_component(c.UIState)

            def compare():
                snapshot(source, native, display_mode)
                assert_display(source, display)
                assert encode(ui) == encode(old_ui)

            # UI-only camera/selection changes must not mutate authority.
            before = native.export_state()
            old_input._handle_tile_click((-1, 0), old_ui)
            inputs._handle_tile_click((-1, 0), ui)
            assert ui.selected_unit == a
            assert native.export_state() == before
            compare()

            # Exercise current key dispatch and mouse screen picking, using the
            # same camera in both worlds. Keep historical keymap unchanged.
            source.get_singleton_component(c.Camera).zoom = camera.zoom
            for key in (pygame.K_v, pygame.K_TAB, pygame.K_F1, pygame.K_1, pygame.K_3, pygame.K_2, pygame.K_ESCAPE):
                event = SimpleNamespace(key=key)
                old_input._handle_key_down(event); inputs._handle_key_down(event)
                compare()
            point = inputs.hex_converter.hex_to_pixel(-1, 0)
            event = SimpleNamespace(button=1, pos=(point[0] * camera.zoom + camera.offset_x, point[1] * camera.zoom + camera.offset_y))
            old_input._handle_mouse_click(event); inputs._handle_mouse_click(event)
            assert ui.selected_unit == a
            compare()

            if display_mode == "window":
                assert buttons._get_input_handling_system() is inputs
                assert inputs.begin_targeting("move", a) == old_input.begin_targeting("move", a)
            for cell in ((-2, 0), (-2, 1), (1, 1)):
                old_input._handle_tile_click(cell, old_ui)
                inputs._handle_tile_click(cell, ui)
                compare()
            for kind in ("wait", "garrison", "capture", "fortify"):
                getattr(old_buttons, f"_execute_{kind}_action")(a)
                getattr(buttons, f"_execute_{kind}_action")(a)
                compare()
            for method in ("_action_toggle_fog", "_action_view_shu", "_action_view_wei", "_action_toggle_fog"):
                getattr(old_input, method)()
                getattr(inputs, method)()
                compare()
            for _ in range(2):
                old_toolbar._end_turn(); toolbar._end_turn(); compare()
            old_input._end_current_turn(); inputs._end_current_turn(); compare()
            # Drive only original gameplay systems on the oracle. Render/input
            # updates are not simulation and need a live SDL window elsewhere.
            for dt in (.1, .25, 1., 2.):
                for system in source.systems:
                    if system not in (old_input, old_buttons, old_toolbar) and system.enabled:
                        system.update(dt)
                native.step(dt)
                controls.refresh()
                compare()
    finally:
        source.reset()
        display.reset()


def test_controls_missing_systems_are_noops_and_stale_scene_fails(frozen):
    source, (a, b, enemy), _ = make("none", GameMode.REAL_TIME, "melee")
    initial = export_initial_state(source)
    display = detached_world(source)
    try:
        with RustRuntime(initial) as native:
            controls = LocalControls(native, WorldPresentation(display), {"systems": {}, "interface": {}})
            controls.refresh()
            before = native.export_state()
            assert controls.execute("move", unit_id=a, position=(-2, 0)) is None
            assert controls.execute("attack", unit_id=a, target_id=enemy) is None
            assert controls.execute("fortify", unit_id=a, position=(-1, 0)) is None
            assert controls.start_capture(a, (-1, 0)) is None
            assert controls.finish_turn() is None
            assert native.export_state() == before
            native.reset(initial)
            with pytest.raises(RuntimeError, match="epoch"): controls.refresh()
    finally:
        source.reset()
        display.reset()


@pytest.mark.parametrize("command", ["move", "keyboard", "capture", "refresh"])
def test_stale_controls_neither_write_nor_drain_new_scene(command, frozen):
    source, (a, b, enemy), _ = make("dummy", GameMode.TURN_BASED, "melee")
    initial = export_initial_state(source, display="dummy")
    display = detached_world(source)
    try:
        with RustRuntime(initial) as native:
            controls = LocalControls(native, WorldPresentation(display), initial)
            controls.refresh()
            native.reset(initial)
            before = native.export_state()
            with pytest.raises(RuntimeError, match="epoch"):
                if command == "move": controls.execute("move", unit_id=b, position=(-1, 1))
                elif command == "keyboard": controls.finish_turn()
                elif command == "capture": controls.start_capture(a, (-1, 0))
                else: controls.refresh()
            assert native.export_state() == before
            first = native.take_presentation_delta()
            assert first["fog"]["full"] and len(first["units"]) == 3
    finally:
        source.reset()
        display.reset()
