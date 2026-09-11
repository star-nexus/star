"""Native stage gates. Run with the optional native package installed."""
import copy
import json
import random
import sys
import threading
import time

import pytest

pytest.importorskip('star_native')
from star_native import NativeRuntime
from rotk_env.runtime.bootstrap import export_initial_state, prepare_scene, rng_state
from rotk_env.runtime.native import RustRuntime
from rotk_env.components import GameTime
from rotk_env.components.rng import _derive_domain_seed
from rotk_env.prefabs.world_builder import build_skirmish_world


@pytest.fixture
def initial():
    return prepare_scene(mode='real_time', scenario='chibi-small', seed=42, display='none', hub_url=None)


def test_initial_state_is_owned_and_matches_python(initial):
    reference = copy.deepcopy(initial)
    with RustRuntime(initial) as r:
        assert r.export_state() == reference
        initial['entities'].clear()
        initial['singletons']['GameTime']['game_elapsed_time'] = 123
        assert r.export_state() == reference
        delta = r.take_presentation_delta()
        assert len(delta['units']) == 10
        assert r.take_presentation_delta()['units'] == []
        r.reset(reference)
        assert r.export_state() == reference
        assert r.diagnostics()['epoch'] == 2
        assert delta['epoch'] == 1 and len(delta['units']) == 10
        assert r.take_presentation_delta()['epoch'] == 2
    r.close()
    for fn in (r.export_state, r.take_presentation_delta, lambda: r.step(0.1), lambda: r.reset(reference)):
        with pytest.raises(RuntimeError, match='closed'):
            fn()


@pytest.mark.parametrize('mode', ['real_time', 'turn_based'])
@pytest.mark.parametrize('fps', [24, 30])
def test_clock_matches_python_with_pause_and_time_scale(mode, fps):
    world = build_skirmish_world(mode=mode, scenario='chibi-small', seed=42, display='none')
    try:
        c = world.get_singleton_component(GameTime)
        with RustRuntime(export_initial_state(world)) as r:
            for paused, scale in [(False, 1.0), (True, 1.0), (False, 0.5), (False, 2.0)]:
                c.paused, c.time_scale = paused, scale
                r.set_clock(paused=paused, time_scale=scale)
                for _ in range(fps * 2):
                    c.update(1 / fps)
                    r.step(1 / fps, wall_time=c.last_update_time)
                    assert r.export_state()['singletons']['GameTime'] == export_initial_state(world)['singletons']['GameTime']
    finally:
        world.reset()


@pytest.mark.parametrize('field,value', [('schema', 99), ('oracle', 'old'), ('display', 'unknown'), ('mode', 'unknown')])
def test_reset_validation_is_atomic(initial, field, value):
    with RustRuntime(initial) as r:
        invalid = copy.deepcopy(initial)
        invalid[field] = value
        with pytest.raises(RuntimeError):
            r.reset(invalid)
        assert r.export_state() == initial
        assert r.diagnostics()['epoch'] == 1


def test_duplicate_ids_clock_and_unknown_fields_are_rejected(initial):
    for edit in [lambda s: s['entities'].append(s['entities'][0]),
                 lambda s: s.update(extra=True),
                 lambda s: s['clock'].update(elapsed=99),
                 lambda s: s['clock'].update(time_scale=-1)]:
        data = copy.deepcopy(initial)
        edit(data)
        with pytest.raises(ValueError):
            NativeRuntime(json.dumps(data))
    for threads in [0, 3, 8]:
        with pytest.raises(ValueError, match='threads'):
            NativeRuntime(json.dumps(initial), threads)
    with RustRuntime(initial) as r:
        for dt in [-1, float('nan'), float('inf')]:
            with pytest.raises(RuntimeError):
                r.step(dt)
            assert r.export_state() == initial
        with pytest.raises(RuntimeError):
            r.step(0.1, wall_time=float('nan'))
        assert r.export_state() == initial


@pytest.mark.parametrize('seed', [0, 42, -42, 2**64-1, 2**200+17])
@pytest.mark.parametrize('domain', ['combat', 'events', 'map', '战斗'])
def test_native_rng_matches_cpython_across_twists_and_rejection(seed, domain, initial):
    initial['seed'] = str(seed)
    initial['rng'] = {}
    py = random.Random(_derive_domain_seed(seed, domain))
    ops, expected = [], []
    for i in range(1400):
        if i % 7 == 0:
            bits = [0, 1, 31, 32, 33, 63, 64][i // 7 % 7]
            ops.append({'kind': 'bits', 'bits': bits})
            expected.append(py.getrandbits(bits))
        elif i % 7 == 1:
            ops.append({'kind': 'randint', 'lo': 1, 'hi': 20})
            expected.append(py.randint(1, 20))
        elif i % 7 == 2:
            n = [1, 2, 3, 2**31, 2**63, 2**64-1][i // 7 % 6]
            ops.append({'kind': 'randbelow', 'n': n})
            expected.append(py.randrange(n))
        elif i % 7 == 3:
            ops.append({'kind': 'uniform', 'lo': -10., 'hi': 30.})
            expected.append(py.uniform(-10., 30.))
        elif i % 7 == 4:
            values = list(range(11))
            ops.append({'kind': 'shuffle', 'values': values.copy()})
            py.shuffle(values)
            expected.append(values)
        else:
            ops.append({'kind': 'random'})
            expected.append(py.random())
    native = NativeRuntime(json.dumps(initial))
    try:
        result = json.loads(native._rng_probe_json(domain, json.dumps(ops)))
        assert result['results'] == expected
        assert result['state'] == rng_state(py)
        exported = json.loads(native.export_state_json())
        restored = NativeRuntime(json.dumps(exported))
        try:
            follow = json.loads(restored._rng_probe_json(domain, '[{"kind":"random"}]'))
            assert follow['results'] == [py.random()]
            assert follow['state'] == rng_state(py)
        finally:
            restored.close()
    finally:
        native.close()


def test_initial_advanced_rng_domain_independence_and_failed_probe(initial):
    py = random.Random(_derive_domain_seed(42, 'map'))
    py.randint(0, 2**31-1)  # MapSystem's initialization draw is imported, not repeated.
    r = NativeRuntime(json.dumps(initial))
    try:
        assert json.loads(r._rng_probe_json('map', '[{"kind":"random"}]'))['results'] == [py.random()]
        before = r.export_state_json()
        with pytest.raises(RuntimeError):
            r._rng_probe_json('new-invalid-domain', '[{"kind":"bits","bits":65}]')
        assert r.export_state_json() == before
        r._rng_probe_json('render', '[{"kind":"random"}]')
        combat = random.Random(_derive_domain_seed(42, 'combat'))
        assert json.loads(r._rng_probe_json('combat', '[{"kind":"randint","lo":1,"hi":20}]'))['results'] == [combat.randint(1,20)]
    finally:
        r.close()


def test_scene_preparation_restores_existing_event_listeners():
    from framework.engine.events import EBS, Event
    saved = EBS._listeners
    callback = lambda event: None
    EBS.subscribe(Event, callback)
    try:
        prepare_scene(mode='real_time', scenario='chibi-small', seed=42)
        assert EBS._listeners is saved and callback in EBS._listeners[Event]
        with pytest.raises(Exception):
            prepare_scene(scenario='does-not-exist')
        assert EBS._listeners is saved and callback in EBS._listeners[Event]
    finally:
        EBS.unsubscribe(Event, callback)


def test_native_computation_detaches_the_gil(initial):
    r = NativeRuntime(json.dumps(initial))
    ops = json.dumps([{'kind': 'random'}] * 50000)
    ready, go, stop = threading.Event(), threading.Event(), threading.Event()
    progress = [0]
    def other_python_thread():
        ready.set()
        go.wait()
        while not stop.is_set():
            progress[0] += 1
            time.sleep(0.001)
    thread = threading.Thread(target=other_python_thread)
    thread.start()
    ready.wait()
    interval = sys.getswitchinterval()
    try:
        sys.setswitchinterval(1.0)
        go.set()
        r._rng_probe_json('gil-probe', ops)
        assert progress[0] > 0
    finally:
        stop.set()
        sys.setswitchinterval(interval)
        thread.join()
        r.close()
