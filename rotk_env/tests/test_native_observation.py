"""Read-only native faction projection, exact decoded responses and cache scope."""
import json
import pytest
pytest.importorskip('star_native')
from star_native import NativeRuntime
from rotk_env.components import (ActionPoints, Combat, FogOfWar, GameStats, GameState,
                                 TeamCoordination, UnitCount, UnitSkills)
from rotk_env.prefabs.config import Faction
from rotk_env.runtime.bootstrap import export_initial_state
from rotk_env.systems.llm_action_handler import LLMActionHandler
from rotk_env.systems.movement_system import MovementSystem
from rotk_env.systems.combat_system import CombatSystem
from rotk_env.tests.test_native_vision import make_vision_world
from rotk_env.tests.test_native_movement import probe
from rotk_env.tests.test_native_combat import combat_probe


def observe(native,requests):
    return json.loads(native._observation_probe_json(json.dumps(requests)))


def setup(display='none'):
    world,ids,vision=make_vision_world(display)
    stats=world.get_singleton_component(GameStats)
    if stats is None:
        stats=GameStats();world.add_singleton_component(stats)
    stats.agent_id_to_faction={'alpha':Faction.WEI,'beta':Faction.WEI,'enemy':Faction.SHU}
    coord=TeamCoordination();coord.claim_units('alpha',[ids[0]])
    world.add_singleton_component(coord)
    return world,ids,vision


@pytest.mark.parametrize('display',['none','dummy','window'])
@pytest.mark.parametrize('fog',[False,True])
def test_faction_panels_permissions_subsets_and_batch_reuse(display,fog):
    world,(a,b,c),vision=setup(display)
    world.get_singleton_component(FogOfWar).enabled=fog
    native=NativeRuntime(json.dumps(export_initial_state(world,display=display)))
    handler=LLMActionHandler(world)
    requests=[{'faction':'wei','agent_id':'alpha'}, {'faction':'shu','agent_id':'enemy'},
              {'faction':'wei','agent_id':'beta','unit_ids':[b,a,b]},
              {'faction':'wei','agent_id':'alpha','unit_ids':[]}, {'faction':'wu'},
              {'faction':'wei','agent_id':'alpha','unit_ids':[a]}]
    try:
        before=native.export_state_json()
        actual=observe(native,requests)
        assert actual['results']==[handler.handle_faction_state(p) for p in requests]
        assert native.export_state_json()==before
        assert actual['metrics']['census_builds']==1
        assert actual['metrics']['faction_builds']==3
        assert actual['metrics']['panel_builds']==3
        if not fog:
            # Every visible unit can appear as an enemy to another faction; built once.
            assert actual['metrics']['enemy_builds']==3
            assert actual['metrics']['tile_builds']==len(actual['results'][0]['visible_terrain'])
        assert actual['results'][0]['units'][0]['commandable'] is True
        assert next(u for u in actual['results'][2]['units'] if u['unit_id']==a)['commandable'] is False
        assert actual['results'][3]['visible_enemy_units']==actual['results'][0]['visible_enemy_units']
    finally:
        native.close();world.reset()


@pytest.mark.parametrize('params',[{}, {'faction':''}, {'faction':'invalid'},
    {'faction':'shu','agent_id':'alpha'}, {'faction':'wei','unit_ids':None},
    {'faction':'wei','unit_ids':[True]}, {'faction':'wei','unit_ids':[1.]},
    {'faction':'wei','unit_ids':[-1]}, {'faction':'wei','unit_ids':[999999]}])
def test_invalid_projection_request_matches_python(params):
    world,ids,vision=setup();native=NativeRuntime(json.dumps(export_initial_state(world)))
    try:
        assert observe(native,[params])['results']==[LLMActionHandler(world).handle_faction_state(params)]
    finally:
        native.close();world.reset()


def test_selected_dead_and_foreign_units_have_distinct_semantics():
    world,(a,b,c),vision=setup();world.get_component(b,UnitCount).current_count=0
    native=NativeRuntime(json.dumps(export_initial_state(world)))
    requests=[{'faction':'wei','unit_ids':[b,a,b]}, {'faction':'wei','unit_ids':[c]}]
    try:
        result=observe(native,requests)['results']
        assert result==[LLMActionHandler(world).handle_faction_state(p) for p in requests]
        assert [u['unit_id'] for u in result[0]['units']]==[a]
    finally:
        native.close();world.reset()


def test_move_query_attack_query_batches_never_reuse_stale_world():
    world,(a,b,c),vision=setup()
    world.get_component(a,Combat).attack_range=5
    world.get_component(c,UnitCount).current_count=1
    native=NativeRuntime(json.dumps(export_initial_state(world)))
    movement=next(s for s in world.systems if isinstance(s,MovementSystem))
    combat=next(s for s in world.systems if isinstance(s,CombatSystem))
    handler=LLMActionHandler(world);params={'faction':'wei','agent_id':'alpha'}
    try:
        q0=observe(native,[params])['results'][0]
        assert probe(native,'move',a,(-2,0))==json.loads(json.dumps(movement.move_unit(a,(-2,0))))
        q1=observe(native,[params])['results'][0]
        assert q1==handler.handle_faction_state(params)
        assert q0['units'][0]['position']!=q1['units'][0]['position']
        assert combat_probe(native,'attack',a,c)==combat.execute_attack(a,c)
        q2=observe(native,[params])['results'][0]
        assert q2==handler.handle_faction_state(params)
        assert q1['visible_enemy_units'] and not q2['visible_enemy_units']
        # Returned Python data remains owned across reset and close.
        native.reset(native.export_state_json());native.close()
        assert q1['visible_enemy_units']
    finally:
        native.close();world.reset()


@pytest.mark.parametrize('winner',[None,Faction.WEI,Faction.SHU])
def test_finished_faction_state_and_skills(winner):
    world,(a,b,c),vision=setup()
    world.add_singleton_component(GameState(current_player=Faction.WEI,game_over=True,winner=winner))
    world.add_component(a,UnitSkills(available_skills={'hide','charge','rockslide','arrow_evasion'}))
    native=NativeRuntime(json.dumps(export_initial_state(world)))
    params={'faction':'wei'}
    try:
        assert observe(native,[params])['results']==[LLMActionHandler(world).handle_faction_state(params)]
    finally:
        native.close();world.reset()
