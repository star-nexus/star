"""Opt-in profiler is read-only and preserves the ordinary handler contract."""
import json
import pytest
pytest.importorskip('star_native')
from star_native import NativeRuntime
from rotk_env.runtime.bootstrap import export_initial_state
from rotk_env.tests.test_native_observation import setup


@pytest.mark.parametrize('threads', [1, 2, 4])
def test_profile_matches_handler_without_changing_world(threads):
    world, (a,b,_), _ = setup('none')
    initial=json.dumps(export_initial_state(world))
    n=NativeRuntime(initial,threads)
    try:
        wire=json.dumps([dict(faction='wei',unit_ids=[b,a,b]),dict(faction='shu'),dict(faction='bad')])
        regular=json.loads(n._observation_probe_json(wire))
        encoded,timing=n._observation_profile_json(wire)
        result=json.loads(encoded);t=json.loads(timing)
        assert result['results']==regular['results']
        assert {k:v for k,v in result['metrics'].items() if k!='panel_worker_threads'} == {k:v for k,v in regular['metrics'].items() if k!='panel_worker_threads'}
        assert all(isinstance(v,int) and v>=0 for k,v in t.items() if k!='profile')
        assert all(isinstance(v,int) and v>=0 for v in t['profile'].values())
        assert t['profile']['public_encode_ns']<=t['profile']['faction_ns']<=t['batch_ns']
        assert t['profile']['census_ns']<=t['profile']['faction_ns']
        assert t['profile']['panels_ns']<=t['batch_ns']
        assert sum(t[k] for k in ('parse_ns','batch_ns','final_encode_ns','drop_ns'))<=t['native_ns']
        assert json.loads(n.export_state_json())==json.loads(initial)
        with pytest.raises(RuntimeError):n._observation_profile_json('{')
        assert json.loads(n.export_state_json())==json.loads(initial)
        n.close()
        with pytest.raises(RuntimeError):n._observation_profile_json('[]')
    finally:n.close();world.reset()
