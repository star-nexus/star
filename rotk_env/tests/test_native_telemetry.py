"""System telemetry, trusted connection metadata and complete settlement counters."""
from copy import deepcopy
import json
import pytest

pytest.importorskip('star_native')
from rotk_env import components as c
from rotk_env.runtime.bootstrap import export_initial_state
from rotk_env.runtime.native import RustRuntime, ActionRequest
from rotk_env.systems.llm_system import LLMSystem
from rotk_env.tests.test_native_vision import make_vision_world
from rotk_env.tests.test_native_request_batch import frozen


@pytest.fixture
def pair(frozen):
    world, ids, vision = make_vision_world('none')
    llm = LLMSystem(); world.add_system(llm)
    with RustRuntime(export_initial_state(world)) as runtime:
        index = [0]
        def call(agent, action, params, *, connections=0):
            llm.client.connected_agents = {str(n): {} for n in range(connections)}
            expected = llm._process_action_request(agent_id=agent, action_id=index[0], action=action,
                                                   params=deepcopy(params), send_response=False)
            actual = runtime.execute_action(action, deepcopy(params), agent_id=agent, connected_agents=connections)
            assert actual == json.loads(json.dumps(expected)), (action, params, actual, expected)
            assert runtime.export_state() == export_initial_state(world), (action, params)
            index[0] += 1
            return actual
        for agent, faction in [('a','wei'), ('b','wei'), ('c','shu')]:
            call(agent, 'register_agent_info', dict(faction=faction, provider='synthetic', model_id=agent, base_url='https://host/v1'))
        yield world, runtime, call
    world.reset()


def test_multiple_same_faction_reports_accumulate_and_completion_counts_factions(pair, frozen):
    world, runtime, call = pair
    payload = dict(faction='wei', api_stats=dict(total_calls=3, successful_calls=2, failed_calls=1,
        prompt_tokens=101, completion_tokens=12, reasoning_tokens=5, prompt_cache_hit_tokens=33,
        prompt_cache_miss_tokens=68, success_rate=66.666, cache_hit_rate=32.67),
        provider='one', model_id='model-A', toolcall_error_total=2, http_error_total=1, spatial_awareness_error=4)
    call('a','report_llm_stats',payload)
    stats = world.get_singleton_component(c.GameStats)
    assert stats.received_llm_stats_count == 1 and stats.expected_llm_stats_count == 2
    assert not stats.can_generate_settlement_report
    frozen[0] += .2
    call('b','report_llm_stats',{**payload, 'provider':'two', 'model_id':'model-B'})
    assert stats.received_llm_stats_count == 1
    call('a','report_llm_stats',{**payload, 'faction':'shu'})  # authenticated faction wins
    call('c','report_llm_stats',{**payload, 'faction':'shu'})
    assert stats.can_generate_settlement_report and stats.received_llm_stats_count == 2
    call('a','report_llm_stats',payload)  # Legacy duplicate reports accumulate too.
    call('a','retrieve_game_status',{'connected_agents':999},connections=3)
    call('a','retrieve_game_status',{},connections=0)  # Registered != connected.


@pytest.mark.parametrize('value', [None, False, True, '', ' 12 ', '1_000', '1.5', 'bad', [], [1], {}, 2.75, -3, 2**53+1])
def test_counter_coercion_on_second_report_matches_legacy(pair, value):
    world, runtime, call = pair
    params=dict(faction='wei',api_stats={key:value for key in ('total_calls','successful_calls','failed_calls',
        'prompt_tokens','completion_tokens','reasoning_tokens','prompt_cache_hit_tokens','prompt_cache_miss_tokens')},
        toolcall_error_total=value, http_error_total=value, spatial_awareness_error=value)
    call('a','report_llm_stats',params)
    call('b','report_llm_stats',dict(faction='wei',api_stats=dict(total_calls=2,successful_calls=1,prompt_tokens=3)))


@pytest.mark.parametrize('action,params', [
    ('report_llm_stats',{}), ('report_llm_stats',{'faction':None}),
    ('report_llm_stats',{'faction':'invalid'}), ('report_llm_stats',{'faction':['wei']}),
    *[('report_llm_stats',dict(faction='wei',api_stats=v)) for v in (None,[],False,'invalid')],
    ('strategy_ping',{}), ('strategy_ping',{'faction':'invalid'}),
    *[('strategy_ping',dict(faction='wei',score=v)) for v in (None,[],{},'invalid',0,-1,1.1,'nan','inf',True,' .1_25 ')],
])
def test_telemetry_validation_precedence_and_errors(pair, action, params):
    _, _, call = pair
    call('missing',action,params)
    call('a',action,params)


def test_strategy_throttle_cap_wall_clock_rounding_and_unicode_evidence(pair, frozen):
    _, runtime, call = pair
    base = frozen[0]
    for offset in (0, 1, 2, 4, 6, 8, 10, 12, -2, 69, 70, 72):
        frozen[0] = base + offset
        call('a','strategy_ping',dict(faction='wei',score='0.12345', evidence='合作⚔️'*40))
    for i in range(13):
        frozen[0] += 61
        call('b','strategy_ping',dict(faction='wei',score=.99995,evidence=f'plan {i}'))
    evidence=runtime.export_state()['singletons']['GameStats']['strategy_evidence']['wei']
    assert len(evidence) == 10 and evidence[-1] == 'plan 12'


@pytest.mark.parametrize('threads',[1,2,4])
def test_telemetry_batch_and_reset_preserve_order(threads, frozen):
    world, _, _ = make_vision_world('none'); world.add_system(LLMSystem())
    initial=export_initial_state(world)
    requests=[ActionRequest('a','register_agent_info',dict(faction='wei',provider='fake',model_id='m',base_url='https://host/v1')),
        ActionRequest('a','strategy_ping',dict(faction='wei',score=.25)),
        ActionRequest('a','report_llm_stats',dict(faction='wei',api_stats={'total_calls':3})),
        ActionRequest('a','retrieve_game_status',{},connected_agents=5),
        ActionRequest('a','get_faction_state',dict(faction='wei'))]
    try:
        with RustRuntime(initial,threads=threads) as single, RustRuntime(initial,threads=threads) as batch:
            expected=[single.execute_action(r.action,r.parameters,agent_id=r.agent_id,connected_agents=r.connected_agents) for r in requests]
            assert batch.execute_actions(requests) == expected
            assert batch.export_state() == single.export_state()
            state=batch.export_state(); batch.reset(state)
            assert batch.export_state() == state
            batch.reset(initial)
            assert batch.execute_actions(requests) == expected
    finally:
        world.reset()


@pytest.mark.parametrize('count',[-1,True,1.5,'3',2**64])
def test_transport_count_rejected_before_any_action(count, pair):
    _, runtime, _ = pair
    before=runtime.export_state()
    with pytest.raises(ValueError,match='transport count'):
        runtime.execute_action('retrieve_game_status',{},agent_id='a',connected_agents=count)
    assert runtime.export_state() == before


@pytest.mark.parametrize('value',[2**64-1, 10**100, 10**400, -10**400, '9'*500, 1e100])
def test_large_counters_remain_exact_and_percentages_match_integer_division(pair, value):
    _, _, call = pair
    payload=dict(faction='wei',api_stats={key:value for key in ('total_calls','successful_calls','prompt_tokens','prompt_cache_hit_tokens')})
    call('a','report_llm_stats',payload)
    call('b','report_llm_stats',dict(faction='wei',api_stats={}))


@pytest.mark.parametrize('numerator,denominator',[(107,4000),(2675,100000),(1,2**1074),(1,2**1075),
    (10**400,3),(-10**400,3),(10**308,1),(2**53+1,2**53-1)])
def test_percentage_rounding_underflow_and_overflow_match_python(pair,numerator,denominator):
    _, _, call = pair
    payload=dict(faction='wei',api_stats=dict(total_calls=denominator,successful_calls=numerator))
    call('a','report_llm_stats',payload)
    call('b','report_llm_stats',dict(faction='wei',api_stats={}))


@pytest.mark.parametrize('registered,connected,received',[
    ([],[],[]),([],['unregistered'],[]),(['a'],[],[]),(['a'],['a'],[]),
    (['a','b','c'],['c','unknown','b','a'],['a']),
    (['a','b','c'],['b'],['a','c']),
])
def test_game_end_collection_and_notification_plan_match_offline_python(registered,connected,received,frozen,monkeypatch):
    from rotk_env.prefabs.config import Faction
    world,_,_=make_vision_world('none')
    llm=LLMSystem();world.add_system(llm)
    try:
        for agent in registered:
            faction='shu' if agent=='c' else 'wei'
            result=llm._process_action_request(agent_id=agent,action_id=0,action='register_agent_info',
                params=dict(faction=faction,provider='synthetic',model_id=agent,base_url='https://host/v1'),send_response=False)
            assert result['success']
        for agent in received:
            result=llm._process_action_request(agent_id=agent,action_id=1,action='report_llm_stats',
                params=dict(faction='shu' if agent=='c' else 'wei',api_stats={}),send_response=False)
            assert result['success']
        state=world.get_singleton_component(c.GameState);state.game_over=True;state.winner=Faction.WEI
        llm.client.connected_agents={agent:{} for agent in connected}
        sent=[]
        monkeypatch.setattr(llm,'send_message',lambda payload,*,target:sent.append(dict(payload=payload,target=target)))
        with RustRuntime(export_initial_state(world)) as runtime:
            count=llm.notify_game_end_to_all_agents(winner=state.winner,reason='game_completed')
            plan=runtime.prepare_game_end(connected,expected_epoch=1)
            assert count==len(plan['targets'])
            assert sent==[dict(payload=plan['notification'],target=dict(type='agent',id=aid)) for aid in plan['targets']]
            assert runtime.export_state()==export_initial_state(world)
            old=runtime.export_state()
            for ids,wall,epoch in [(['a','a'],frozen[0],1),([],float('nan'),1),([],frozen[0],2)]:
                with pytest.raises(RuntimeError):runtime.prepare_game_end(ids,wall_time=wall,expected_epoch=epoch)
                assert runtime.export_state()==old
            runtime.reset(old)
            with pytest.raises(RuntimeError,match='epoch'):
                runtime.prepare_game_end(connected,expected_epoch=1)
    finally:
        world.reset()


def test_game_end_plan_rejects_running_world_before_writes(pair):
    _,runtime,_=pair
    before=runtime.export_state()
    with pytest.raises(RuntimeError,match='has not ended'):
        runtime.prepare_game_end([])
    assert runtime.export_state()==before


# CPython 3.13 is the normalized oracle. Enumerate its decimal scripts so every
# accepted digit (not only the motivating fullwidth example) crosses the API.
import unicodedata
_DECIMAL_ZERO = [i for i in range(0x110000)
                 if unicodedata.category(chr(i)) == 'Nd' and unicodedata.decimal(chr(i)) == 0]


@pytest.mark.parametrize('zero', _DECIMAL_ZERO)
def test_unicode_decimal_stats_and_strategy_match_python(zero,pair,frozen):
    _,_,call=pair
    digits=''.join(chr(zero+i) for i in range(10))
    call('a','report_llm_stats',dict(faction='wei',api_stats=dict(total_calls=digits,successful_calls=1)))
    call('a','report_llm_stats',dict(faction='wei',api_stats=dict(total_calls=2,successful_calls=1)))
    for digit in digits:
        frozen[0]+=61
        call('a','strategy_ping',dict(faction='wei',score='0.1'+digit))


@pytest.mark.parametrize('value',['\u3000１２_３\u00a0','＋１２','¹','①','１２__３','１２_','_１２','\x1c１２','١٢.٥'])
def test_unicode_numeric_spacing_separators_and_rejected_symbols(value,pair,frozen):
    _,_,call=pair
    call('a','report_llm_stats',dict(faction='wei',api_stats=dict(total_calls=value,successful_calls=1)))
    call('a','report_llm_stats',dict(faction='wei',api_stats=dict(total_calls=2,successful_calls=1)))
    call('a','strategy_ping',dict(faction='wei',score=value))
