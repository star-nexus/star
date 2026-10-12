"""Public match deadlines and settlement lifecycle, separate from game rules."""
import asyncio
import logging
import time
from . import store as db

log = logging.getLogger('starbench.arena')

async def settle(arena, match, outcome):
    async with arena.management:
        match = dict(arena.store.one(db.matches, id=match['id']))
        if arena.store.one(db.results, match_id=match['id']):
            return
        if match['status'] not in ('running', 'settling'):
            return
        valid = outcome['winner'] in ('wei', 'shu') or outcome.get('is_tie') is True
        body = dict(outcome, mode=match['mode'], season=match['season'],
            entries={f: p['entry'] for f, p in match['players'].items()},
            rated=match['kind'] != 'private' and valid, seed=match['seed'],
            scenario=match['scenario'], rules=match['rules'], settled_at=time.time())
        # Result order is the durable insertion sequence. Status and result commit together.
        with arena.store.transaction() as c:
            c.execute(db.results.insert().values(match_id=match['id'], body=body))
            c.execute(db.matches.update().where(db.matches.c.id == match['id']).values(status='finished'))
            c.execute(db.events.insert().values(match_id=match['id'], owner=None, kind='game_finished',
                body={'match_id': match['id'], 'winner': body['winner'], 'is_tie': body['is_tie']}, created=time.time()))
        await arena.workers.close_match(match)

async def check_matches(arena, now=None):
    now = time.time() if now is None else now
    for row in arena.store.all(db.matches):
        match = dict(row)
        if match['status'] not in ('preparing', 'running', 'settling') or not match['worker']:
            continue
        try:
            status = await arena.workers.control(match['worker'], 'status')
            arena.failures.pop(match['id'], None)
            if status['result']:
                # Recover the narrow start/DB-commit race after gateway restart.
                if match['status'] == 'preparing':
                    arena.store.update(db.matches, {'id': match['id']}, status='running')
                await settle(arena, match, status['result'])
            elif status['running'] and match['status'] == 'preparing':
                arena.store.update(db.matches, {'id': match['id']}, status='running', started=status.get('started_at', now))
            elif match['status'] == 'preparing' and now - match['prepared'] >= match['rules']['prepare_seconds']:
                async with arena.management:
                    current = arena.store.one(db.matches, id=match['id'])
                    if current['status'] == 'preparing':
                        arena.store.update(db.matches, {'id': match['id']}, status='cancelled')
                        arena.emit(match['id'], 'match_cancelled', {'reason': 'preparation_timeout'})
                        await arena.workers.close_match(match)
        except Exception:
            log.exception('Match supervision failed: %s', match['id'])
            failures = arena.failures.get(match['id'], 0) + 1
            arena.failures[match['id']] = failures
            if failures >= 3 and arena.store.one(db.matches, id=match['id'])['status'] not in ('finished', 'cancelled', 'aborted'):
                arena.store.update(db.matches, {'id': match['id']}, status='aborted')
                arena.emit(match['id'], 'match_aborted', {'reason': 'worker_unreachable'})
                try:
                    await arena.workers.close_match(match)
                except Exception:
                    pass

async def monitor(arena):
    while True:
        await check_matches(arena)
        await asyncio.sleep(1)
