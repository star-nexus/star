import pytest
from starbench_arena.config import Settings
from starbench_arena.store import Store
from starbench_arena import store as db
from starbench_arena.service import Arena
from starbench_arena.auth import Principal

class Workers:
    def __init__(self):
        self.calls = []
        self.on_event = None
        self.effects = {}
    async def launch(self, match):
        return {'url': 'http://worker', 'token': 'private-test-secret'}
    async def control(self, worker, command):
        return {'running': command == 'start', 'result': None}
    async def call(self, agent, action, parameters, operation_id=None):
        self.calls.append((agent['id'], action, parameters, operation_id))
        if action == 'get_action_list':
            return {'success': True, 'names': ['move', 'attack'], 'actions': {}}
        key = (agent['id'], operation_id)
        if operation_id and key in self.effects:
            return self.effects[key]
        result = {'success': True, 'action': action}
        if operation_id:
            self.effects[key] = result
        return result
    async def close_match(self, match): pass
    async def close(self): pass

@pytest.fixture
def arena():
    store = Store('sqlite:///:memory:'); store.initialize()
    return Arena(Settings(development=True), store, Workers())

async def pair(arena, mode='turn_based'):
    a, b = Principal('a'), Principal('b')
    ea = await arena.register_entry(a, 'harness', 'v1')
    eb = await arena.register_entry(b, 'harness', 'v1')
    m = await arena.request_match(a, ea['id'], mode)
    joined = await arena.request_match(b, eb['id'], mode)
    assert joined['id'] == m['id']
    aa = (await arena.register_agents(a, m['id'], ['a1', 'a2']))[0]['agent_handle']
    bb = (await arena.register_agents(b, m['id'], ['b1']))[0]['agent_handle']
    await arena.ready_match(a, m['id']); await arena.ready_match(b, m['id'])
    return a, b, m['id'], aa, bb

@pytest.mark.asyncio
async def test_identity_batch_partial_success_and_retries(arena):
    a, b, mid, aa, bb = await pair(arena)
    with pytest.raises(PermissionError):
        await arena.action(b, aa, 'move', {}, 'op')
    with pytest.raises(PermissionError):
        await arena.action(a, aa, 'get_faction_state', {'faction': 'shu'})
    batch = [{'action': 'move', 'operation_id': 'op', 'parameters': {'unit_id': 1}},
             {'action': 'reset', 'operation_id': 'evil'}]
    results = await arena.submit_actions(a, aa, batch)
    assert results['results'][0]['response']['success']
    assert not results['results'][1]['response']['success']
    calls = len(arena.workers.calls)
    await arena.submit_actions(a, aa, batch[:1])
    assert len(arena.workers.calls) == calls
    with pytest.raises(ValueError, match='conflict'):
        await arena.action(a, aa, 'attack', {}, 'op')
    assert (await arena.get_operation(a, aa, 'op'))['state'] == 'completed'
    assert 'worker' not in arena.list_matches(a)[0]

@pytest.mark.asyncio
async def test_entries_are_immutable_events_are_not_consumed(arena):
    a, b, mid, aa, bb = await pair(arena)
    with pytest.raises(ValueError, match='immutable'):
        await arena.register_entry(a, 'harness', 'v1', {'changed': True})
    arena.emit(mid, 'turn_start', {'faction': 'wei'}, a.subject)
    left = arena.read_events(a, mid)
    assert left == arena.read_events(a, mid)
    assert not any(e['kind'] == 'turn_start' for e in arena.read_events(b, mid)['events'])
    assert not arena.read_events(a, mid, left['cursor'])['events']
    resumed = await arena.resume_agent(a, aa)
    assert resumed['generation'] == 1
    assert resumed['agent_handle'] == aa

@pytest.mark.asyncio
async def test_invites_and_no_agent_readiness(arena):
    a = Principal('a')
    entry = await arena.register_entry(a, 'x', 'v')
    match = await arena.request_match(a, entry['id'], 'real_time', 'private')
    with pytest.raises(ValueError):
        await arena.ready_match(a, match['id'])
    cancelled = await arena.cancel_match(a, match['id'])
    assert cancelled['status'] == 'cancelled'
