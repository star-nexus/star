"""Encoded facts are immutable; identity and write boundaries remain per request."""
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


@pytest.mark.parametrize('display', ['none', 'dummy', 'window'])
@pytest.mark.parametrize('threads', [1, 2, 4])
def test_encoded_facts_preserve_escaping_permissions_and_independent_lifetimes(display, threads):
    world, (a,b,enemy), _ = setup(display)
    identity = '雪"\\\n\x00agent'
    world.get_singleton_component(c.GameStats).agent_id_to_faction[identity] = Faction.WEI
    team = world.get_singleton_component(c.TeamCoordination)
    team.release_units('alpha')
    team.claim_units(identity, [a])
    world.add_component(a, c.UnitSkills(available_skills={'charge', '雪"\\\n\x00{}[]'}))
    world.get_singleton_component(c.FogOfWar).enabled = False
    params = [dict(faction='wei',agent_id=identity,unit_ids=[b,a,b]),
              dict(faction='wei',agent_id='beta',unit_ids=[a]),
              dict(faction='shu',agent_id='enemy'),
              dict(faction='wei',agent_id=identity,unit_ids=[]),
              dict(faction='wei',agent_id=identity,unit_ids=[a])]
    initial = json.dumps(export_initial_state(world, display=display))
    n = NativeRuntime(initial, threads)
    try:
        raw = n._observation_probe_json(json.dumps(params))
        report = json.loads(raw)
        expected = [LLMActionHandler(world).handle_faction_state(p) for p in params]
        assert report['results'] == expected
        assert n.export_state_json() == initial or json.loads(n.export_state_json()) == json.loads(initial)
        m = report['metrics']
        assert m['public_encodes'] == 2
        assert m['panel_encodes'] == 3
        assert m['shared_public_results'] == 5
        assert m['shared_panel_results'] == 5
        assert report['results'][0]['units'][1]['owner'] == identity
        assert report['results'][1]['units'][0]['commandable'] is False
        # This decoded result must not mutate siblings or any retained Rust fact.
        report['results'][0]['visible_terrain'][0]['type'] = 'local mutation'
        report['results'][0]['units'][1]['capabilities'].clear()
        assert report['results'][4] == expected[4]
        assert json.loads(n._observation_probe_json(json.dumps(params)))['results'] == expected
        n.reset(initial); n.close()
        assert json.loads(raw)['results'] == expected
    finally:
        n.close();world.reset()


@pytest.mark.parametrize('threads', [1, 2, 4])
def test_encoded_batch_freezes_facts_before_later_death_and_permission_writes(threads):
    world, (a,b,enemy), _ = setup('none')
    world.get_singleton_component(c.FogOfWar).enabled = False
    world.get_component(a,c.Combat).attack_range=5
    world.get_component(enemy,c.UnitCount).current_count=1
    initial=json.dumps(export_initial_state(world))
    def request(agent, action, **params):
        return dict(agent_id=agent,action=action,parameters=params,wall_time=1720000000.)
    q=lambda agent='alpha':request(agent,'get_faction_state',faction='wei',unit_ids=[a])
    requests=[q(),q('beta'),request('alpha','release_units',unit_ids=[a]),
              request('beta','claim_units',unit_ids=[a]),q(),q('beta'),
              request('beta','attack',unit_id=a,target_id=enemy),q(),
              request('unregistered','get_faction_state',faction='wei'),q('beta')]
    batch=NativeRuntime(initial,threads);single=NativeRuntime(initial,threads)
    try:
        expected=[json.loads(single.execute_action_json(json.dumps(r))) for r in requests]
        report=json.loads(batch.execute_actions_json(json.dumps(requests)))
        assert report['results']==expected
        assert batch.export_state_json()==single.export_state_json()
        assert expected[0]['visible_enemy_units'] and not expected[7]['visible_enemy_units']
        assert expected[0]['units'][0]['owner']=='alpha'
        assert expected[4]['units'][0]['owner']=='beta'
        assert expected[4]['units'][0]['commandable'] is False
        assert expected[8]['error_code']==2005
        segments=report['observation_segments']
        assert [(s['start'],s['end']) for s in segments]==[(0,2),(4,6),(7,10)]
        assert all(s['metrics']['public_encodes']==s['metrics']['panel_encodes']==1 for s in segments)
        saved=copy.deepcopy(report)
        batch.reset(initial);batch.close()
        assert report==saved
    finally:
        batch.close();single.close();world.reset()
