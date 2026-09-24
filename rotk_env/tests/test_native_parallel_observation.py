"""Scoped native reads preserve responses/state across worker counts and writes."""
import copy
import json
import pytest
pytest.importorskip('star_native')
from star_native import NativeRuntime
from rotk_env import components as c
from rotk_env.prefabs.config import Faction
from rotk_env.runtime.bootstrap import export_initial_state
from rotk_env.systems.llm_action_handler import LLMActionHandler
from rotk_env.tests.test_native_observation import setup
from rotk_env.tests.test_faction_state_affordances import _spawn
from rotk_env.utils.unit_spatial_index import rebuild_unit_spatial_index


@pytest.mark.parametrize('display', ['none', 'dummy', 'window'])
@pytest.mark.parametrize('fog', [False, True])
def test_worker_modes_match_python_keep_query_state_and_bound_jobs(display, fog):
    world,(a,b,enemy),_=setup(display)
    own=[a,b]
    for i in range(14):
        own.append(_spawn(world,faction=Faction.WEI,col=-1,row=i%2,mp=3))
    world.get_singleton_component(c.FogOfWar).enabled=fog
    world.get_component(a,c.Combat).attack_range=5
    world.get_component(enemy,c.UnitCount).current_count=1
    if display=="window":rebuild_unit_spatial_index(world)
    initial=json.dumps(export_initial_state(world,display=display))
    params=[dict(faction='wei',agent_id='alpha',unit_ids=list(reversed(own))+own[:2]),
            dict(faction='wei',agent_id='beta',unit_ids=own),
            dict(faction='shu',agent_id='enemy')]
    expected=[LLMActionHandler(world).handle_faction_state(p) for p in params]
    reference=None
    try:
        for threads in (1,2,4):
            n=NativeRuntime(initial,threads)
            try:
                result=json.loads(n._observation_probe_json(json.dumps(params)))
                assert result['results']==expected
                assert json.loads(n.export_state_json())==json.loads(initial)
                metrics=result['metrics']
                work={k:v for k,v in metrics.items() if k not in ('parallel_panel_batches','panel_tasks','panel_worker_threads')}
                if reference is None:reference=work
                assert work==reference
                assert metrics['parallel_panel_batches']==(0 if threads==1 else 1)
                assert metrics['panel_tasks']==(0 if threads==1 else threads)
                assert (metrics['panel_worker_threads']==0 if threads==1 else 1<=metrics['panel_worker_threads']<=threads)
                # A failed reset must not replace the world or retire its pool.
                with pytest.raises(RuntimeError):n.reset('{}')
                assert json.loads(n._observation_probe_json(json.dumps(params)))['results']==expected
                n.reset(initial)
                assert json.loads(n._observation_probe_json(json.dumps(params)))['results']==expected
            finally:n.close()
    finally:world.reset()


@pytest.mark.parametrize('threads', [1,2,4])
def test_parallel_reads_rebuild_after_ownership_move_death_and_reset(threads):
    world,(a,b,enemy),_=setup('none')
    own=[a,b]+[_spawn(world,faction=Faction.WEI,col=-1,row=i%2,mp=3) for i in range(10)]
    world.get_component(a,c.Combat).attack_range=5
    world.get_component(enemy,c.UnitCount).current_count=1
    world.get_singleton_component(c.FogOfWar).enabled=False
    initial=json.dumps(export_initial_state(world))
    def req(action,**parameters):
        return dict(agent_id='alpha',action=action,parameters=parameters,wall_time=1720000000.)
    q=req('get_faction_state',faction='wei',unit_ids=own)
    operations=[q,req('release_units',unit_ids=[a]),q,
                req('move',unit_id=a,target_position=dict(col=-2,row=0)),q,
                req('attack',unit_id=a,target_id=enemy),q]
    n=NativeRuntime(initial,threads);serial=NativeRuntime(initial,1)
    try:
        expected=json.loads(serial.execute_actions_json(json.dumps(operations)))
        actual=json.loads(n.execute_actions_json(json.dumps(operations)))
        assert actual['results']==expected['results']
        assert n.export_state_json()==serial.export_state_json()
        assert expected['results'][0]['units'][0]['owner']=='alpha'
        assert expected['results'][2]['units'][0]['owner'] is None
        assert expected['results'][4]['visible_enemy_units']
        assert not expected['results'][6]['visible_enemy_units']
        preserved=copy.deepcopy(actual)
        n.reset(initial)
        assert json.loads(n.execute_actions_json(json.dumps(operations)))['results']==expected['results']
        n.close();assert actual==preserved
    finally:n.close();serial.close();world.reset()
