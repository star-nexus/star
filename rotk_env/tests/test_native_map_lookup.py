"""E13 lookup representation preserves paths, wire, ownership and lifecycle."""
import copy
import json
import pytest

pytest.importorskip('star_native')
from star_native import NativeRuntime
from rotk_env.runtime.bootstrap import export_initial_state
from rotk_env.tests.test_native_movement import make_world
from rotk_env.prefabs.config import TerrainType
from rotk_env.runtime.native import ActionRequest, RustRuntime
from rotk_env.systems.llm_system import LLMSystem
from rotk_env.tests.test_native_vision import make_vision_world
from rotk_env.tests.test_native_request_batch import frozen


@pytest.mark.parametrize('threads', [1, 4])
@pytest.mark.parametrize('display', ['none', 'dummy', 'window'])
@pytest.mark.parametrize('variant', ['normal', 'one_hole', 'holes', 'sparse', 'empty', 'missing', 'paused', 'game_over'])
def test_paths_wire_full_state_and_modes(threads, display, variant):
    world, ids = make_world(display, {(0, 1): TerrainType.FOREST, (1, 0): TerrainType.WATER})
    initial = export_initial_state(world, display=display);world.reset()
    if variant == 'one_hole':
        initial['singletons']['MapData']['tiles']['$map'] = [p for p in initial['singletons']['MapData']['tiles']['$map'] if p[0] != [0, 0]]
    elif variant == 'holes':
        initial['singletons']['MapData']['tiles']['$map'] = initial['singletons']['MapData']['tiles']['$map'][::2]
    elif variant == 'sparse':
        pairs = initial['singletons']['MapData']['tiles']['$map']
        initial['singletons']['MapData']['tiles']['$map'] = [pairs[0], pairs[-1]]
    elif variant == 'empty':initial['singletons']['MapData']['tiles']['$map'] = []
    elif variant == 'missing':
        tile_id = initial['singletons']['MapData']['tiles']['$map'][0][1]
        next(e for e in initial['entities'] if e['id'] == tile_id)['components'].pop('Terrain')
    elif variant == 'paused':
        initial['clock']['paused'] = True
        initial['singletons']['GameTime']['paused'] = True
    elif variant == 'game_over':initial['singletons']['GameState'] = dict(game_over=True, winner='wei')
    a, b = NativeRuntime(json.dumps(initial), threads), NativeRuntime(json.dumps(initial), threads)
    try:
        a._set_map_lookup_mode('baseline')
        layout = json.loads(b._map_lookup_diagnostics_json())
        assert layout['requested'] is True
        # The half-removed fixture has 19 cells / 42 bbox slots and must fall back.
        assert layout['active'] is (variant not in ('holes', 'sparse', 'empty'))
        before = b.export_state_json();b._set_map_lookup_mode('dense_tile')
        assert b.export_state_json() == before == a.export_state_json()
        ops = [dict(kind='reachable', unit_id=i) for i in ids]
        ops += [dict(kind='path', unit_id=i, goal=[x,y]) for i in ids for x in range(-4,5) for y in range(-4,5)]
        encoded = json.dumps(ops)
        assert a._movement_probe_json(encoded) == b._movement_probe_json(encoded)
        params = json.dumps([dict(faction='wei', unit_ids=list(ids)), dict(faction='shu', unit_ids=[])])
        expected = a._observation_probe_json(params)
        assert b._observation_probe_json(params) == expected
        retained = json.loads(expected);saved = copy.deepcopy(retained)
        for mode in ['baseline', 'dense_tile', 'dense_tile', 'baseline', 'dense_tile']:
            b._set_map_lookup_mode(mode)
            assert b._observation_probe_json(params) == expected
            assert b.export_state_json() == before
        with pytest.raises(ValueError, match='invalid map lookup mode'):b._set_map_lookup_mode('unknown')
        assert b.export_state_json() == before
        with pytest.raises(RuntimeError):b.reset('{broken')
        assert b._map_lookup_diagnostics_json() != a._map_lookup_diagnostics_json()
        assert b.export_state_json() == before
        assert a.take_presentation_delta_json() == b.take_presentation_delta_json()
        for tick in range(3):
            a.step(.1, 100.+tick);b.step(.1, 100.+tick)
            assert a.export_state_json() == b.export_state_json()
            assert a.take_presentation_delta_json() == b.take_presentation_delta_json()
        b._set_map_lookup_mode('baseline')
        b.reset(json.dumps(initial))
        assert json.loads(b._map_lookup_diagnostics_json()) == layout
        b.close();assert retained == saved
        with pytest.raises(RuntimeError):b._set_map_lookup_mode('dense_tile')
    finally:a.close();b.close()


@pytest.mark.parametrize('threads', [1, 4])
def test_default_public_requests_and_batch_match_explicit_baseline(threads, frozen):
    world, ids, _ = make_vision_world('dummy')
    world.add_system(LLMSystem())
    initial = export_initial_state(world, display='dummy')
    world.reset()
    with RustRuntime(initial, threads=threads) as baseline, RustRuntime(initial, threads=threads) as candidate:
        baseline._native._set_map_lookup_mode('baseline')
        assert json.loads(candidate._native._map_lookup_diagnostics_json())['active'] is True
        registration = dict(faction='wei', provider='synthetic', model_id='fake', base_url='https://host/v1/')
        for runtime in (baseline, candidate):
            result = runtime.execute_action('register_agent_info', registration, agent_id='alpha',
                wall_time=frozen[0], registration_time='2026-09-12T12:00:00')
            assert result['success'] is True
        assert candidate.get_faction_state_json('wei', agent_id='alpha', wall_time=frozen[0]) == baseline.get_faction_state_json('wei', agent_id='alpha', wall_time=frozen[0])
        requests = [ActionRequest('alpha', 'get_faction_state', dict(faction='wei', unit_ids=[uid]), frozen[0])
                    for uid in ids[:2]]
        assert candidate.execute_actions(requests) == baseline.execute_actions(requests)
        assert candidate.export_state() == baseline.export_state()
        assert candidate.take_presentation_delta() == baseline.take_presentation_delta()
        for tick in range(3):
            candidate.step(.1, wall_time=frozen[0]+tick)
            baseline.step(.1, wall_time=frozen[0]+tick)
            assert candidate.export_state() == baseline.export_state()
            assert candidate.take_presentation_delta() == baseline.take_presentation_delta()
        retained = candidate.get_faction_state('wei', agent_id='alpha', wall_time=frozen[0])
        saved = copy.deepcopy(retained)
        candidate.reset(initial)
        assert json.loads(candidate._native._map_lookup_diagnostics_json())['active'] is True
        assert candidate.get_faction_state('wei', agent_id='alpha')['error_code'] == 2005
        assert retained == saved
