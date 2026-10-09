"""E11 exact terrain bytes are derived, bounded and independent of visibility."""
import copy
import json
import pytest

pytest.importorskip('star_native')
from star_native import NativeRuntime
from rotk_env.runtime.bootstrap import export_initial_state
from rotk_env.tests.test_native_observation import setup


def scene(display='none'):
    world, ids, _ = setup(display)
    try:
        return export_initial_state(world, display=display), ids
    finally:
        world.reset()


def profile(n, params):
    raw, timing = n._observation_profile_json(json.dumps(params))
    return json.loads(raw)['results'], json.loads(timing)['profile']


@pytest.mark.parametrize('threads', [1, 4])
@pytest.mark.parametrize('display', ['none', 'dummy', 'window'])
@pytest.mark.parametrize('fog', [False, True])
def test_visibility_permissions_and_warm_hits(threads, display, fog):
    initial, (a, b, enemy) = scene(display)
    initial['singletons']['FogOfWar']['enabled'] = fog
    params = [dict(faction='wei', agent_id='alpha', unit_ids=[b, a, b]),
              dict(faction='shu', agent_id='enemy'), dict(faction='wu', unit_ids=[]),
              dict(faction='shu', agent_id='alpha'), dict(faction='wei', unit_ids=[enemy])]
    left, right = NativeRuntime(json.dumps(initial), threads), NativeRuntime(json.dumps(initial), threads)
    try:
        left._set_observation_terrain_mode('baseline')
        before = right.export_state_json()
        expected, _ = profile(left, params)
        cold, cold_p = profile(right, params)
        warm, warm_p = profile(right, params)
        assert cold == warm == expected
        assert cold_p['terrain_reuse_enabled'] is True
        assert cold_p['terrain_fact_builds'] > 0
        assert warm_p['terrain_fact_builds'] == 0
        assert warm_p['terrain_fact_hits'] > 0
        assert warm_p['terrain_cache_entries'] <= len(initial['singletons']['MapData']['tiles']['$map'])
        assert right.export_state_json() == before == left.export_state_json()
        # Decoded output is owned; modifying it cannot change cached bytes.
        warm[0]['visible_terrain'][0]['type'] = 'caller mutation'
        assert profile(right, params)[0] == expected
        retained = copy.deepcopy(cold)
        right._set_observation_terrain_mode('baseline')
        assert profile(right, params)[0] == retained
        right.close()
        assert cold == retained
    finally:
        left.close(); right.close()


@pytest.mark.parametrize('threads', [1, 4])
@pytest.mark.parametrize('variant', ['empty_map', 'missing_terrain', 'unicode_cost',
                                   'no_fog', 'empty_visible', 'off_map', 'paused', 'game_over'])
def test_imported_boundaries_match_baseline(threads, variant):
    initial, _ = scene()
    if variant == 'empty_map':
        initial['singletons']['MapData']['tiles']['$map'] = []
    elif variant == 'missing_terrain':
        next(e for e in initial['entities'] if e['id'] == 18)['components'].pop('Terrain')
    elif variant == 'unicode_cost':
        name = '林地"\\\n🌲'
        next(e for e in initial['entities'] if e['id'] == 18)['components']['Terrain']['terrain_type'] = name
        initial['rules']['terrain_effects'][name] = dict(movement_cost=999)
        initial['singletons']['FogOfWar']['enabled'] = False
    elif variant == 'no_fog':
        initial['singletons'].pop('FogOfWar')
    elif variant == 'empty_visible':
        initial['singletons']['FogOfWar']['faction_vision']['wei'] = {'$set': []}
    elif variant == 'off_map':
        initial['singletons']['FogOfWar']['faction_vision']['wei']['$set'].append([10000, -10000])
    elif variant == 'paused':
        initial['clock']['paused'] = True
        initial['singletons']['GameTime']['paused'] = True
    else:
        initial['singletons']['GameState']['game_over'] = True
        initial['singletons']['GameState']['winner'] = 'shu'
    a, b = NativeRuntime(json.dumps(initial), threads), NativeRuntime(json.dumps(initial), threads)
    try:
        a._set_observation_terrain_mode('baseline')
        for _ in range(3):
            assert profile(a, [dict(faction='wei', unit_ids=[])])[0] == profile(b, [dict(faction='wei', unit_ids=[])])[0]
        assert a.export_state_json() == b.export_state_json()
    finally:
        a.close(); b.close()


@pytest.mark.parametrize('threads', [1, 4])
def test_mode_reset_failure_instances_and_retained_responses(threads):
    initial, _ = scene()
    params = [dict(faction='wei', unit_ids=[])]
    a, b = NativeRuntime(json.dumps(initial), threads), NativeRuntime(json.dumps(initial), threads)
    try:
        b._set_observation_terrain_mode('baseline')
        saved, cold = profile(a, params)
        assert cold['terrain_reuse_enabled'] is True
        assert cold['terrain_fact_builds'] > 0
        before = a.export_state_json()
        with pytest.raises(ValueError, match='invalid observation terrain mode'):
            a._set_observation_terrain_mode('unknown')
        assert a.export_state_json() == before
        assert profile(a, params)[1]['terrain_fact_builds'] == 0
        with pytest.raises(RuntimeError):
            a.reset('{broken')
        assert a.export_state_json() == before
        assert profile(a, params)[1]['terrain_fact_builds'] == 0
        assert profile(b, params)[1]['terrain_reuse_enabled'] is False
        changed = copy.deepcopy(initial)
        changed['singletons']['FogOfWar']['enabled'] = False
        changed['rules']['terrain_effects']['plain']['movement_cost'] = 7
        a.reset(json.dumps(changed))
        reset_profile = profile(a, params)[1]
        assert reset_profile['terrain_reuse_enabled'] is True
        assert reset_profile['terrain_fact_builds'] > 0
        assert any(t['movement_cost'] == 7 for t in profile(a, params)[0][0]['visible_terrain'])
        a._set_observation_terrain_mode('baseline')
        assert profile(a, params)[1]['terrain_reuse_enabled'] is False
        with pytest.raises(RuntimeError):
            a.reset('{broken')
        assert profile(a, params)[1]['terrain_reuse_enabled'] is False
        a.reset(json.dumps(initial))
        assert profile(a, params)[0] == saved
        # Stable state does not grow cache backing storage over repeated reads.
        size = profile(a, params)[1]['terrain_cache_backing_bytes']
        for _ in range(50):
            assert profile(a, params)[1]['terrain_cache_backing_bytes'] == size
        a.close()
        assert saved[0]['visible_terrain']
        with pytest.raises(RuntimeError, match='closed'):
            a._set_observation_terrain_mode('baseline')
    finally:
        a.close(); b.close()


@pytest.mark.parametrize('threads', [1, 4])
def test_existing_mixed_death_permission_error_contract(monkeypatch, threads):
    # First instance in the established contract is batched candidate;
    # second instance executes the independent baseline one request at a time.
    from rotk_env.tests import test_native_encoded_observation as contract
    calls = 0
    def factory(*args, **kwargs):
        nonlocal calls
        n = NativeRuntime(*args, **kwargs)
        if calls != 0:
            n._set_observation_terrain_mode('baseline')
        calls += 1
        return n
    monkeypatch.setattr(contract, 'NativeRuntime', factory)
    contract.test_encoded_batch_freezes_facts_before_later_death_and_permission_writes(threads)


@pytest.mark.parametrize('threads', [1, 4])
def test_step_clock_scale_range_and_fog_changes(threads):
    initial, _ = scene('window')
    a, b = NativeRuntime(json.dumps(initial), threads), NativeRuntime(json.dumps(initial), threads)
    try:
        a._set_observation_terrain_mode('baseline')
        params = [dict(faction='wei'), dict(faction='shu')]
        for paused, scale in [(True, 1.), (False, 2.), (False, 1.)]:
            for n in (a, b):
                n.set_clock(paused, scale)
                n.step(.25, 1720000000.)
            assert profile(a, params)[0] == profile(b, params)[0]
            assert a.export_state_json() == b.export_state_json()
            assert a.take_presentation_delta_json() == b.take_presentation_delta_json()
    finally:
        a.close(); b.close()


@pytest.mark.parametrize('threads', [1, 4])
def test_default_cache_on_public_single_wire_and_batch_ingress(threads):
    from rotk_env.runtime.native import ActionRequest, RustRuntime
    initial, (unit, _, _) = scene('window')
    params = dict(faction='wei', unit_ids=[unit])
    wall_time = 1720000000.
    with RustRuntime(initial, threads=threads) as baseline, RustRuntime(initial, threads=threads) as ordinary:
        baseline._native._set_observation_terrain_mode('baseline')
        expected = baseline.get_faction_state_json(**params, agent_id='alpha', wall_time=wall_time)
        retained = ordinary.get_faction_state_json(**params, agent_id='alpha', wall_time=wall_time)
        assert retained == expected
        # The authenticated ordinary read populated the cache without a setter.
        warm = profile(ordinary._native, [dict(params, agent_id='alpha')])[1]
        assert warm['terrain_reuse_enabled'] is True
        assert warm['terrain_fact_builds'] == 0 and warm['terrain_fact_hits'] > 0
        assert baseline.get_faction_state(**params, agent_id='alpha', wall_time=wall_time) == ordinary.get_faction_state(**params, agent_id='alpha', wall_time=wall_time)
        requests = [ActionRequest('alpha', 'get_faction_state', params, wall_time),
                    ActionRequest('unknown', 'get_faction_state', params, wall_time),
                    ActionRequest('alpha', 'get_faction_state', params, wall_time)]
        actual = ordinary.execute_actions(requests)
        assert actual == baseline.execute_actions(requests)
        assert actual[0]['success'] and actual[1]['error_code'] == 2005
        assert ordinary.export_state() == baseline.export_state()
        assert ordinary.take_presentation_delta() == baseline.take_presentation_delta()
        ordinary.reset(initial)
        cold = profile(ordinary._native, [dict(params, agent_id='alpha')])[1]
        assert cold['terrain_reuse_enabled'] is True and cold['terrain_fact_builds'] > 0
    assert json.loads(retained)['success']
