"""Display bytes attach to authorized native projections at the request boundary."""
import base64
import builtins
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import io
import json
from threading import Event

import pygame
import pytest

pytest.importorskip('star_native')
from framework.engine import frame_capture
from framework.engine.renders import RenderEngine
from rotk_env import components as c
from rotk_env.prefabs.config import GameMode
from rotk_env.runtime.bootstrap import export_initial_state
from rotk_env.runtime.native import ActionRequest, RustRuntime
from rotk_env.systems.llm_system import LLMSystem
from rotk_env.tests.test_native_request_batch import frozen
from rotk_env.tests.test_native_vision import make_vision_world

VLM = 'get_faction_state_vlm'
REG = dict(faction='wei', provider='synthetic', model_id='fake', base_url='http://local')


def make(display='none', mode='real_time', enabled=True):
    world, ids, _ = make_vision_world(display)
    world.get_singleton_component(c.GameTime).current_mode = GameMode(mode)
    world.get_singleton_component(c.GameModeComponent).mode = GameMode(mode)
    if enabled:
        world.add_singleton_component(c.MatchRules(game_actions=('move', 'attack', 'get_faction_state', VLM)))
    llm = LLMSystem(); world.add_system(llm)
    return world, ids, llm


def python_call(llm, agent, action, params):
    return json.loads(json.dumps(llm._process_action_request(agent_id=agent, action_id=0,
                    action=action, params=deepcopy(params), send_response=False)))


@pytest.fixture
def screen(monkeypatch):
    screen = pygame.Surface((13, 7))
    screen.fill((18, 90, 147)); screen.set_at((3, 4), (251, 2, 67))
    monkeypatch.setattr(RenderEngine(), '_screen', screen)
    return screen


@pytest.mark.parametrize('mode', ['real_time', 'turn_based'])
@pytest.mark.parametrize('display', ['none', 'dummy', 'window'])
@pytest.mark.parametrize('threads', [1, 2, 4])
def test_vlm_permissions_filters_bytes_and_reset_match_python(mode, display, threads, screen, frozen):
    world, (a, b, _), llm = make(display, mode)
    initial = export_initial_state(world, display=display)
    requests = [
        ('missing', VLM, {'faction': 'wei'}),
        ('a', 'register_agent_info', REG), ('b', 'register_agent_info', REG),
        ('a', 'claim_units', {'unit_ids': [a]}),
        ('a', VLM, {'faction': 'shu'}), ('a', VLM, {'faction': 'invalid'}),
        ('a', VLM, {'faction': 'wei', 'unit_ids': 'bad'}),
        ('b', VLM, {'faction': 'wei', 'unit_ids': [b, a, b], 'agent_id': 'a'}),
        ('a', VLM, {'faction': 'wei', 'unit_ids': []}),
        ('a', VLM, {'faction': 'wei'}),
    ]
    try:
        with RustRuntime(initial, threads=threads) as runtime:
            expected = []
            for agent, action, params in requests:
                answer = python_call(llm, agent, action, params); expected.append(answer)
                assert runtime.execute_action(action, deepcopy(params), agent_id=agent) == answer
                assert runtime.export_state() == export_initial_state(world, display=display)
            payload = expected[-1]
            data = base64.b64decode(payload['frame_base64'])
            assert payload['frame_format'] == 'png'  # Preserved legacy mislabel, not a new encoding claim.
            assert not data.startswith(b'\x89PNG\r\n\x1a\n')
            decoded = pygame.image.load(io.BytesIO(data), 'frame.tga')
            assert decoded.get_size() == screen.get_size()
            assert pygame.image.tobytes(decoded, 'RGB') == pygame.image.tobytes(screen, 'RGB')
            runtime.reset(initial)
            assert runtime.execute_actions([ActionRequest(agent, action, params) for agent, action, params in requests]) == expected
            assert runtime.export_state() == export_initial_state(world, display=display)
    finally:
        world.reset()


@pytest.mark.parametrize('enabled,agent,params', [
    (False, 'a', {'faction': 'wei'}), (True, 'missing', {'faction': 'wei'}),
    (True, 'a', {'faction': 'shu'}), (True, 'a', {'faction': 'invalid'}),
    (True, 'a', {'faction': 'wei', 'unit_ids': 'bad'}),
])
def test_rejected_vlm_never_reads_display(enabled, agent, params, monkeypatch, frozen):
    world, _, llm = make(enabled=enabled)
    monkeypatch.setattr(frame_capture, 'capture_rendered_frame', lambda: pytest.fail('unauthorized capture'))
    try:
        with RustRuntime(export_initial_state(world)) as runtime:
            assert runtime.execute_action('register_agent_info', REG, agent_id='a') == python_call(llm, 'a', 'register_agent_info', REG)
            expected = python_call(llm, agent, VLM, params)
            assert not expected['success']
            assert runtime.execute_action(VLM, params, agent_id=agent) == expected
            assert runtime.export_state() == export_initial_state(world)
    finally:
        world.reset()


@pytest.mark.parametrize('failure', ['imports', 'screen', 'copy', 'encode'])
def test_capture_error_keeps_successful_state_and_legacy_message(failure, monkeypatch, frozen, screen):
    world, _, llm = make()
    if failure == 'imports':
        original = builtins.__import__
        def importing(name, *args, **kwargs):
            if name == 'pygame':
                raise ImportError('injected')
            return original(name, *args, **kwargs)
        monkeypatch.setattr(builtins, '__import__', importing)
    elif failure == 'screen':
        monkeypatch.setattr(RenderEngine(), '_screen', None)
    elif failure == 'copy':
        class Broken:
            def copy(self): raise RuntimeError('injected')
        monkeypatch.setattr(RenderEngine(), '_screen', Broken())
    else:
        def broken(*args): raise RuntimeError('injected')
        monkeypatch.setattr(pygame.image, 'save', broken)
    try:
        with RustRuntime(export_initial_state(world)) as runtime:
            runtime.execute_action('register_agent_info', REG, agent_id='a'); python_call(llm, 'a', 'register_agent_info', REG)
            expected = python_call(llm, 'a', VLM, {'faction': 'wei'})
            actual = runtime.execute_action(VLM, {'faction': 'wei'}, agent_id='a')
            assert actual == expected and actual['success']
            assert actual['frame_base64'] is None and actual['frame_format'] is None
            assert actual['frame_error']
            assert runtime.export_state() == export_initial_state(world)
    finally:
        world.reset()


@pytest.mark.parametrize('threads', [1, 2, 4])
def test_mixed_batch_captures_before_later_actions_and_preserves_read_segments(threads, monkeypatch, screen, frozen):
    world, (a, b, _), llm = make()
    initial = export_initial_state(world)
    requests = [ActionRequest('a', 'register_agent_info', REG),
        ActionRequest('a', 'move', {'unit_id': a, 'target_position': {'col': -2, 'row': 0}}),
        ActionRequest('a', 'get_faction_state', {'faction': 'wei'}),
        ActionRequest('a', VLM, {'faction': 'wei'}),
        ActionRequest('a', 'move', {'unit_id': b, 'target_position': {'col': -1, 'row': 1}}),
        ActionRequest('a', VLM, {'faction': 'wei'}),
        ActionRequest('a', 'get_faction_state', {'faction': 'wei'}),
        ActionRequest('a', 'get_faction_state', {'faction': 'wei'})]
    try:
        expected=[];states=[]
        for req in requests:
            expected.append(python_call(llm, req.agent_id, req.action, req.parameters))
            if req.action == VLM:states.append(export_initial_state(world)['entities'])
        with RustRuntime(initial, threads=threads) as runtime:
            captured=[];capture=frame_capture.capture_rendered_frame
            def record():
                captured.append(runtime.export_state()['entities'])
                # A caller may mutate its later request while image capture yields.
                # The already-admitted batch must keep the original wire snapshot.
                requests[4].parameters['target_position']['col'] = 999
                return capture()
            monkeypatch.setattr(frame_capture, 'capture_rendered_frame', record)
            report=runtime.execute_actions_diagnostic(requests)
            assert report['results'] == expected
            assert captured == states and captured[0] != captured[1]
            assert [(s['start'],s['end']) for s in report['observation_segments']] == [(2,3),(6,8)]
            assert report['observation_segments'][-1]['metrics']['census_builds'] == 1
            assert runtime.export_state() == export_initial_state(world)
    finally:
        world.reset()


@pytest.mark.parametrize('bad', [ActionRequest('a', 7, {}), ActionRequest(7, 'move', {}),
    ActionRequest('a', VLM, {}, wall_time=float('nan')), ActionRequest('a', VLM, {}, wall_time=10**400)])
def test_vlm_split_does_not_execute_prefix_of_invalid_envelopes(bad, frozen):
    world, _, _ = make()
    try:
        with RustRuntime(export_initial_state(world)) as runtime:
            before=runtime.export_state()
            requests=[ActionRequest('a', 'register_agent_info', REG), ActionRequest('a', VLM, {'faction':'wei'}), bad]
            with pytest.raises((RuntimeError, ValueError)):
                runtime.execute_actions(requests)
            assert runtime.export_state() == before
    finally:
        world.reset()


@pytest.mark.parametrize('operation', ['step', 'reset', 'close'])
def test_other_runtime_writer_cannot_pass_a_pending_capture(operation, monkeypatch, frozen):
    world, _, _ = make();initial=export_initial_state(world)
    entered=Event();release=Event();started=Event();finished=Event()
    runtime=RustRuntime(initial)
    try:
        runtime.execute_action('register_agent_info', REG, agent_id='a')
        def capture():
            entered.set()
            assert release.wait(5)
            return None, 'injected frame error'
        def mutate():
            started.set()
            if operation=='step':runtime.step(1/30, wall_time=frozen[0])
            elif operation=='reset':runtime.reset(initial)
            else:runtime.close()
            finished.set()
        monkeypatch.setattr(frame_capture, 'capture_rendered_frame', capture)
        with ThreadPoolExecutor(max_workers=2) as pool:
            query=pool.submit(runtime.execute_action,VLM,{'faction':'wei'},agent_id='a')
            assert entered.wait(5)
            writer=pool.submit(mutate)
            try:
                assert started.wait(5)
                assert not finished.wait(.05)
            finally:
                release.set()
            assert query.result(timeout=5)['frame_error']=='injected frame error'
            writer.result(timeout=5)
        assert finished.is_set()
    finally:
        release.set();runtime.close();world.reset()


def test_plain_queries_do_not_import_or_capture_display(monkeypatch, frozen):
    world, _, _ = make()
    monkeypatch.setattr(frame_capture,'capture_rendered_frame',lambda:pytest.fail('plain query captured a frame'))
    try:
        with RustRuntime(export_initial_state(world)) as runtime:
            runtime.execute_action('register_agent_info',REG,agent_id='a')
            assert runtime.get_faction_state('wei',agent_id='a')['success']
            assert runtime.execute_actions([ActionRequest('a','get_faction_state',{'faction':'wei'})])[0]['success']
            runtime.close()
            with pytest.raises(RuntimeError,match='closed'):
                runtime.execute_action(VLM,{'faction':'wei'},agent_id='a')
    finally:
        world.reset()
