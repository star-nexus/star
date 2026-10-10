"""Scene ownership, teardown and failure boundaries for the offline native host."""

from copy import deepcopy
import os
import subprocess
import sys
import pygame
import pytest

pytest.importorskip("star_native")
from framework.engine.events import EBS, Event
from framework.engine.engine_event import KeyDownEvent
from rotk_env import components as c
from rotk_env.runtime import session as module
from rotk_env.runtime.bootstrap import prepare_display_world, encode
from rotk_env.runtime.session import NativeSession
from rotk_env.runtime.native_input import CoordinateInputHandlingSystem
from rotk_env.tests.test_native_input import fonts
from rotk_env.tests.test_native_request_batch import frozen


def listeners():
    return {kind: tuple(callbacks) for kind, callbacks in EBS._listeners.items() if callbacks}


@pytest.fixture
def sdl(monkeypatch):
    initialized = pygame.display.get_init()
    if not initialized:
        monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
        pygame.display.init()
        pygame.display.set_mode((1200, 800))
    try:
        yield
    finally:
        if not initialized:
            pygame.display.quit()


@pytest.mark.parametrize("display", ["none", "dummy"])
@pytest.mark.parametrize("mode", ["real_time", "turn_based"])
@pytest.mark.parametrize("threads", [1, 2, 4])
def test_scene_owns_native_clock_and_retires_input_between_worlds(display, mode, threads, fonts, frozen, sdl):
    before = listeners()
    with NativeSession(display=display, mode=mode, scenario="chibi-small", seed=42, threads=threads) as scene:
        original = scene.runtime.export_state()
        assert len(scene.world.query().with_component(c.Unit).entities()) == 10
        assert [type(s).__name__ for s in scene.world.systems] == (
            ["CoordinateInputHandlingSystem"] if display == "dummy" else [])
        assert scene.world.entity_counter == original["entity_counter"]
        for callbacks in listeners().values():
            for callback in callbacks:
                if callback not in sum(before.values(), ()):
                    assert isinstance(callback.__self__, CoordinateInputHandlingSystem)
        for dt in (1/30, 1/24, 0.0, .5):
            frozen[0] += 123  # Wall seconds must not become simulation dt.
            scene.step(dt, wall_time=frozen[0])
            state = scene.runtime.export_state()
            assert encode(scene.world.get_singleton_component(c.GameTime)) == state["singletons"]["GameTime"]
            scene.update_display(dt)
            assert scene.runtime.export_state() == state
        if mode == "real_time":
            assert scene.runtime.diagnostics()["clock"]["elapsed"] == pytest.approx(1/30 + 1/24 + .5)
        # Mutating a display copy must never modify native authority.
        uid = scene.world.query().with_component(c.UnitCount).ordered_entities()[0]
        before_edit = scene.runtime.export_state()
        scene.world.get_component(uid, c.UnitCount).current_count = 1
        scene.world.get_singleton_component(c.GameStats).faction_stats.clear()
        assert scene.runtime.export_state() == before_edit
        old_controls = scene.controls
        old_world = scene.world
    assert listeners() == before
    assert not old_world.entities and not old_world.systems
    scene.close()
    with pytest.raises(RuntimeError, match="closed"):
        scene.step(1/30)
    with NativeSession(display=display, mode=mode, scenario="chibi-small", seed=7) as second:
        state = second.runtime.export_state()
        with pytest.raises(RuntimeError, match="closed"):
            old_controls.execute("set_fog", enabled=False)
        assert second.runtime.export_state() == state
    assert listeners() == before


@pytest.mark.parametrize("error_at", ["runtime", "subscribe"])
def test_failed_initialization_releases_components_and_partial_subscriptions(error_at, monkeypatch, fonts):
    before = listeners()
    prepared = []
    prepare = module.prepare_display_world
    def capture(**kwargs):
        result = prepare(**kwargs)
        prepared.append(result[0])
        return result
    monkeypatch.setattr(module, "prepare_display_world", capture)
    if error_at == "runtime":
        def fail(*args, **kwargs):
            raise RuntimeError("injected extension load failure")
        monkeypatch.setattr(module, "RustRuntime", fail)
    else:
        subscribe = CoordinateInputHandlingSystem.subscribe_events
        def fail(self):
            subscribe(self)
            raise RuntimeError("injected subscription failure")
        monkeypatch.setattr(CoordinateInputHandlingSystem, "subscribe_events", fail)
    with pytest.raises(RuntimeError, match="injected"):
        NativeSession(display="dummy", scenario="chibi-small", seed=42)
    assert listeners() == before
    assert len(prepared) == 1 and not prepared[0].entities and not prepared[0].systems


def test_event_bus_cannot_hide_native_failure_and_continue_world(monkeypatch, fonts):
    before = listeners()
    with NativeSession(display="dummy", scenario="chibi-small", seed=42) as scene:
        def fail(*args, **kwargs):
            raise RuntimeError("injected native fault")
        monkeypatch.setattr(scene.runtime, "execute_control", fail)
        EBS.publish(KeyDownEvent(key=pygame.K_1, mod=pygame.KMOD_SHIFT, sender="test", timestamp=0))
        assert str(scene.failure) == "injected native fault"
        for operation in (lambda: scene.step(1/30), lambda: scene.update_display(1/30)):
            with pytest.raises(RuntimeError, match="Native session failed") as error:
                operation()
            assert error.value.__cause__ is scene.failure
        with pytest.raises(RuntimeError, match="closed"):
            scene.runtime.export_state()
    assert listeners() == before


@pytest.mark.parametrize("kwargs", [{"scenario": "does-not-exist"}, {"display": "invalid"},
                                   {"hub_url": "ws://invalid"}, {"enable_mock_ai": True}])
def test_prepare_rejects_unsupported_setup_without_touching_other_subscribers(kwargs):
    callback = lambda event: None
    EBS.subscribe(Event, callback)
    original = EBS._listeners
    before = listeners()
    try:
        with pytest.raises(Exception):
            prepare_display_world(**kwargs)
        assert EBS._listeners is original and listeners() == before
    finally:
        EBS.unsubscribe(Event, callback)


def test_prepared_world_has_no_live_simulation_or_shared_state(fonts):
    before = listeners()
    world, state = prepare_display_world(display="dummy", scenario="chibi-small", seed=42)
    try:
        reference = deepcopy(state)
        assert world.systems == [] and listeners() == before
        world.get_singleton_component(c.GameTime).game_elapsed_time = 900
        world.update(10)
        assert state == reference
        assert world.get_singleton_component(c.GameTime).game_elapsed_time == 900
    finally:
        world.reset()


def test_full_window_systems_render_hud_without_python_gameplay_in_dummy_sdl():
    # Own SDL/engine singletons in a subprocess, without altering the test host.
    # Default font tests execution only; Lab Cocoa evidence uses the real font.
    script = '''
import pygame
from framework.engine.game_engine import GameEngine
from framework.engine import RMS
from framework.engine.events import EBS
from rotk_env import components as c
from rotk_env.runtime.session import NativeSession
original_font = pygame.font.Font
pygame.font.Font = lambda path, size: original_font(None, size)
GameEngine(width=1200, height=800, fps=30)
before = {k: tuple(v) for k, v in EBS._listeners.items() if v}
try:
    for mode in ('real_time', 'turn_based'):
        with NativeSession(display='window', scenario='chibi-small', mode=mode, seed=42) as scene:
            names = [type(s).__name__ for s in scene.world.systems]
            assert len(names) == 10, names
            assert {'PanelRenderSystem', 'UIRenderSystem', 'MiniMapSystem'} <= set(names)
            ui = scene.world.get_singleton_component(c.UIState)
            ui.selected_unit = scene.world.query().with_component(c.Unit).ordered_entities()[0]
            ui.show_stats = ui.show_help = ui.show_coordinates = True
            for frame in range(3):
                scene.step(1/30)
                state = scene.runtime.export_state()
                RMS.screen.fill((0, 0, 0))
                scene.update_display(1/30)
                RMS.update(); pygame.display.flip()
                assert scene.runtime.export_state() == state
        assert {k: tuple(v) for k, v in EBS._listeners.items() if v} == before
finally:
    pygame.quit()
'''
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True,
                            env={**os.environ, "HEADLESS": "1", "SDL_VIDEODRIVER": "dummy"}, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
