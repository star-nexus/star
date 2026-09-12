"""Core World.update lifecycle parity; presentation/settlement remain separate gates."""
import json
import time
import pytest
pytest.importorskip('star_native')
from framework.engine.events import EBS
from rotk_env.components import (GameTime, GameState, GameModeComponent, UnitCount, Combat,
                                 HexPosition, UnitObservation, UnitStatistics)
from rotk_env.prefabs.config import GameMode, GameConfig
from rotk_env.runtime.bootstrap import export_initial_state, encode
from rotk_env.runtime.native import RustRuntime
from rotk_env.systems.game_time_system import GameTimeSystem
from rotk_env.systems.realtime_system import RealtimeSystem
from rotk_env.systems.window_realtime_system import RealtimeSystem as WindowRealtime
from rotk_env.systems.turn_system import TurnSystem
from rotk_env.systems.resource_recovery_system import ResourceRecoverySystem
from rotk_env.systems.statistics_system import StatisticsSystem
from rotk_env.systems.window_statistics_system import StatisticsSystem as WindowStatistics
from rotk_env.systems.llm_system import LLMSystem
from rotk_env.tests.test_native_vision import make_vision_world
from rotk_env.tests.test_native_request_batch import frozen
from rotk_env.utils.unit_spatial_index import rebuild_unit_spatial_index


def snapshot(world, native, display):
    expected = export_initial_state(world, display=display)
    expected['clock']['tick'] = native.diagnostics()['clock']['tick']
    assert native.export_state() == expected


def capture_events(monkeypatch):
    events = []
    publish = EBS.publish
    def capture(event):
        events.append({'type': type(event).__name__, 'fields': encode(event)})
        publish(event)
    monkeypatch.setattr(EBS, 'publish', capture)
    return events


@pytest.mark.parametrize('display', ['none', 'dummy', 'window'])
@pytest.mark.parametrize('mode', [GameMode.REAL_TIME, GameMode.TURN_BASED])
@pytest.mark.parametrize('ending', ['ongoing', 'annihilation', 'mutual', 'timeout', 'positionless'])
def test_lifecycle_winner_timeout_and_clock_sync(display, mode, ending, frozen, monkeypatch):
    world, (a,b,c), vision = make_vision_world(display)
    world.get_singleton_component(GameModeComponent).mode = mode
    state = world.get_singleton_component(GameState); state.game_mode = mode
    world.add_system(GameTimeSystem())
    system = (WindowRealtime() if display=='window' else RealtimeSystem()) if mode==GameMode.REAL_TIME else TurnSystem()
    world.add_system(system)
    clock = world.get_singleton_component(GameTime)
    if ending in ('annihilation','mutual'):
        world.get_component(c,UnitCount).current_count = 0
        if ending=='mutual':
            for uid in (a,b): world.get_component(uid,UnitCount).current_count = 0
        # Also timed out: annihilation has priority.
        clock.game_elapsed_time = GameConfig.MAX_REALTIME_SECONDS
        state.turn_number = GameConfig.MAX_TURNS+1
    elif ending=='timeout':
        clock.game_elapsed_time = GameConfig.MAX_REALTIME_SECONDS
        state.turn_number = GameConfig.MAX_TURNS+1
    elif ending=='positionless':
        world.remove_component(c,HexPosition)
    if display=='window': rebuild_unit_spatial_index(world)
    events = capture_events(monkeypatch)
    try:
        with RustRuntime(export_initial_state(world,display=display)) as native:
            native.take_presentation_delta()
            for index in range(2):
                frozen[0] += .25
                world.update(.25); native.step(.25,wall_time=frozen[0])
                snapshot(world,native,display)
                assert native.take_presentation_delta()['events'] == events
                events.clear()
            over = ending not in ('ongoing','positionless') or (ending=='positionless' and display=='window' and mode==GameMode.REAL_TIME)
            assert state.game_over is over
    finally: world.reset()


@pytest.mark.parametrize('clock_enabled,lifecycle_enabled,paused', [(True,True,False),(True,True,True),(False,True,False),(True,False,False)])
def test_timeout_uses_simulation_boundary_and_enabled_systems(clock_enabled,lifecycle_enabled,paused,frozen):
    world,ids,vision = make_vision_world('none')
    timer=GameTimeSystem(); world.add_system(timer)
    policy=RealtimeSystem(); world.add_system(policy)
    timer.enabled=clock_enabled; policy.enabled=lifecycle_enabled
    clock=world.get_singleton_component(GameTime); clock.paused=paused
    clock.game_elapsed_time=GameConfig.MAX_REALTIME_SECONDS-.5
    try:
        with RustRuntime(export_initial_state(world)) as native:
            for dt in (.25,.25,0.,1.):
                frozen[0]+=1000.  # Large wall jumps cannot expire a simulation timeout.
                world.update(dt); native.step(dt,wall_time=frozen[0]); snapshot(world,native,'none')
            assert world.get_singleton_component(GameState).game_over is (clock_enabled and lifecycle_enabled and not paused)
    finally: world.reset()


@pytest.mark.parametrize('display', ['none','dummy','window'])
def test_core_world_tick_move_query_attack_and_recovery(display,frozen,monkeypatch):
    # Factories capture time.time at class creation, so freeze their metadata explicitly.
    for cls,field in ((UnitStatistics,'creation_time'),(UnitObservation,'last_seen_time')):
        original=cls.__init__
        def initialize(self,*args,_init=original,_field=field,**kwargs):
            _init(self,*args,**kwargs);setattr(self,_field,frozen[0])
        monkeypatch.setattr(cls,'__init__',initialize)
    world,(a,b,c),vision=make_vision_world(display)
    world.add_system(GameTimeSystem())
    world.add_system(WindowStatistics(batch_size=1) if display=='window' else StatisticsSystem())
    world.add_system(ResourceRecoverySystem())
    world.add_system(WindowRealtime() if display=='window' else RealtimeSystem())
    llm=LLMSystem();world.add_system(llm)
    world.get_component(a,Combat).attack_range=5
    world.get_component(c,UnitCount).current_count=1
    events=capture_events(monkeypatch)
    reg=dict(provider='synthetic',model_id='fake',base_url='https://host')
    try:
        with RustRuntime(export_initial_state(world,display=display)) as native:
            native.take_presentation_delta()
            def command(agent,action,params):
                expected=llm._process_action_request(agent_id=agent,action_id=0,action=action,params=dict(params),send_response=False)
                result=native.execute_action(action,params,agent_id=agent,wall_time=frozen[0])
                assert result==json.loads(json.dumps(expected))
                snapshot(world,native,display)
                assert native.take_presentation_delta()['events']==events
                events.clear()
            command('alpha','register_agent_info',{**reg,'faction':'wei'})
            command('enemy','register_agent_info',{**reg,'faction':'shu'})
            command('alpha','claim_units',{'unit_ids':[a,b]})
            for index in range(120):
                frozen[0]+=.25
                if index==0:
                    command('alpha','move',{'unit_id':a,'target_position':{'col':-2,'row':0}})
                    command('alpha','move',{'unit_id':b,'target_position':{'col':-1,'row':1}})
                if index==40 and display=='none':
                    command('alpha','attack',{'unit_id':a,'target_id':c})
                    assert not world.get_singleton_component(GameState).game_over
                if index in (0,20,40,80,119):
                    command('alpha','get_faction_state',{'faction':'wei'})
                world.update(1/30);native.step(1/30,wall_time=frozen[0]);snapshot(world,native,display)
                assert native.take_presentation_delta()['events']==events
                events.clear()
                if index==60:
                    native.reset(native.export_state());snapshot(world,native,display)
    finally:world.reset()
