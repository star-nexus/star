import pytest
from .test_service import arena, pair
from starbench_arena import store as db
from starbench_arena.policy import settle, check_matches
from starbench_arena.ranking import leaderboard

@pytest.mark.asyncio
async def test_settlement_idempotency_and_separate_modes(arena):
    a, b, mid, *_ = await pair(arena)
    match = arena.store.one(db.matches, id=mid)
    await settle(arena, match, dict(winner='wei', is_tie=False, source='turn_timeout', game_duration_seconds=1, units_info={}))
    await settle(arena, match, dict(winner='shu', is_tie=False, source='env'))
    board = leaderboard(arena.store, 'turn_based')
    assert [r['elo'] for r in board['rows']] == [1016, 984]
    assert [r['pw_elo'] for r in board['rows']] == [1016, 984]
    assert len(arena.store.all(db.results)) == 1
    assert not leaderboard(arena.store, 'real_time')['rows']
    assert board == leaderboard(arena.store, 'turn_based')

@pytest.mark.asyncio
async def test_preparation_timeout_not_ranked(arena):
    a, b, mid, *_ = await pair(arena)
    arena.store.update(db.matches, {'id': mid}, status='preparing', prepared=0)
    await check_matches(arena, 1000)
    assert arena.store.one(db.matches, id=mid)['status'] == 'cancelled'
    assert not arena.store.all(db.results)

@pytest.mark.asyncio
async def test_unrecoverable_worker_aborts(arena):
    a, b, mid, *_ = await pair(arena)
    async def fail(*args): raise OSError('worker gone')
    arena.workers.control = fail
    for _ in range(3): await check_matches(arena)
    assert arena.store.one(db.matches, id=mid)['status'] == 'aborted'
    assert not arena.store.all(db.results)

@pytest.mark.asyncio
async def test_turn_reminder_recovers_without_agent_reconnecting(arena):
    a,b,mid,*_=await pair(arena)
    async def status(*args):
        return {'running':True,'result':None,'state':{'current_player':'shu','turn_number':4}}
    arena.workers.control=status
    await check_matches(arena);await check_matches(arena)
    events=[e for e in arena.read_events(b,mid)['events'] if e['kind']=='turn_start']
    assert len(events)==1 and events[0]['body']['turn_number']==4
