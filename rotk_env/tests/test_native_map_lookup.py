"""E13 lookup representation preserves paths, wire, ownership and lifecycle."""
import copy
import json
import pytest

pytest.importorskip('star_native')
from star_native import NativeRuntime
from rotk_env.runtime.bootstrap import export_initial_state
from rotk_env.tests.test_native_movement import make_world
from rotk_env.prefabs.config import TerrainType


@pytest.mark.parametrize('threads', [1, 4])
@pytest.mark.parametrize('display', ['none', 'dummy', 'window'])
@pytest.mark.parametrize('variant', ['normal', 'holes', 'sparse', 'empty', 'missing', 'paused', 'game_over'])
def test_paths_wire_full_state_and_modes(threads, display, variant):
    world, ids = make_world(display, {(0, 1): TerrainType.FOREST, (1, 0): TerrainType.WATER})
    initial = export_initial_state(world, display=display);world.reset()
    if variant == 'holes':
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
        b.reset(json.dumps(initial));assert json.loads(b._map_lookup_diagnostics_json())['requested'] is False
        b.close();assert retained == saved
        with pytest.raises(RuntimeError):b._set_map_lookup_mode('dense_tile')
    finally:a.close();b.close()
