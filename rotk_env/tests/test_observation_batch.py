"""Local batches retain the ordinary gate, ordering and response ownership."""
import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from rotk_env.components import GameStats
from rotk_env.prefabs.config import Faction
from rotk_env.systems.llm_system import LLMSystem
from rotk_env.tests.test_selected_observation import setup_world


def setup():
    world, a, b, enemy = setup_world()
    gate = LLMSystem(server_url=None)
    world.add_system(gate)
    world.get_singleton_component(GameStats).agent_id_to_faction['c'] = Faction.SHU
    return world, gate, a, b, enemy


def query(agent, uid, faction='wei', action_id=1):
    return {'agent_id':agent, 'action_id':action_id,
            'params':{'faction':faction, 'unit_ids':[uid]}}


def decode(result):
    return [json.loads(r['payload']) for r in result['responses']]


def reference(gate, requests):
    return [gate._process_action_request(r['agent_id'],r['action_id'],
        'get_faction_state',dict(r['params']),send_response=False) for r in requests]


@pytest.mark.parametrize("reuse", [False, True])
def test_batch_gate_and_independent_bytes_match_single_queries(monkeypatch, reuse):
    monkeypatch.setattr("rotk_env.systems.llm_system.time.time", lambda: 1234.0)
    world, gate, a, b, enemy = setup()
    requests = [query('a',a), query('b',a),query('c',enemy,'shu'),
                query('a',enemy),query('unknown',a),query('b',b,'shu')]
    expected = reference(gate,requests)
    result = gate.process_observation_batch(requests,budget_ms=1000,reuse=reuse)
    assert result['consumed']==len(requests)
    assert decode(result)==expected
    assert expected[0]['units'][0]['commandable']
    assert not expected[1]['units'][0]['commandable']
    assert not any(r['success'] for r in expected[3:])
    decoded = decode(result)
    decoded[0]['units'][0]['position']['col']=999
    assert decode(result)==expected
    assert gate._observation_batch_context is None
    assert gate.action_handler._observation_batch_context is None


def test_budget_prefix_and_write_rejection(monkeypatch):
    _, gate, a, *_ = setup()
    requests=[query('a',a,action_id=i) for i in range(3)]
    assert gate.process_observation_batch(requests,budget_ms=0)['consumed']==0
    assert gate.process_observation_batch(requests,budget_ms=1000,max_requests=1)['consumed']==1
    # Simulate a single slow uninterruptible request, without sleeping in tests.
    now=[0.0]
    monkeypatch.setattr('rotk_env.systems.llm_system.time.perf_counter',lambda:now[0])
    original=gate._process_action_request
    def slow(*args,**kwargs):
        result=original(*args,**kwargs)
        now[0]+=.02
        return result
    monkeypatch.setattr(gate,'_process_action_request',slow)
    result=gate.process_observation_batch(requests,budget_ms=12)
    assert result['consumed']==1 and result['responses'][0]['action_id']==0
    with pytest.raises(ValueError,match='only get_faction_state'):
        gate.process_observation_batch([{'action':'move'}])


def test_exception_and_reentry_release_context(monkeypatch):
    _,gate,a,*_=setup()
    original=gate._process_action_request
    def nested(*args,**kwargs):
        return gate.process_observation_batch([query('a',a)])
    monkeypatch.setattr(gate,'_process_action_request',nested)
    result=gate.process_observation_batch([query('a',a),query('a',a)],budget_ms=1000)
    assert result['consumed']==1 and not decode(result)[0]['success']
    assert gate._observation_batch_context is None
    monkeypatch.setattr(gate,'_process_action_request',original)
    assert decode(gate.process_observation_batch([query('a',a)],budget_ms=1000))[0]['success']


def test_wrong_thread_cannot_enter_world():
    _,gate,a,*_=setup()
    with ThreadPoolExecutor(max_workers=1) as pool:
        with pytest.raises(RuntimeError,match='owner thread'):
            pool.submit(gate.process_observation_batch,[query('a',a)]).result()


@pytest.mark.parametrize('fog_enabled', [True, False])
def test_reuse_is_exact_and_facts_build_once_across_factions(fog_enabled):
    from rotk_env.components import FogOfWar
    world, gate, a, b, enemy = setup()
    fog = world.get_singleton_component(FogOfWar)
    fog.enabled = fog_enabled
    fog.faction_vision[Faction.SHU] = set(fog.faction_vision[Faction.WEI])
    requests = [query('a', a), query('b', a), query('c', enemy, 'shu'), query('a', b)]
    expected = reference(gate, requests)
    result = gate.process_observation_batch(requests, budget_ms=1000)
    assert decode(result) == expected
    metrics = result['cache_metrics']
    assert metrics['census_builds'] == 1
    assert metrics['faction_builds'] == 2
    assert metrics['faction_hits'] == 2
    assert metrics['unit_panel_builds'] == 3
    assert metrics['unit_panel_hits'] == 1
    assert metrics['tile_hits'] > 0
    from rotk_env.components import MapData
    cells = world.get_singleton_component(MapData).tiles
    queried = set(cells) if not fog_enabled else set(cells).intersection(fog.faction_vision[Faction.WEI])
    assert metrics['tile_builds'] == len(queried)  # includes cached missing tiles
    # A subsequent batch starts fresh, even though World.revision did not change.
    again = gate.process_observation_batch(requests, budget_ms=1000)
    assert again['cache_metrics'] == metrics


def test_in_place_changes_between_batches_are_immediate():
    from rotk_env.components import ActionPoints, FogOfWar, UnitCount
    world, gate, a, b, enemy = setup()
    requests = [query('a', a), query('b', b)]
    first = decode(gate.process_observation_batch(requests, budget_ms=1000))
    revision = world.revision
    world.get_component(a, ActionPoints).current_ap = 0
    world.get_component(b, UnitCount).current_count = 0
    world.get_singleton_component(FogOfWar).faction_vision[Faction.WEI].clear()
    assert world.revision == revision
    second = decode(gate.process_observation_batch(requests, budget_ms=1000))
    assert second == reference(gate, requests)
    assert second != first
    assert second[0]['alive_units'] == 1
    assert second[0]['visible_enemy_units'] == []
    assert second[1]['units'] == []


def test_encoding_failure_releases_context_and_stops_prefix(monkeypatch):
    _, gate, a, *_ = setup()
    original = gate._process_action_request
    monkeypatch.setattr(gate, '_process_action_request', lambda **kw: {'success': True, 'bad': object()})
    result = gate.process_observation_batch([query('a', a)]*2, budget_ms=1000)
    assert result['consumed'] == 1
    assert not decode(result)[0]['success']
    assert gate._observation_batch_context is None
    monkeypatch.setattr(gate, '_process_action_request', original)
    assert decode(gate.process_observation_batch([query('a', a)], budget_ms=1000))[0]['success']


def test_revision_change_and_business_write_reentry_stop_batch(monkeypatch):
    from rotk_env.components import UnitCount
    world, gate, a, *_ = setup()
    original = gate._process_action_request
    def revision_change(**kwargs):
        result = original(**kwargs)
        world.bump_revision()
        return result
    monkeypatch.setattr(gate, '_process_action_request', revision_change)
    result = gate.process_observation_batch([query('a', a)]*2, budget_ms=1000)
    assert result['consumed'] == 1 and not decode(result)[0]['success']
    assert gate._observation_batch_context is None
    def write_reentry(**kwargs):
        return original('a', 999, 'move', {'unit_id': a, 'target_position': {'col': 1, 'row': 0}}, send_response=False)
    monkeypatch.setattr(gate, '_process_action_request', write_reentry)
    result = gate.process_observation_batch([query('a', a)]*2, budget_ms=1000)
    assert result['consumed'] == 1 and not decode(result)[0]['success']
    assert gate._observation_batch_context is None


def test_only_requested_faction_action_points_are_materialized():
    from rotk_env.components import ActionPoints
    from rotk_env.utils.observation_batch import ObservationBatchContext
    world, gate, a, b, enemy = setup()
    context = ObservationBatchContext(gate.action_handler)
    totals, living, alive = context.census()
    assert ActionPoints not in context._components
    assert context.actionable(Faction.WEI, alive[Faction.WEI]) == 2
    assert set(context._components[ActionPoints]) == {a, b}
    context.close()
    assert not context._components and not context._cache


@pytest.mark.parametrize('change', ['position', 'mp', 'faction', 'ownership', 'replace', 'destroy'])
def test_other_world_changes_between_batches_match_uncached(change):
    from rotk_env.components import HexPosition, MovementPoints, TeamCoordination, Unit, UnitCount
    world, gate, a, b, enemy = setup()
    requests = [query('a', a), query('b', a), query('c', enemy, 'shu')]
    # Query the full faction after membership changes, avoiding invalid selections.
    if change in ('faction', 'destroy'):
        for request in requests:
            request['params'].pop('unit_ids')
    first = decode(gate.process_observation_batch(requests, budget_ms=1000))
    if change == 'position':
        world.get_component(a, HexPosition).col = 1
    elif change == 'mp':
        world.get_component(a, MovementPoints).current_mp = 0
    elif change == 'faction':
        world.get_component(a, Unit).faction = Faction.SHU
    elif change == 'ownership':
        world.get_singleton_component(TeamCoordination).claim_units('b', [a], exclusive=False)
    elif change == 'replace':
        world.add_component(a, UnitCount(current_count=25, max_count=100))
    else:
        world.destroy_entity(a)
    second = decode(gate.process_observation_batch(requests, budget_ms=1000))
    assert second == reference(gate, requests)
    assert second != first


def test_empty_batch_does_not_build_observation_facts():
    _, gate, *_ = setup()
    result = gate.process_observation_batch([], budget_ms=1000)
    assert result['consumed'] == 0
    assert result['cache_metrics'] == {}
