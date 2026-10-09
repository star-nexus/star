"""E10 owned window history storage, exports, wrap and error-prefix contracts."""
import json

import pytest

pytest.importorskip('star_native')
from star_native import NativeRuntime
from rotk_env.tests.test_native_statistics_compute import initial_statistics


def snapshot(n):
    return json.loads(n.export_state_json())


def compare_step(a, b, wall, dt=.1, profile=False):
    reports = []
    for n in (a, b):
        reports.append(json.loads(n._step_profile_json(dt, wall)) if profile else n.step(dt, wall))
    assert snapshot(a) == snapshot(b)
    assert a.take_presentation_delta_json() == b.take_presentation_delta_json()
    return reports


@pytest.mark.parametrize('threads', [1, 4])
@pytest.mark.parametrize('limit,old_rows', [(0,0), (0,7), (1,1), (2,0), (2,2), (2,9), (10000,10000)])
def test_wrap_retention_switch_and_owned_export(threads, limit, old_rows):
    initial, ids = initial_statistics('window')
    initial['systems']['StatisticsSystem']['history_limit'] = limit
    initial['singletons']['GameStats']['unit_observation_history'] = [
        {'prior': i, 'extension': {'nested': [i, '独立所有权']}} for i in range(old_rows)
    ]
    scene = json.dumps(initial)
    a, b = NativeRuntime(scene, threads), NativeRuntime(scene, threads)
    try:
        a._set_statistics_history_mode('baseline')
        b._set_statistics_history_mode('deque')
        assert snapshot(a) == snapshot(b) == initial
        for tick in range(25):
            if tick in (8, 16):
                before = snapshot(b)
                b._set_statistics_history_mode('baseline' if tick == 8 else 'deque')
                assert snapshot(b) == before
            compare_step(a, b, 1720000000. + tick)
            assert len(snapshot(b)['singletons']['GameStats']['unit_observation_history']) <= limit
        saved = b.export_state_json()
        owned = snapshot(b)
        if owned['singletons']['GameStats']['unit_observation_history']:
            owned['singletons']['GameStats']['unit_observation_history'][0]['foreign'] = [999]
        assert b.export_state_json() == saved
        c, d = NativeRuntime(saved, threads), NativeRuntime(saved, threads)
        try:
            assert snapshot(c) == snapshot(b)
            c._set_statistics_history_mode('deque')
            compare_step(d, c, 1720000030.)
            b.step(.1, 1720000030.)
            assert snapshot(b) == snapshot(c)
        finally:
            c.close(); d.close()
    finally:
        a.close(); b.close()


@pytest.mark.parametrize('threads', [1, 4])
@pytest.mark.parametrize('bad_index', [0, 1, 2])
@pytest.mark.parametrize('display', ['window', 'none'])
def test_error_successful_prefix_and_failed_reset(threads, bad_index, display):
    initial, ids = initial_statistics(display)
    units = {e['id']: e['components'] for e in initial['entities']}
    units[ids[bad_index]]['UnitCount']['max_count'] = 0
    prior = 10 if display == 'window' else 10000
    initial['singletons']['GameStats']['unit_observation_history'] = [{'prior': i} for i in range(prior)]
    scene = json.dumps(initial)
    instances = [NativeRuntime(scene, threads) for _ in range(2)]
    try:
        instances[1]._set_statistics_history_mode('deque')
        for n in instances:
            with pytest.raises(RuntimeError, match='statistics health division by zero'):
                n.step(.25, 1720000000.)
        assert snapshot(instances[0]) == snapshot(instances[1])
        before = instances[1].export_state_json()
        with pytest.raises(RuntimeError):
            instances[1].reset('{}')
        assert instances[1].export_state_json() == before
        instances[1]._set_statistics_history_mode('baseline')
        assert instances[1].export_state_json() == before
    finally:
        for n in instances: n.close()


@pytest.mark.parametrize('variant', ['disabled', 'missing_stats', 'duplicates', 'paused', 'scaled', 'game_over', 'dummy'])
@pytest.mark.parametrize('threads', [1, 4])
def test_phases_missing_rows_and_clock_boundaries(variant, threads):
    initial, ids = initial_statistics('window')
    system = initial['systems']['StatisticsSystem']
    if variant == 'disabled': system['enabled'] = False
    if variant == 'missing_stats': del initial['singletons']['GameStats']
    if variant == 'duplicates':
        system['cycle'] = dict(phase='observations', index=0, observation_entities=[ids[0], ids[0], ids[1], ids[2], 99999],
                               visibility_entities=list(ids), faction_counts={}, visibility_cleared=False,
                               fog_disabled_visible_to=None)
        units = {e['id']: e['components'] for e in initial['entities']}
        del units[ids[1]]['MovementPoints']; del units[ids[2]]['UnitCount']
    if variant == 'dummy': initial['display'] = 'dummy'
    if variant == 'game_over': initial['singletons']['GameState']['game_over'] = True
    scene = json.dumps(initial)
    a, b = NativeRuntime(scene, threads), NativeRuntime(scene, threads)
    try:
        b._set_statistics_history_mode('deque')
        if variant in ('paused', 'scaled'):
            for n in (a, b): n.set_clock(variant == 'paused', 2. if variant == 'scaled' else 1.)
        for tick in range(12): compare_step(a, b, 1720000000. + tick)
    finally:
        a.close(); b.close()


def test_invalid_mode_reset_default_and_multi_instance():
    initial, _ = initial_statistics('window')
    initial['singletons']['GameStats']['unit_observation_history'] = [{'prior': i} for i in range(10)]
    scene = json.dumps(initial)
    a, b = NativeRuntime(scene, 1), NativeRuntime(scene, 4)
    try:
        before = a.export_state_json()
        with pytest.raises(ValueError, match='invalid statistics history mode'):
            a._set_statistics_history_mode('unknown')
        assert a.export_state_json() == before
        a._set_statistics_history_mode('deque')
        left, right = compare_step(a, b, 1720000000., profile=True)
        assert left['statistics']['history_transfers'] == 1
        assert left['statistics']['history_retained_slots_relocated'] == 0
        assert right['statistics']['history_retained_slots_relocated'] == 2
        for n in (a,b): n.reset(scene)
        left, right = compare_step(a, b, 1720000000., profile=True)
        assert left['statistics']['history_transfers'] == 0
        assert left['statistics']['history_retained_slots_relocated'] == 2
        returned = snapshot(a)
        a.close()
        assert returned['singletons']['GameStats']['unit_observation_history']
        with pytest.raises(RuntimeError, match='closed'):
            a._set_statistics_history_mode('deque')
    finally:
        a.close(); b.close()


@pytest.mark.parametrize('value', [None, {}, 'invalid'])
def test_malformed_history_fails_at_step_not_configuration(value):
    initial, _ = initial_statistics('window')
    initial['singletons']['GameStats']['unit_observation_history'] = value
    scene = json.dumps(initial)
    for mode in ('baseline', 'deque'):
        n = NativeRuntime(scene, 1)
        n._set_statistics_history_mode(mode)
        assert snapshot(n) == initial
        with pytest.raises(BaseException, match='observation history'):
            n.step(.25, 1720000000.)
        with pytest.raises(RuntimeError, match='poisoned'):
            n.export_state_json()
        # Existing panic boundary intentionally poisons the owning mutex;
        # its Python owner is dropped rather than recovering through close.
