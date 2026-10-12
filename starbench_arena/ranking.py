"""Deterministic online replay of durable settlements; paper analysis is untouched."""
from collections import defaultdict
from sqlalchemy import select
from . import store as db

def leaderboard(store, mode, season='s1'):
    if mode not in ('real_time', 'turn_based'):
        raise ValueError('Unknown leaderboard mode')
    ratings, weighted = defaultdict(lambda: 1000.), defaultdict(lambda: 1000.)
    counts, wins, ties = defaultdict(int), defaultdict(int), defaultdict(int)
    latest = {}
    with store.engine.connect() as c:
        records = c.execute(select(db.results).order_by(db.results.c.sequence)).mappings().all()
    for record in records:
        r = record['body']
        if not r.get('rated') or r['mode'] != mode or r['season'] != season:
            continue
        a, b = r['entries']['wei'], r['entries']['shu']
        score = .5 if r['is_tie'] else (1. if r['winner'] == 'wei' else 0.)
        multiplier = 1.
        if not r['is_tie'] and r['source'] == 'env':
            units = r.get('units_info', {}).get(r['winner'], {})
            total = units.get('total_units', 5) or 5
            remaining = units.get('surviving_units', 0)
            duration = r.get('game_duration_seconds', 3600)
            multiplier += .5 * remaining / total + .5 * (1 - min(duration / 3600, 1))
        for table, m in ((ratings, 1.), (weighted, multiplier)):
            expected = 1 / (1 + 10 ** ((table[b] - table[a]) / 400))
            delta = 32 * m * (score - expected)
            table[a] += delta
            table[b] -= delta
        for entry in (a, b):
            counts[entry] += 1
            latest[entry] = r['settled_at']
        if r['is_tie']:
            ties[a] += 1; ties[b] += 1
        else:
            wins[a if score == 1 else b] += 1
    rows = []
    for entry_id, rating in ratings.items():
        entry = store.one(db.entries, id=entry_id)
        rows.append({'entry_id': entry_id, 'name': entry['name'], 'version': entry['version'],
            'model': entry['details'].get('model'), 'model_source': 'self_reported',
            'elo': round(rating, 3), 'pw_elo': round(weighted[entry_id], 3),
            'games': counts[entry_id], 'wins': wins[entry_id], 'draws': ties[entry_id],
            'win_rate': wins[entry_id] / counts[entry_id], 'last_match_at': latest[entry_id]})
    rows.sort(key=lambda r: (-r['elo'], r['entry_id']))
    for index, row in enumerate(rows, 1):
        row['rank'] = index
    return {'mode': mode, 'season': season, 'rows': rows, 'primary': 'elo'}
