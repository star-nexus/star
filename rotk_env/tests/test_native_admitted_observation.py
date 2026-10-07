"""Private E8 scopes preserve independent ingress, accounting and ownership."""
import json
from concurrent.futures import ThreadPoolExecutor
import pytest
from rotk_env.runtime.bootstrap import export_initial_state
from rotk_env.runtime.native import ActionRequest, RustRuntime
from rotk_env.tests.test_native_observation import setup


@pytest.fixture
def initial():
    world, ids, _ = setup('window')
    try:
        yield export_initial_state(world, display='window'), ids
    finally:
        world.reset()


def accounting(state, metadata, agent, wall_time):
    stats = state['singletons'].get('GameStats', {})
    faction = stats.get('agent_id_to_faction', {}).get(agent)
    return dict(wall_time=wall_time,epoch=metadata['epoch'],revision=metadata['revision'],
                agent=agent,registered_faction=faction,
                agent_actions=stats.get('action_counts_by_agent',{}).get(agent),
                faction_actions=stats.get('action_counts_by_faction',{}).get(faction))


@pytest.mark.parametrize('threads', [1,4])
@pytest.mark.parametrize('mode', ['segment_no_reuse','segment_encoded'])
@pytest.mark.parametrize('case', ['repeat','mixed','duplicates','empty','null','foreign','unknown','invalid','denied','unregistered','other_owner'])
def test_each_response_accounting_and_final_world(initial, threads, mode, case):
    state, (a,b,enemy) = initial
    common = dict(faction='wei',agent_id='alpha',unit_ids=[a])
    second = dict(common)
    if case == 'mixed': second.update(faction='shu',agent_id='enemy',unit_ids=[enemy])
    elif case == 'duplicates':second['unit_ids']=[b,a,b]
    elif case == 'empty':second['unit_ids']=[]
    elif case == 'null':second['unit_ids']=None
    elif case == 'foreign':second['unit_ids']=[enemy]
    elif case == 'unknown':second['unit_ids']=[999999999]
    elif case == 'invalid':second['unit_ids']='invalid'
    elif case == 'denied':second['faction']='shu'
    elif case == 'unregistered':second['agent_id']='unknown-agent'
    elif case == 'other_owner':second['agent_id']='beta'
    requests=[common,second,dict(common,unit_ids=[b]),common]
    with RustRuntime(state,threads=threads) as single, RustRuntime(state,threads=threads) as candidate:
        expected=[]; snapshots=[]
        for i,q in enumerate(requests):
            expected.append(single.get_faction_state_json(**q,wall_time=1720000000.+i))
            snapshots.append(accounting(single.export_state(),single.diagnostics(),q['agent_id'],1720000000.+i))
        with candidate._admitted_observation_segment(mode,diagnostics=True) as segment:
            actual=[segment.get_faction_state_json(**q,wall_time=1720000000.+i) for i,q in enumerate(requests)]
        assert actual==expected
        assert candidate.export_state()==single.export_state()
        # A misspelled stats key must not turn this into a null==null oracle.
        assert isinstance(snapshots[0]['agent_actions'], int)
        assert isinstance(snapshots[0]['faction_actions'], int)
        assert [x['accounting_after_request'] for x in segment.report['query_diagnostics']]==snapshots
        if case=='repeat':
            builds=[x['metrics']['census_builds'] for x in segment.report['query_diagnostics']]
            assert builds==([1,0,0,0] if mode=='segment_encoded' else [1,1,1,1])


@pytest.mark.parametrize('barrier', ['rest','read','step','reset','malformed'])
def test_native_barrier_freshness_and_owned_output(initial, barrier):
    state,(a,_,_) = initial
    q=dict(faction='wei',agent_id='alpha',unit_ids=[a],wall_time=1720000000.)
    with RustRuntime(state) as single, RustRuntime(state) as candidate:
        with candidate._admitted_observation_segment('segment_encoded') as segment:
            before=segment.get_faction_state_json(**q)
            assert before==single.get_faction_state_json(**q)
            for r in (single,candidate):
                if barrier=='rest':r.execute_action('rest',{'unit_id':a},agent_id='alpha',wall_time=1720000001.)
                elif barrier=='read':r._native.diagnostics_json()
                elif barrier=='step':r.step(1/30,wall_time=1720000001.)
                elif barrier=='reset':r.reset(state)
                else:
                    with pytest.raises(RuntimeError):r._native.execute_action_json('{')
            after=segment.get_faction_state_json(**q)
            assert after==single.get_faction_state_json(**q)
        assert candidate.export_state()==single.export_state()
        candidate.close()
        assert json.loads(before)['success'] and json.loads(after)['success']


def test_invalid_mode_limit_nested_and_exception_cleanup(initial):
    state,(a,_,_) = initial
    with RustRuntime(state) as r:
        before=r.export_state()
        for mode,limit in [('bad',4),('segment_encoded',1),('segment_encoded',True),('segment_encoded',5)]:
            with pytest.raises(ValueError):r._admitted_observation_segment(mode,max_requests=limit)
        assert r.export_state()==before
        with r._admitted_observation_segment('segment_encoded',diagnostics=True) as outer:
            outer.get_faction_state_json('wei',agent_id='alpha',unit_ids=[a],wall_time=1.)
            with pytest.raises(RuntimeError):
                with r._admitted_observation_segment('segment_encoded'):pass
            outer.get_faction_state_json('wei',agent_id='alpha',unit_ids=[a],wall_time=2.)
        assert outer.report['query_diagnostics'][1]['metrics']['census_builds']==0
        with pytest.raises(ValueError):
            with r._admitted_observation_segment('segment_encoded') as segment:
                segment.get_faction_state_json('wei',agent_id='alpha',wall_time=float('nan'))
        with r._admitted_observation_segment('segment_encoded'):pass


def test_stale_cross_instance_thread_limit_and_old_end(initial):
    state,(a,_,_) = initial
    request=json.dumps(ActionRequest('alpha','get_faction_state',{'faction':'wei','unit_ids':[a]},1.).to_wire())
    with RustRuntime(state) as first, RustRuntime(state) as second:
        n=first._native
        old=n._begin_observation_segment_json('segment_encoded',2,True)
        n._end_observation_segment_json(old)
        token=n._begin_observation_segment_json('segment_encoded',2,True)
        assert n._end_observation_segment_json(old) is None
        # Foreign token can execute only through ordinary fallback, never cache.
        second._native._observation_segment_request_json(token,request)
        assert second._native._end_observation_segment_json(token) is None
        n._observation_segment_request_json(token,request)
        n._observation_segment_request_json(token,request)
        n._observation_segment_request_json(token,request)  # limit: ordinary fallback
        assert n._end_observation_segment_json(token) is None
        token=n._begin_observation_segment_json('segment_encoded',2,True)
        with ThreadPoolExecutor(max_workers=1) as pool:
            assert json.loads(pool.submit(n._observation_segment_request_json,token,request).result())['success']
        assert n._end_observation_segment_json(token) is None
        token=n._begin_observation_segment_json('segment_encoded',2,False)
        with pytest.raises(RuntimeError):n._observation_segment_request_json(token,'{')
        assert n._end_observation_segment_json(token) is None


def test_custom_write_spec_falls_back_and_error_success_prefix(initial):
    state,(a,_,_) = initial
    state['interface']['action_specs']['get_faction_state']['kind']='write'
    with RustRuntime(state) as single, RustRuntime(state) as candidate:
        with candidate._admitted_observation_segment('segment_encoded') as segment:
            assert segment.token is None
            for wall in (1.,2.):
                q=dict(faction='wei',agent_id='alpha',unit_ids=[a],wall_time=wall)
                assert segment.get_faction_state_json(**q)==single.get_faction_state_json(**q)
        assert candidate.export_state()==single.export_state()
        assert candidate.diagnostics()['revision']==single.diagnostics()['revision']


def test_malformed_later_request_preserves_prior_commit_and_close(initial):
    state,(a,_,_) = initial
    with RustRuntime(state) as single, RustRuntime(state) as candidate:
        q=dict(faction='wei',agent_id='alpha',unit_ids=[a],wall_time=1.)
        with candidate._admitted_observation_segment('segment_encoded') as segment:
            before=segment.get_faction_state_json(**q)
            assert before==single.get_faction_state_json(**q)
            with pytest.raises(RuntimeError):candidate._native._observation_segment_request_json(segment.token,'{')
        assert candidate.export_state()==single.export_state()
        with candidate._admitted_observation_segment('segment_encoded') as segment:
            segment.get_faction_state_json(**q)
            candidate.close()
        assert json.loads(before)['success']
