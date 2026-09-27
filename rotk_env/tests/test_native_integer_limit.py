"""Accepted telemetry must preserve the host's int(string) failure fallback."""
import sys
import pytest

pytest.importorskip('star_native')
from rotk_env.runtime.native import ActionRequest
from rotk_env.systems.llm_system import _LLM_STATS_ADD_KEYS
from rotk_env.tests.test_native_telemetry import pair
from rotk_env.tests.test_native_request_batch import frozen


@pytest.fixture
def digit_limit():
    previous = sys.get_int_max_str_digits()
    try:
        yield sys.set_int_max_str_digits
    finally:
        sys.set_int_max_str_digits(previous)


def report(value):
    params = dict(faction='wei', api_stats={k:value for k in _LLM_STATS_ADD_KEYS},
                  toolcall_error_total=value, http_error_total=value, spatial_awareness_error=value)
    # An Agent parameter cannot override trusted interpreter metadata.
    params['integer_string_limit'] = 0
    return params


@pytest.mark.parametrize('digits', [4299, 4300, 4301])
@pytest.mark.parametrize('style', ['ascii', 'unicode', 'separators', 'signed'])
def test_default_decimal_boundary_matches_complete_response_and_state(pair, digit_limit, digits, style):
    digit_limit(4300)
    text = '0' * (digits - 1) + '1'
    if style == 'unicode': text = text.translate(str.maketrans('01', '０１'))
    if style == 'separators': text = '_'.join(text)
    if style == 'signed': text = ' \t-' + text + '\u2003'
    _, _, call = pair
    call('a', 'report_llm_stats', report(text))
    call('b', 'report_llm_stats', report(2))


@pytest.mark.parametrize('limit,digits', [(640,639),(640,640),(640,641),(5000,5001),(0,5001)])
@pytest.mark.parametrize('batch', [False,True])
def test_nondefault_limit_reset_and_batch(pair, digit_limit, limit, digits, batch):
    from copy import deepcopy
    from rotk_env.runtime.bootstrap import export_initial_state
    from rotk_env.systems.llm_system import LLMSystem
    world, runtime, call = pair
    digit_limit(limit)
    initial = export_initial_state(world)
    requests = [ActionRequest('a','report_llm_stats',report('0'*(digits-1)+'1')),
                ActionRequest('b','report_llm_stats',report(2))]
    if batch:
        gate=next(s for s in world.systems if isinstance(s,LLMSystem))
        expected=[gate._process_action_request(agent_id=r.agent_id,action_id=i,action=r.action,params=deepcopy(r.parameters),send_response=False) for i,r in enumerate(requests)]
        assert runtime.execute_actions(requests)==expected
        assert runtime.export_state()==export_initial_state(world)
    else:
        for r in requests:call(r.agent_id,r.action,r.parameters)
    expected_state=runtime.export_state()
    runtime.reset(initial)
    assert runtime.execute_actions(requests)
    assert runtime.export_state()==expected_state


def test_limit_is_captured_when_report_is_admitted_not_when_world_is_created(pair, digit_limit):
    _, _, call = pair
    digit_limit(640)
    call('a', 'report_llm_stats', report('0'*999+'1'))  # first report stores raw text
    digit_limit(5000)
    call('b', 'report_llm_stats', report(2))  # conversion happens now


def test_integer_limit_does_not_apply_to_float_score(pair, digit_limit):
    digit_limit(640)
    _, _, call = pair
    call('a', 'strategy_ping',dict(faction='wei',score='0.'+'0'*1000+'1'))
