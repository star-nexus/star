"""All non-frame observation variants use the same trusted request contract."""
import pytest
pytest.importorskip('star_native')
from rotk_env.components import (ActionPoints, Combat, FogOfWar, HexPosition, MapData,
    MatchRules, MovementAnimation, MovementPoints, UnitCount, UnitStatus, Vision,
    TerritoryControl, BattleLog, GameStats, Unit)
from rotk_env.prefabs.config import Faction, GameMode, UnitState
from rotk_env.prefabs.action_catalog import GAME_ACTIONS
from rotk_env.runtime.bootstrap import encode, export_initial_state
from rotk_env.runtime.native import RustRuntime, ActionRequest
from rotk_env.tests.test_native_unit_actions import setup, register
from rotk_env.tests.test_native_request_batch import frozen
from rotk_env.tests.test_native_lifecycle import snapshot

QUERIES=('observation','unit_observation','faction_observation','limited_observation','godview_observation')


def make(display='none', mode=GameMode.REAL_TIME, case='normal'):
    w, ids, territory, llm = setup(display, mode)
    w.get_singleton_component(MatchRules).game_actions=tuple(s.name for s in GAME_ACTIONS)
    a,b,c=ids
    w.add_component(a,Vision(range=3,visible_tiles={(-1,0),(0,0),(0,1),(1,0),(-2,0)}))
    w.add_component(b,Vision(range=2,visible_tiles=set()))
    if case=='empty_vision':w.get_component(a,Vision).visible_tiles.clear()
    if case=='fog':w.add_singleton_component(FogOfWar(enabled=True, faction_vision={Faction.WEI:set()},explored_tiles={Faction.WEI:{(0,1)}}))
    if case=='fog_fallback':w.add_singleton_component(FogOfWar(enabled=True))
    if case=='dead':w.get_component(c,UnitCount).current_count=0
    if case=='wounded':w.get_component(a,UnitCount).current_count=1
    if case=='confused':w.get_component(a,UnitStatus).current_status=UnitState.CONFUSION
    if case=='raw_confused':w.get_component(a,UnitStatus).current_status='confusion'
    if case=='moving':w.add_component(a,MovementAnimation(path=[(-1,0),(0,0)],is_moving=True))
    if case=='zero_mp':w.get_component(a,MovementPoints).current_mp=0
    if case=='zero_ap':w.get_component(a,ActionPoints).current_ap=0
    if case=='no_combat_system':w.systems=[s for s in w.systems if type(s).__name__!='CombatSystem']
    if case=='no_territory_system':w.systems.remove(territory)
    if case=='no_count':w.remove_component(a,UnitCount)
    if case=='no_combat':w.remove_component(a,Combat)
    if case=='no_position':w.remove_component(a,HexPosition)
    if case=='no_mp':w.remove_component(a,MovementPoints)
    if case=='no_unit':w.remove_component(a,Unit)
    if case=='territory':
        tile=w.get_singleton_component(MapData).tiles[0,0]
        t=w.get_component(tile,TerritoryControl);t.controlling_faction=Faction.WEI;t.is_city=True;t.fortified=True;t.fortification_level=2
        t.being_captured=True;t.capturing_unit=c
    return w,ids,llm


def call(world,native,llm,action,params,display='none',agent='alpha'):
    expected=llm._process_action_request(agent_id=agent,action_id=0,action=action,params=dict(params),send_response=False)
    actual=native.execute_action(action,params,agent_id=agent)
    assert encode(actual)==encode(expected), (action,params,actual,expected)
    snapshot(world,native,display)
    return actual


@pytest.mark.parametrize('display',['none','dummy','window'])
@pytest.mark.parametrize('case',['normal','empty_vision','fog','fog_fallback','dead','wounded','confused','raw_confused','moving','zero_mp','zero_ap','no_count','no_combat','no_position','no_mp','no_unit','territory','no_combat_system','no_territory_system'])
def test_variants_data_permissions_and_same_revision_cache(display,case,frozen):
    world,(a,b,c),llm=make(display,case=case)
    try:
        with RustRuntime(export_initial_state(world,display=display)) as native:
            register(world,native,llm,display)
            for action,params in [('observation',{'unit_id':a,'observation_level':'tactical'}),
                                  ('unit_observation',{'unit_id':a}),('unit_observation',{'unit_id':b}),
                                  ('unit_observation',{'unit_id':c}), # Match's legacy unit query has no ownership gate.
                                  ('faction_observation',{'faction':'wei','include_hidden':True}),
                                  ('faction_observation',{'faction':'wei','include_hidden':False}),
                                  ('limited_observation',{'faction':'wei'}),('godview_observation',{})]:
                first=call(world,native,llm,action,params,display)
                frozen[0]+=1
                second=call(world,native,llm,action,params,display)
                if action!='observation' and first.get('operation')=='get_observation':
                    assert second.get('from_cache')
                    if first.get('success'):assert first['metadata']['timestamp']==second['metadata']['timestamp']
                # Returned objects cannot alter the world's cached observation.
                first.clear()
            call(world,native,llm,'faction_observation',{'faction':'shu'},display)
    finally:world.reset()


@pytest.mark.parametrize('action',QUERIES)
@pytest.mark.parametrize('params',[{}, {'unit_id':'3'},{'unit_id':False},{'unit_id':-1},{'unit_id':9999},
    {'unit_id':1.5},{'unit_id':0,'faction':'invalid'},{'unit_id':0,'faction':False},
    {'unit_id':0,'faction':'SHU'},{'unit_id':0,'faction':19},
    {'unit_id':0,'faction':'wei','include_hidden':[]}, {'unit_id':0,'faction':'wei','include_hidden':None}])
def test_variant_parameter_errors_and_legacy_wrapper_order(action,params,frozen):
    w,ids,llm=make()
    try:
        with RustRuntime(export_initial_state(w)) as native:
            register(w,native,llm)
            call(w,native,llm,action,params)
            call(w,native,llm,action,params)
    finally:w.reset()


@pytest.mark.parametrize('display',['none','dummy','window'])
@pytest.mark.parametrize('mode',[GameMode.REAL_TIME,GameMode.TURN_BASED])
@pytest.mark.parametrize('threads',[1,2,4])
def test_query_write_query_batch_reset_and_full_state(display,mode,threads,frozen):
    w,(a,b,c),llm=make(display,mode)
    try:
        with RustRuntime(export_initial_state(w,display=display),threads=threads) as native:
            register(w,native,llm,display)
            initial=native.export_state()
            requests=[ActionRequest('alpha',action,params,frozen[0], '') for action,params in [
                ('unit_observation',{'unit_id':a}),('faction_observation',{'faction':'wei'}),
                ('rest',{'unit_id':a}),('unit_observation',{'unit_id':a}),
                ('occupy',{'unit_id':a,'position':{'col':-1,'row':0}}),
                ('faction_observation',{'faction':'wei'}),('limited_observation',{'faction':'wei'}),
                ('godview_observation',{}),('godview_observation',{}),('get_faction_state',{'faction':'wei'})]]
            expected=[]
            for r in requests:expected.append(call(w,native,llm,r.action,r.parameters,display))
            with RustRuntime(initial,threads=threads) as batched:
                assert encode(batched.execute_actions(requests))==encode(expected)
                assert batched.export_state()==native.export_state()
            # Mid-world import carries valid query results, including the timestamp.
            imported=export_initial_state(w,display=display)
            native.reset(imported)
            assert call(w,native,llm,'godview_observation',{},display).get('from_cache')
            for dt in (.1,1.,30.):
                frozen[0]+=100;w.update(dt);native.step(dt,wall_time=frozen[0]);snapshot(w,native,display)
                assert not call(w,native,llm,'godview_observation',{},display).get('from_cache')
            native.reset(initial)
            result=native.execute_action('unit_observation',{'unit_id':a},agent_id='alpha')
            assert not result.get('from_cache') and isinstance(result['data']['visible_area'],set)
    finally:w.reset()


@pytest.mark.parametrize('legacy_fields',[False,True])
def test_nonempty_battle_history_keeps_existing_error_and_complete_legacy_records(legacy_fields,frozen):
    from rotk_env.components.battle_log import BattleLogEntry
    w,ids,llm=make()
    entries=[]
    for i in range(12):
        e=BattleLogEntry(message=f'battle {i}')
        if legacy_fields:
            e.turn=i;e.attacker_name='a';e.defender_name='b';e.damage=i;e.result='hit'
        entries.append(e)
    w.add_singleton_component(BattleLog(entries=entries))
    try:
        with RustRuntime(export_initial_state(w)) as native:
            register(w,native,llm)
            for _ in range(2):
                result=call(w,native,llm,'godview_observation',{})
                if legacy_fields:assert len(result['data']['battle_history'])==10
                else:
                    assert result['error_code']=='INTERNAL_ERROR'
                    assert "has no attribute 'turn'" in result['error']
                    assert not result.get('from_cache')
    finally:w.reset()


@pytest.mark.parametrize('action',QUERIES)
def test_observation_match_subset_and_registration_gates(action,frozen):
    w,(a,b,c),llm=make()
    w.get_singleton_component(MatchRules).game_actions=('move','attack','get_faction_state')
    try:
        with RustRuntime(export_initial_state(w)) as native:
            assert call(w,native,llm,action,{'unit_id':a,'faction':'wei'})['error_code']==2005
            register(w,native,llm)
            assert call(w,native,llm,action,{'unit_id':a,'faction':'wei'})['error_code']==2003
    finally:w.reset()


@pytest.mark.parametrize('raw',[['wei'],{'key':'wei'}])
def test_limited_observation_unhashable_faction_retains_error_without_caching(raw,frozen):
    w,ids,llm=make(case='fog')
    try:
        with RustRuntime(export_initial_state(w)) as native:
            register(w,native,llm)
            for _ in range(2):
                result=call(w,native,llm,'limited_observation',{'faction':raw})
                assert result['error_code']=='INTERNAL_ERROR' and not result.get('from_cache')
    finally:w.reset()
