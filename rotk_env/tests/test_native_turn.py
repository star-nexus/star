"""Faction handoff, human turn reset and statistics preserve legacy sequencing."""
import json
import pytest
pytest.importorskip('star_native')
from rotk_env.components import (Player, GameState, GameTime, GameModeComponent, GameModeStatistics,
                                 MovementPoints, ActionPoints, UnitCount, UnitStatus, BattleLog, UnitObservation, UnitStatistics)
from rotk_env.prefabs.config import Faction, PlayerType, GameMode, UnitState
from rotk_env.runtime.bootstrap import export_initial_state
from rotk_env.runtime.native import RustRuntime
from rotk_env.systems.game_time_system import GameTimeSystem
from rotk_env.systems.turn_system import TurnSystem
from rotk_env.systems.statistics_system import StatisticsSystem
from rotk_env.systems.llm_system import LLMSystem
from rotk_env.tests.test_native_vision import make_vision_world
from rotk_env.tests.test_native_request_batch import frozen
from rotk_env.tests.test_native_lifecycle import snapshot, capture_events


def setup(display):
    world,(a,b,c),vision=make_vision_world(display)
    world.get_singleton_component(GameModeComponent).mode=GameMode.TURN_BASED
    state=world.get_singleton_component(GameState);state.game_mode=GameMode.TURN_BASED
    world.add_system(GameTimeSystem())
    world.add_singleton_component(BattleLog())
    world.add_system(StatisticsSystem())
    for faction,units in [(Faction.WEI,{a,b}),(Faction.SHU,{c}),(Faction.WU,set())]:
        pid=world.create_entity();world.add_component(pid,Player(faction=faction,player_type=PlayerType.HUMAN,color=(255,255,255),units=units))
    turn=TurnSystem();world.add_system(turn)
    llm=LLMSystem();world.add_system(llm)
    # Exercise reset details; AP on a unit without MP must stay unchanged.
    world.get_component(a,UnitCount).current_count=20
    for uid in (a,b,c):
        world.get_component(uid,ActionPoints).current_ap=0
        world.get_component(uid,MovementPoints).current_mp=0
        world.get_component(uid,MovementPoints).has_moved=True
    world.remove_component(b,MovementPoints)
    status=world.get_component(a,UnitStatus);status.current_status=UnitState.CONFUSION
    status.status_duration=2;status.wait_turns=1
    return world,(a,b,c),turn,llm


@pytest.mark.parametrize('display',['none','dummy','window'])
@pytest.mark.parametrize('human',[False,True])
def test_turn_handoff_round_reset_events_and_clock(display,human,frozen,monkeypatch):
    for cls,field in ((UnitStatistics,'creation_time'),(UnitObservation,'last_seen_time')):
        original=cls.__init__
        def initialize(self,*args,_init=original,_field=field,**kwargs):
            _init(self,*args,**kwargs);setattr(self,_field,frozen[0])
        monkeypatch.setattr(cls,'__init__',initialize)
    world,(a,b,c),turn,llm=setup(display)
    events=capture_events(monkeypatch)
    reg=dict(provider='synthetic',model_id='fake',base_url='https://host')
    try:
        with RustRuntime(export_initial_state(world,display=display)) as native:
            native.take_presentation_delta()
            for faction in ('wei','shu','wu'):
                params={**reg,'faction':faction}
                expected=llm._process_action_request(agent_id=faction,action_id=0,action='register_agent_info',params=params.copy(),send_response=False)
                assert native.execute_action('register_agent_info',params,agent_id=faction)==json.loads(json.dumps(expected))
                snapshot(world,native,display)
            for i in range(35):
                frozen[0]+=.125
                previous=world.get_singleton_component(GameState).current_player.value
                if human:
                    turn.end_turn();native.finish_human_turn(wall_time=frozen[0])
                else:
                    params={'faction':previous,'force':None if i%2 else True}
                    expected=llm._process_action_request(agent_id=previous,action_id=i,action='end_turn',params=params.copy(),send_response=False)
                    assert native.execute_action('end_turn',params,agent_id=previous)==json.loads(json.dumps(expected))
                snapshot(world,native,display)
                assert native.take_presentation_delta()['events']==events;events.clear()
                # Time's round number synchronizes on the next tick, not in end_turn.
                world.update(1/30);native.step(1/30,wall_time=frozen[0]);snapshot(world,native,display)
                assert native.take_presentation_delta()['events']==events;events.clear()
                if i==4:native.reset(native.export_state())
            assert world.get_component(a,MovementPoints).current_mp==3  # original severe-loss rule
            assert world.get_component(b,ActionPoints).current_ap==0   # no MP => no AP reset
    finally:world.reset()


@pytest.mark.parametrize('ending',['annihilation','timeout','already_over'])
@pytest.mark.parametrize('human',[False,True])
def test_game_over_precedence_and_human_reset_before_check(ending,human,frozen,monkeypatch):
    world,(a,b,c),turn,llm=setup('none')
    state=world.get_singleton_component(GameState)
    if ending=='annihilation':world.get_component(c,UnitCount).current_count=0
    elif ending=='timeout':state.turn_number=state.max_turns+1
    else:state.game_over=True
    events=capture_events(monkeypatch)
    try:
        with RustRuntime(export_initial_state(world)) as native:
            native.take_presentation_delta()
            faction=state.current_player.value
            params=dict(faction=faction,provider='synthetic',model_id='fake',base_url='https://host')
            llm._process_action_request(agent_id=faction,action_id=0,action='register_agent_info',params=params.copy(),send_response=False)
            native.execute_action('register_agent_info',params,agent_id=faction)
            if human:turn.end_turn();native.finish_human_turn(wall_time=frozen[0])
            else:
                params={'faction':faction}
                expected=llm._process_action_request(agent_id=faction,action_id=1,action='end_turn',params=params.copy(),send_response=False)
                assert native.execute_action('end_turn',params,agent_id=faction)==json.loads(json.dumps(expected))
            snapshot(world,native,'none');assert native.take_presentation_delta()['events']==events
            assert world.get_component(a,ActionPoints).current_ap==(2 if human else 0)
    finally:world.reset()


def test_turn_duration_sum_matches_python_with_cancellation(frozen):
    world,ids,turn,llm=setup('none')
    stats=world.get_singleton_component(GameModeStatistics)
    stats.turn_based_stats['turn_durations']=[1e16,1.,-1e16]
    try:
        with RustRuntime(export_initial_state(world)) as native:
            frozen[0]+=.125
            turn.end_turn();native.finish_human_turn(wall_time=frozen[0]);snapshot(world,native,'none')
    finally:world.reset()


def test_stale_extension_and_scene_fail_explicitly(frozen,monkeypatch):
    import star_native
    from rotk_env.runtime.native import load_native
    world,ids,turn,llm=setup('none')
    try:
        initial=export_initial_state(world)
        with RustRuntime(initial) as runtime:
            before=runtime.export_state()
            initial['schema']=1
            with pytest.raises(RuntimeError,match='schema or oracle'):
                runtime.reset(initial)
            assert runtime.export_state()==before
        monkeypatch.delattr(star_native,'API_VERSION')
        with pytest.raises(RuntimeError,match='API version mismatch'):
            load_native()
    finally:world.reset()
