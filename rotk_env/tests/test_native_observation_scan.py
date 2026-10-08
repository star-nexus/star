"""E8 scan research preserves missing-component behavior and scope lifetime."""
import json
import pytest
from rotk_env.components import ActionPoints, FogOfWar, HexPosition, UnitCount
from rotk_env.runtime.bootstrap import export_initial_state
from rotk_env.runtime.native import RustRuntime
from rotk_env.tests.test_native_observation import setup


@pytest.mark.parametrize('threads', [1, 4])
@pytest.mark.parametrize('missing', [None, ActionPoints, HexPosition, UnitCount])
@pytest.mark.parametrize('fog', [False, True])
@pytest.mark.parametrize('mode', ['entity_ref', 'borrowed_census'])
def test_scans_preserve_full_projection_and_metrics(threads, missing, fog, mode):
    world, (a, b, c), _ = setup('window')
    try:
        world.get_singleton_component(FogOfWar).enabled = fog
        if missing:
            world.remove_component(b, missing)
        state = export_initial_state(world, display='window')
        queries = [dict(faction='wei', agent_id='alpha', unit_ids=[b, a, b]),
                   dict(faction='shu', agent_id='enemy', unit_ids=[c]),
                   dict(faction='wei', agent_id='beta'),
                   dict(faction='wu', agent_id=None, unit_ids=[])]
        with RustRuntime(state, threads=threads) as base, RustRuntime(state, threads=threads) as candidate:
            candidate._set_observation_scan_research(mode)
            # Bare projection compares all work counters, not just output.
            wire = json.dumps(queries)
            assert candidate._native._observation_probe_json(wire) == base._native._observation_probe_json(wire)
            assert candidate.export_state() == base.export_state()
            reports = []
            responses = []
            for runtime in (base, candidate):
                with runtime._admitted_observation_segment('segment_encoded', diagnostics=True) as segment:
                    responses.append([segment.get_faction_state_json(**q, wall_time=100.+i)
                                      for i, q in enumerate(queries)])
                reports.append(segment.report)
            assert responses[0] == responses[1]
            assert reports[0] == reports[1]
            assert base.export_state() == candidate.export_state()
    finally:
        world.reset()


@pytest.mark.parametrize('mode', ['entity_ref', 'borrowed_census'])
def test_mode_validation_barrier_reset_and_instance_isolation(mode):
    world, (a, _, _), _ = setup('window')
    try:
        state = export_initial_state(world, display='window')
        q = dict(faction='wei', agent_id='alpha', unit_ids=[a], wall_time=100.)
        with RustRuntime(state) as first, RustRuntime(state) as second:
            assert first._native._observation_scan_research() == 'baseline'
            first._set_observation_scan_research(mode)
            assert second._native._observation_scan_research() == 'baseline'
            with first._admitted_observation_segment('segment_encoded', diagnostics=True) as segment:
                segment.get_faction_state_json(**q)
                with pytest.raises(ValueError): first._set_observation_scan_research('bad')
                assert first._native._observation_scan_research() == mode
                segment.get_faction_state_json(**q)
            assert segment.report['query_diagnostics'][1]['metrics']['census_builds'] == 0
            with first._admitted_observation_segment('segment_encoded') as segment:
                before = segment.get_faction_state_json(**q)
                first._set_observation_scan_research('baseline')
                after = segment.get_faction_state_json(**q)
            assert before == after and segment.report is None
            first._set_observation_scan_research(mode)
            first.reset(state)
            assert first._native._observation_scan_research() == 'baseline'
            assert first.export_state() == second.export_state()
        with pytest.raises(RuntimeError): first._set_observation_scan_research('entity_ref')
    finally:
        world.reset()
