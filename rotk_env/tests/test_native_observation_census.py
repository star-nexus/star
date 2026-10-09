"""Default census keeps counts, ordered IDs and owned responses across writes."""
import json
import pytest
from rotk_env.components import ActionPoints, FogOfWar, HexPosition, UnitCount
from rotk_env.runtime.bootstrap import export_initial_state
from rotk_env.runtime.native import RustRuntime
from rotk_env.tests.test_native_observation import setup


@pytest.mark.parametrize('threads', [1, 4])
@pytest.mark.parametrize('missing', [None, ActionPoints, HexPosition, UnitCount])
@pytest.mark.parametrize('fog', [False, True])
def test_default_census_preserves_missing_component_counts_and_order(threads, missing, fog):
    world, (a, b, enemy), _ = setup('window')
    try:
        world.get_singleton_component(FogOfWar).enabled = fog
        for unit in (a, b, enemy):
            world.get_component(unit, UnitCount).current_count = 1
            world.get_component(unit, ActionPoints).current_ap = 1
        if missing:
            world.remove_component(b, missing)
        state = export_initial_state(world, display='window')
        queries = [dict(faction='wei', agent_id='alpha', unit_ids=[b, a, b]),
                   dict(faction='shu', agent_id='enemy', unit_ids=[enemy]),
                   dict(faction='wei', agent_id='beta'),
                   dict(faction='wu', agent_id=None, unit_ids=[])]
        with RustRuntime(state, threads=threads) as runtime:
            before = runtime.export_state()
            report = json.loads(runtime._native._observation_probe_json(json.dumps(queries)))
            assert runtime.export_state() == before
            wei, shu, repeated, empty = report['results']
            assert (wei['total_units'], wei['alive_units'], wei['actionable_units']) == (
                2, 1 if missing is UnitCount else 2,
                1 if missing in (UnitCount, ActionPoints) else 2)
            assert (shu['total_units'], shu['alive_units'], shu['actionable_units']) == (1, 1, 1)
            assert (empty['total_units'], empty['alive_units'], empty['actionable_units']) == (0, 0, 0)
            assert repeated['alive_units'] == wei['alive_units']
            assert [u['unit_id'] for u in repeated['units']] == (
                [a] if missing is UnitCount else [a, b])
            assert report['metrics']['census_builds'] == 1
            assert report['metrics']['census_entities_visited'] == 3
            with runtime._admitted_observation_segment('segment_encoded', diagnostics=True) as segment:
                responses = [segment.get_faction_state_json(**q, wall_time=100.+i)
                             for i, q in enumerate(queries)]
            assert [json.loads(wire) for wire in responses[:3]] == report['results'][:3]
            # The bare probe can inspect an empty faction; the action gate still
            # rejects the unregistered caller before projecting any facts.
            assert json.loads(responses[3])['error_code'] == 2005
            assert segment.report['query_diagnostics'][0]['metrics']['census_builds'] == 1
            assert segment.report['query_diagnostics'][2]['metrics']['census_builds'] == 0
    finally:
        world.reset()


@pytest.mark.parametrize('threads', [1, 4])
def test_default_census_reset_and_instances_keep_owned_results(threads):
    world, (a, b, _), _ = setup('window')
    try:
        original = export_initial_state(world, display='window')
        world.get_component(b, UnitCount).current_count = 0
        changed = export_initial_state(world, display='window')
        q = dict(faction='wei', agent_id='alpha', unit_ids=[])
        with RustRuntime(original, threads=threads) as first, RustRuntime(changed, threads=threads) as second:
            assert not hasattr(first._native, '_set_observation_scan_research')
            saved = first.get_faction_state_json(**q, wall_time=100.)
            assert json.loads(saved)['alive_units'] == 2
            assert json.loads(second.get_faction_state_json(**q, wall_time=100.))['alive_units'] == 1
            with first._admitted_observation_segment('segment_encoded') as segment:
                assert json.loads(segment.get_faction_state_json(**q, wall_time=101.))['alive_units'] == 2
                first.reset(changed)
                assert json.loads(segment.get_faction_state_json(**q, wall_time=102.))['alive_units'] == 1
            first.reset(original)
            assert json.loads(first.get_faction_state_json(**q, wall_time=103.))['alive_units'] == 2
        assert json.loads(saved)['alive_units'] == 2
    finally:
        world.reset()
