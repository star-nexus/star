"""Python insertion order remains significant when accepted JSON becomes text."""
from copy import deepcopy

import pytest

pytest.importorskip('star_native')
from rotk_env import components as c
from rotk_env.runtime.bootstrap import export_initial_state
from rotk_env.runtime.native import ActionRequest, RustRuntime
from rotk_env.systems.llm_system import LLMSystem
from rotk_env.tests.test_native_request_batch import frozen
from rotk_env.tests.test_native_telemetry import pair
from rotk_env.tests.test_native_vision import make_vision_world


VALUES = [
    {'z': 1, 'a': 2},
    {'魏': {'z': None, 'a': True}, 'a': [False, {'y': 'quoted\'value', 'b': 2}]},
    [{'z': [1, 2], 'a': {}}, {'β': 1.5, 'A': 'line\nnext'}],
    {'z': '战' * 130, 'a': 'after truncation'},
]


@pytest.mark.parametrize('value', VALUES)
def test_strategy_evidence_keeps_recursive_input_order(pair, value):
    world, _, call = pair
    call('a', 'strategy_ping', dict(faction='wei', score=.5, evidence=value))
    expected = str(value)
    if len(expected) > 120:
        expected = expected[:117] + '...'
    assert world.get_singleton_component(c.GameStats).strategy_evidence['wei'] == [expected]


@pytest.mark.parametrize('value', VALUES)
@pytest.mark.parametrize('restore', [False, True])
def test_stored_raw_labels_keep_order_until_second_report(pair, value, restore):
    world, runtime, call = pair
    params = dict(faction='wei', api_stats={}, provider=value, model_id=value)
    call('a', 'report_llm_stats', params)
    # The first report keeps the raw type. Conversion happens only on accumulation.
    if restore:
        runtime.reset(export_initial_state(world))
    call('b', 'report_llm_stats', dict(faction='wei', api_stats={}, provider='next', model_id='next'))


@pytest.mark.parametrize('value', VALUES)
@pytest.mark.parametrize('action', ['strategy_ping', 'report_llm_stats'])
def test_invalid_faction_feedback_keeps_mapping_order(pair, value, action):
    _, _, call = pair
    call('missing', action, dict(faction=value, score=.5, api_stats={}))


@pytest.mark.parametrize('threads', [1, 2, 4])
def test_batch_export_import_reset_keep_input_order_and_owned_results(threads, frozen):
    world, _, _ = make_vision_world('none')
    llm = LLMSystem(); world.add_system(llm)
    initial = export_initial_state(world)
    label = {'z': [None, {'y': 2, 'b': 1}], 'a': True}
    requests = [
        ActionRequest('a', 'register_agent_info', dict(faction='wei', provider='fake', model_id='m', base_url='http://local')),
        ActionRequest('a', 'report_llm_stats', dict(faction='wei', api_stats={}, provider=label, model_id=label)),
    ]
    followup = ActionRequest('a', 'report_llm_stats', dict(faction='wei', api_stats={}, provider='next', model_id='next'))
    try:
        expected = [llm._process_action_request(agent_id=r.agent_id, action_id=i, action=r.action,
                    params=deepcopy(r.parameters), send_response=False) for i, r in enumerate(requests)]
        with RustRuntime(initial, threads=threads) as runtime:
            assert runtime.execute_actions(requests) == expected
            snapshot = runtime.export_state()
            # Dict equality alone would miss reordering; inspect the stored label explicitly.
            assert snapshot == export_initial_state(world)
            # Roundtrip the native-owned snapshot, not just the original Python bootstrap.
            runtime.reset(snapshot)
            snapshot['singletons'].clear()  # Returned state cannot alias the authority.
            expected_next = llm._process_action_request(agent_id='a', action_id=2, action=followup.action,
                            params=deepcopy(followup.parameters), send_response=False)
            assert runtime.execute_actions([followup]) == [expected_next]
            assert runtime.export_state() == export_initial_state(world)
            runtime.reset(initial)
            assert runtime.execute_actions(requests + [followup]) == expected + [expected_next]
            assert runtime.export_state() == export_initial_state(world)
    finally:
        world.reset()
