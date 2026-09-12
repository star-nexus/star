"""Trusted public requests: shared reads never cross writes or leak ownership."""
import datetime
import json
import time
import pytest
pytest.importorskip('star_native')
from rotk_env.components import Combat, UnitCount
from rotk_env.runtime.bootstrap import export_initial_state
from rotk_env.runtime.native import ActionRequest, RustRuntime
from rotk_env.systems.llm_system import LLMSystem
from rotk_env.tests.test_native_vision import make_vision_world


@pytest.fixture
def frozen(monkeypatch):
    now = [1720000000.]
    monkeypatch.setattr(time, 'time', lambda: now[0])
    class Frozen(datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 9, 12, 12)
    monkeypatch.setattr(datetime, 'datetime', Frozen)
    return now


@pytest.mark.parametrize('display', ['none', 'dummy', 'window'])
@pytest.mark.parametrize('threads', [1, 2, 4])
def test_public_batch_matches_sequential_python_and_native(display, threads, frozen):
    world, (a, b, c), vision = make_vision_world(display)
    world.get_component(a, Combat).attack_range = 5
    world.get_component(c, UnitCount).current_count = 1
    llm = LLMSystem(); world.add_system(llm)
    initial = export_initial_state(world, display=display)
    reg = dict(faction='wei', provider='synthetic', model_id='fake', base_url='https://host/v1/?key=removed')
    actions = [
        ('new', 'get_faction_state', {'faction': 'wei'}),
        ('alpha', 'register_agent_info', reg),
        ('beta', 'register_agent_info', reg),
        ('enemy', 'register_agent_info', {**reg, 'faction': 'shu'}),
        ('alpha', 'claim_units', {'unit_ids': [a]}),
        ('alpha', 'get_faction_state', {'faction': 'wei'}),
        ('enemy', 'get_faction_state', {'faction': 'shu'}),
        ('beta', 'get_faction_state', {'faction': 'wei', 'unit_ids': [b, a, b], 'agent_id': 'alpha'}),
        ('beta', 'get_faction_state', {'faction': 'shu'}),
        ('beta', 'get_faction_state', {'faction': 'wei', 'unit_ids': []}),
        ('alpha', 'move', {'unit_id': a, 'target_position': {'col': -2, 'row': 0}}),
        ('alpha', 'get_faction_state', {'faction': 'wei'}),
        ('beta', 'get_faction_state', {'faction': 'wei'}),
        ('beta', 'claim_units', {'unit_ids': [a], 'exclusive': False}),
        ('alpha', 'get_faction_state', {'faction': 'wei', 'unit_ids': [a]}),
        ('beta', 'get_faction_state', {'faction': 'wei', 'unit_ids': [a]}),
        # Legacy release can write a prefix before a malformed later element fails.
        ('beta', 'release_units', {'unit_ids': [a, {}]}),
        ('alpha', 'get_faction_state', {'faction': 'wei', 'unit_ids': [a]}),
        ('beta', 'get_faction_state', {'faction': 'wei', 'unit_ids': [a]}),
    ]
    if display == 'none':
        actions += [('beta', 'attack', {'unit_id': a, 'target_id': c}),
                    ('beta', 'get_faction_state', {'faction': 'wei'})]
    requests = [ActionRequest(agent, action, params, frozen[0] + index, '2026-09-12T12:00:00')
                for index, (agent, action, params) in enumerate(actions)]
    try:
        expected = []
        with RustRuntime(initial, threads=threads) as single, RustRuntime(initial, threads=threads) as batch:
            for index, request in enumerate(requests):
                frozen[0] = request.wall_time
                result = llm._process_action_request(agent_id=request.agent_id, action_id=index,
                    action=request.action, params=dict(request.parameters), send_response=False)
                result = json.loads(json.dumps(result))
                expected.append(result)
                assert single.execute_action(request.action, request.parameters, agent_id=request.agent_id,
                    wall_time=request.wall_time, registration_time=request.registration_time) == result
                assert single.export_state() == export_initial_state(world, display=display), index
            report = batch.execute_actions_diagnostic(requests)
            assert report['results'] == expected
            assert batch.export_state() == single.export_state()
            shared = report['observation_segments'][1]
            assert (shared['start'], shared['end']) == (5, 10)
            assert shared['metrics']['census_builds'] == 1
            assert shared['metrics']['faction_builds'] == 2
            assert shared['metrics']['panel_builds'] == 3
            assert report['observation_segments'][0]['metrics']['census_builds'] == 0
            assert report['results'][7]['units'][1]['commandable'] is False
            assert report['results'][14]['units'][0]['commandable'] is False
            assert report['results'][15]['units'][0]['commandable'] is True
            assert report['results'][16]['error_code'] == 2012
            assert report['results'][17]['units'][0]['owner'] is None
            assert report['results'][17]['units'][0]['commandable'] is True
            if display == 'none':
                assert report['results'][5]['units'][0]['position'] != report['results'][11]['units'][0]['position']
                assert report['results'][11]['visible_enemy_units'] and not report['results'][-1]['visible_enemy_units']
            # Returned trees do not alias cached facts, including after a reset.
            report['results'][5]['units'][0]['owner'] = 'modified locally'
            assert report['results'][11]['units'][0]['owner'] == 'alpha'
            batch.reset(initial)
            assert batch.get_faction_state('wei', agent_id='alpha')['error_code'] == 2005
            assert report['results'][11]['units'][0]['owner'] == 'alpha'
            assert batch.execute_actions([]) == []
    finally:
        world.reset()


def test_public_parameters_are_detached_and_envelope_errors_are_atomic(frozen):
    world, (a, b, c), vision = make_vision_world('none')
    initial = export_initial_state(world)
    try:
        with RustRuntime(initial) as runtime:
            reg = dict(faction='wei', provider='synthetic', model_id='fake', base_url='https://host', agent_id='spoof')
            before = runtime.export_state()
            with pytest.raises(TypeError, match='normalized dictionary'):
                runtime.execute_actions([ActionRequest('a', 'register_agent_info', reg), ActionRequest('a', 'move', [])])
            assert runtime.export_state() == before
            with pytest.raises(ValueError):
                runtime.execute_actions([ActionRequest('a', 'register_agent_info', reg), ActionRequest('a', 'move', {}, float('nan'))])
            assert runtime.export_state() == before
            assert runtime.execute_action('register_agent_info', reg, agent_id='a')['success']
            assert reg['agent_id'] == 'spoof'
            assert runtime.get_faction_state('wei', agent_id='a', unit_ids=[])['units'] == []
            assert not runtime.get_faction_state('wei', agent_id='a', unit_ids=None)['success']
            runtime.close()
            with pytest.raises(RuntimeError, match='closed'):
                runtime.get_faction_state('wei', agent_id='a')
    finally:
        world.reset()
