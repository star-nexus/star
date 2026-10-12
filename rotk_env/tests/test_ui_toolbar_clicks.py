"""Toolbar interaction through the SDL queue used by the actual window."""
import os

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')

import pygame
import pytest

from framework.engine import RMS
from framework.engine.events import EBS
from framework.engine.inputs import IPS
from rotk_env import components as c
from rotk_env.prefabs.config import Faction, GameConfig, PlayerType
from rotk_env.prefabs.world_builder import build_skirmish_world
from rotk_env.utils.env_events import TurnStartEvent
from rotk_env.rendering.pygame.display import sync_game_config_from_display


@pytest.fixture(params=['python', 'rust-serial', 'rust-threaded'])
def toolbar(request, monkeypatch):
    pygame.display.init()
    pygame.font.init()
    pygame.display.set_mode((1200, 900))
    sync_game_config_from_display()
    RMS.screen = pygame.display.get_surface()
    prior = {kind: tuple(callbacks) for kind, callbacks in EBS._listeners.items() if callbacks}
    options = dict(display='window', scenario='river_split', mode='turn_based',
                   seed=42, hub_url=None,
                   players={Faction.WEI: PlayerType.HUMAN, Faction.SHU: PlayerType.AI})
    session = None
    if request.param.startswith('rust'):
        pytest.importorskip('star_rust_runtime')
        from rotk_env.runtime.session import NativeSession
        session = NativeSession(authority_scheduling=request.param == 'rust-threaded', **options)
        world = session.world
    else:
        world = build_skirmish_world(**options)
    system = next(s for s in world.systems if type(s).__name__ == 'UIButtonSystem')
    # A click must use event.pos, even before the polled pointer catches up.
    monkeypatch.setattr(pygame.mouse, 'get_pos', lambda: (0, 0))
    pygame.event.clear()
    try:
        yield world, system, session
    finally:
        if session:
            session.close()
        else:
            world._ui_context.close()
            world.reset()
        RMS.clear()
        assert {kind: tuple(callbacks) for kind, callbacks in EBS._listeners.items() if callbacks} == prior


def click(pos, button=1):
    pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=button, pos=pos))
    IPS.update()


def release(pos):
    pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=pos))
    IPS.update()


def move(pos, held=False):
    pygame.event.post(pygame.event.Event(pygame.MOUSEMOTION, pos=pos,
                                       rel=(0, 0), buttons=(int(held), 0, 0)))
    IPS.update()


def turn(world):
    state = world.get_singleton_component(c.GameState)
    return state.current_player, state.turn_number


def button(world, name):
    entity = world.get_singleton_component(c.UIButtonCollection).get_button(name)
    return world.get_component(entity, c.UIButton)


@pytest.mark.parametrize('entry', ['space', 'button'])
def test_keyboard_and_toolbar_restore_resources_and_publish_turn_start(toolbar, entry, monkeypatch):
    world, system, session = toolbar
    unit = next(uid for uid in world.query().with_all(c.Unit, c.ActionPoints).ordered_entities()
                if world.get_component(uid, c.Unit).faction == Faction.WEI)
    actions = next(s for s in world.systems if type(s).__name__ == 'UnitActionButtonSystem')
    seen = []

    def record(event):
        seen.append(event.faction)

    if session:
        # Native events reach the scene through ordered projection callbacks;
        # they must not re-enter Python simulation listeners.
        monkeypatch.setattr(session.controls, 'on_events', lambda events: seen.extend(
            Faction(event['fields']['faction']) for event in events
            if event['type'] == 'TurnStartEvent'))
    else:
        EBS.subscribe(TurnStartEvent, record)
    try:
        for expected_turn in ((Faction.SHU, 1), (Faction.WEI, 2)):
            # Spend real AP through the local action path, including Rust's
            # authority owner and ordered projection, not a display-only edit.
            ap = world.get_component(unit, c.ActionPoints)
            assert ap.max_ap > 0
            for _ in range(ap.current_ap):
                actions._execute_wait_action(unit)
            assert world.get_component(unit, c.ActionPoints).current_ap == 0
            if entry == 'space':
                pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE, mod=0))
                pygame.event.post(pygame.event.Event(pygame.KEYUP, key=pygame.K_SPACE))
                IPS.update()
            else:
                click(world._ui_context.layout.footer.center)
                release(world._ui_context.layout.footer.center)
            assert turn(world) == expected_turn
            ap = world.get_component(unit, c.ActionPoints)
            assert ap.current_ap == ap.max_ap
            for uid in world.query().with_component(c.MovementPoints).ordered_entities():
                movement = world.get_component(uid, c.MovementPoints)
                count = world.get_component(uid, c.UnitCount)
                expected_mp = movement.get_effective_movement(count) if count else movement.max_mp
                assert movement.current_mp == expected_mp and not movement.has_moved
        assert seen == [Faction.SHU, Faction.WEI]
    finally:
        if not session:
            EBS.unsubscribe(TurnStartEvent, record)


def test_end_turn_click_advances_once_without_polled_mouse_state(toolbar):
    world, system, session = toolbar
    state = world.get_singleton_component(c.InputState)
    assert not state.mouse_pressed and state.mouse_pos == (0, 0)
    assert turn(world) == (Faction.WEI, 1)
    click(world._ui_context.layout.footer.center)
    assert turn(world) == (Faction.SHU, 1)
    # Neither held/stale polled state nor subsequent paint is another click.
    state.mouse_pressed.add(1)
    state.mouse_pos = world._ui_context.layout.footer.center
    for _ in range(3):
        if session:
            session.update_inputs(0)
            session.update_display(0, inputs=False)
        else:
            system.update(0)
        RMS.clear()
    assert turn(world) == (Faction.SHU, 1)
    click(world._ui_context.layout.footer.center)
    assert turn(world) == (Faction.WEI, 2)


def test_toolbar_respects_modal_disabled_hidden_and_other_clicks(toolbar):
    world, system, _ = toolbar
    end = button(world, 'end_turn')
    point = world._ui_context.layout.footer.center
    original = turn(world)
    click(point, button=3)
    click(world._ui_context.layout.sidebar.midleft)
    end.is_enabled = False
    click(point)
    end.is_enabled = True
    end.is_visible = False
    click(point)
    end.is_visible = True
    assert turn(world) == original
    ui = world.get_singleton_component(c.UIState)
    click(system._button_rect(button(world, 'help')).center)
    assert ui.show_help
    click(point)
    assert turn(world) == original
    click(system._button_rect(button(world, 'help')).center)
    assert not ui.show_help
    click(system._button_rect(button(world, 'stats')).center)
    assert ui.show_stats
    click(point)
    assert turn(world) == original
    click(system._button_rect(button(world, 'stats')).center)
    assert not ui.show_stats
    click(point)
    assert turn(world) == (Faction.SHU, 1)


def test_click_uses_current_footer_after_resize_before_next_frame(toolbar):
    world, system, _ = toolbar
    old = world._ui_context.layout.footer.center
    pygame.display.set_mode((1920, 1080))
    # Simulate resize + click in one SDL batch, before a gameplay render sync.
    from rotk_env.ui.context import UiContext
    fresh = UiContext()
    current = fresh.layout.footer.center
    fresh.close()
    assert old != current
    click(current)
    assert turn(world) == (Faction.SHU, 1)


def test_quick_click_has_visible_feedback_then_recovers_without_another_turn(toolbar, monkeypatch):
    world, system, session = toolbar
    now = [10.0]
    monkeypatch.setattr(system, '_feedback_clock', lambda: now[0])
    end = button(world, 'end_turn')
    point = world._ui_context.layout.footer.center
    move(point)
    assert end.is_hovered and not system._button_is_pressed(end)
    # A fast click's down/up pair can reach the input pump in the same frame.
    pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=point))
    pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=point))
    IPS.update()
    assert turn(world) == (Faction.SHU, 1)
    assert system._button_is_pressed(end)
    from rotk_env.runtime.bootstrap import export_initial_state
    authority = session.runtime.export_state if session else lambda: export_initial_state(world, display='window')
    snapshot = authority()
    now[0] += 0.06
    if session:
        session.update_display(0, inputs=False)
    else:
        system.update(0)
    RMS.clear()
    assert system._button_is_pressed(end)
    now[0] += 0.10
    system._update_button_states()
    assert end.is_hovered and not system._button_is_pressed(end)
    assert turn(world) == (Faction.SHU, 1)
    assert authority() == snapshot


def test_hold_release_drag_out_and_disabled_states_do_not_stick(toolbar, monkeypatch):
    world, system, _ = toolbar
    now = [10.0]
    monkeypatch.setattr(system, '_feedback_clock', lambda: now[0])
    end = button(world, 'end_turn')
    point = world._ui_context.layout.footer.center
    click(point)
    now[0] += 1
    system._update_button_states()
    assert system._button_is_pressed(end)
    release(point)
    assert not system._button_is_pressed(end)
    click(point)
    move((0, 0), held=True)
    assert not system._button_is_pressed(end) and not end.is_hovered
    move(point, held=True)
    assert not system._button_is_pressed(end)
    click(point)
    end.is_enabled = False
    system._update_button_states()
    assert not system._button_is_pressed(end) and not end.is_hovered
    end.is_enabled = True
    system._update_button_states()
    assert not system._button_is_pressed(end)
