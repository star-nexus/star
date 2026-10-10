"""Experimental offline CLI/scene selection and authoritative post-game handoff."""
from types import SimpleNamespace
import pytest

pytest.importorskip('star_native')
from rotk_env import components as c
from rotk_env.main import parse_arguments, game_scene_kwargs_from_args
from rotk_env.scenes.game_scene import GameScene
from rotk_env.runtime import session as module
from rotk_env.runtime.settlement import NativeSettlementFormatter
from rotk_env.tests.test_native_session import sdl, listeners
from rotk_env.tests.test_native_input import fonts
from rotk_env.tests.test_native_request_batch import frozen


def test_backend_cli_defaults_and_explicit_selection(monkeypatch):
    monkeypatch.setattr('sys.argv',['star'])
    args=parse_arguments()
    assert args.backend=='rust' and args.native_threads==1
    monkeypatch.setattr('sys.argv',['star','--backend','rust','--native-threads','4','--no-hub'])
    kwargs=game_scene_kwargs_from_args(parse_arguments())
    assert kwargs['backend']=='rust' and kwargs['native_threads']==4 and kwargs['hub_url'] is None


@pytest.mark.parametrize('mode',['real_time','turn_based'])
def test_scene_reuses_native_session_and_headless_settlement_exit(mode,fonts,sdl,frozen,monkeypatch):
    original=module.prepare_display_world
    def ended(**kwargs):
        world,initial=original(**kwargs)
        initial['singletons']['GameState'].update(game_over=True,winner='wei')
        return world,initial
    monkeypatch.setattr(module,'prepare_display_world',ended)
    reports=[]
    monkeypatch.setattr(NativeSettlementFormatter,'_save_report_to_files',lambda self,data:reports.append(data))
    monkeypatch.setattr(NativeSettlementFormatter,'_print_report_summary',lambda self,data:None)
    stopped=[]
    engine=SimpleNamespace(runtime_backend='rust',native_threads=1,stop=lambda event:stopped.append(event))
    scene=GameScene(engine)
    before=listeners()
    try:
        scene.enter(headless=True,hub_url=None,scenario='chibi-small',seed=42,mode=mode)
        old=scene.native_session;old_controls=old.controls
        assert scene.backend=='rust' and old is not None
        assert all(type(s).__name__ not in ('GameTimeSystem','CombatSystem','RealtimeSystem','TurnSystem') for s in scene.world.systems)
        scene.update(1/30)
        assert not stopped and not reports
        frozen[0]+=60
        scene.update(1/30)
        assert len(stopped)==1 and len(reports)==1
        assert reports[0]['units_info']['wei']['total_units']==5
        scene.exit()
        assert old.closed and listeners()==before
        scene.enter(headless=True,hub_url=None,scenario='chibi-small',seed=7,mode=mode)
        assert scene.native_session is not old
        snapshot=scene.native_session.runtime.export_state()
        with pytest.raises(RuntimeError,match='closed'):
            old_controls.execute('set_fog',enabled=False)
        assert scene.native_session.runtime.export_state()==snapshot
        assert scene.game_end_wait_start is None and not scene._headless_exit_triggered
        scene.update(1/30)
        frozen[0]+=60
        scene.update(1/30)
        assert len(stopped)==2 and len(reports)==2
    finally:
        scene.exit()
    assert listeners()==before


@pytest.mark.parametrize('extra',[{'enable_mock_ai':True},{'scale_harness_socket':'/tmp/not-used'}])
def test_rust_scene_rejects_unconnected_hosts_before_starting_world(extra):
    scene=GameScene(SimpleNamespace(runtime_backend='rust',native_threads=1))
    with pytest.raises(ValueError):
        scene.enter(**{**dict(headless=True,hub_url=None,scenario='chibi-small',seed=42), **extra})
    assert not scene.initialized and not scene.world.entities
    scene.exit()


def test_requested_rust_load_failure_exits_nonzero_without_window(monkeypatch):
    from rotk_env import main as entry
    from rotk_env.runtime import native
    monkeypatch.setattr('sys.argv',['star','--backend','rust','--no-hub','--headless'])
    def unavailable():raise RuntimeError('injected missing extension')
    monkeypatch.setattr(native,'load_native',unavailable)
    monkeypatch.setattr(entry,'GameEngine',lambda **kwargs:pytest.fail('must fail before creating a window'))
    with pytest.raises(SystemExit) as error:entry.main()
    assert error.value.code==1
