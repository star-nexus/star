"""Transport-independent arena application service. ENV remains the rules engine."""
import asyncio
import hashlib
import json
import secrets
import subprocess
import time
from uuid import uuid4
from sqlalchemy import select, or_
from . import store as db
from .auth import Auth

TERMINAL = frozenset({'finished', 'cancelled', 'aborted'})
SIDE_ACTIONS = frozenset({'claim_units', 'release_units', 'list_team', 'broadcast_to_team',
    'read_team_messages', 'get_action_list', 'get_faction_state', 'end_turn', 'report_llm_stats'})
READ_ACTIONS = frozenset({'get_action_list', 'get_faction_state', 'list_team'})
PREP_ACTIONS = SIDE_ACTIONS - {'end_turn'}

def identifier(prefix):
    return prefix + '_' + uuid4().hex

def label(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 128:
        raise ValueError('Names and versions must contain 1–128 characters')
    return value

class Arena:
    def __init__(self, settings, store, workers):
        self.settings, self.store, self.workers = settings, store, workers
        self.auth = Auth(settings)
        self.management = asyncio.Lock()
        self.operation_locks = {}
        self.catalogs = {}
        self.failures = {}
        self.workers.on_event = self.receive_event
        self.env_revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()

    def match_for(self, principal, match_id):
        self.auth.invited(principal)
        match = self.store.one(db.matches, id=match_id)
        if not match or principal.subject not in [p['owner'] for p in match['players'].values()]:
            raise PermissionError('Match is not owned by this account')
        return dict(match)

    def agent_for(self, principal, agent_handle):
        self.auth.invited(principal)
        agent = self.store.one(db.agents, id=agent_handle)
        if not agent or agent['owner'] != principal.subject:
            raise PermissionError('Agent is not owned by this account')
        return dict(agent), self.match_for(principal, agent['match_id'])

    def public_match(self, match):
        return {k: v for k, v in dict(match).items() if k not in ('worker', 'seed')}

    def emit(self, match_id, kind, body, owner=None):
        self.store.insert(db.events, match_id=match_id, owner=owner, kind=kind, body=body, created=time.time())

    async def receive_event(self, agent, payload):
        # Persist first; the backend sends the transport ACK after this returns.
        if payload['type'] == 'turn_start':
            previous = self.store.all(db.events, match_id=agent['match_id'], owner=agent['owner'], kind='turn_start')
            if previous and previous[-1]['body'].get('turn_number') == payload.get('turn_number') and previous[-1]['body'].get('faction') == payload.get('faction'):
                return
        self.emit(agent['match_id'], payload['type'], payload, agent['owner'])

    async def register_entry(self, principal, name, version, details=None):
        self.auth.invited(principal)
        label(name); label(version)
        details = details or {}
        if len(json.dumps(details)) > 16384:
            raise ValueError('Entry metadata is too large')
        async with self.management:
            row = self.store.one(db.entries, owner=principal.subject, name=name, version=version)
            if row:
                if row['details'] != details:
                    raise ValueError('An entry version is immutable; publish a new version')
                return dict(row)
            row = dict(id=identifier('entry'), owner=principal.subject, name=name, version=version, details=details)
            self.store.insert(db.entries, **row)
            return row

    async def request_match(self, principal, entry_id, mode, kind='ranked', opponent_entry=None):
        self.auth.invited(principal)
        if mode not in ('real_time', 'turn_based') or kind not in ('ranked', 'private', 'boss'):
            raise ValueError('Invalid mode or match kind')
        entry = self.store.one(db.entries, id=entry_id, owner=principal.subject)
        if not entry:
            raise PermissionError('Entry is not owned by this account')
        if kind == 'boss':
            boss = self.store.one(db.entries, id=opponent_entry)
            if not boss or not boss['details'].get('boss') or boss['owner'] not in self.settings.boss_subjects:
                raise ValueError('Select a registered administrator-designated webpage BOSS entry')
        async with self.management:
            active = [m for m in self.store.all(db.matches) if m['status'] not in TERMINAL]
            if any(principal.subject in [p['owner'] for p in m['players'].values()] for m in active):
                raise ValueError('Finish or cancel the current match before requesting another')
            if kind == 'ranked':
                queued = [m for m in active if m['status'] == 'queued' and m['mode'] == mode and m['kind'] == kind]
                if queued:
                    match = dict(min(queued, key=lambda m: m['created']))
                    seat = 'shu' if 'wei' in match['players'] else 'wei'
                    players = dict(match['players'], **{seat: {'owner': principal.subject, 'entry': entry_id, 'ready': False}})
                    self.store.update(db.matches, {'id': match['id']}, players=players, status='preparing', prepared=time.time())
                    await self.prepare(match['id'])
                    return self.public_match(self.store.one(db.matches, id=match['id']))
            # Alternate first seats to balance queue and BOSS entries over time.
            seat = 'wei' if len(self.store.all(db.matches)) % 2 == 0 else 'shu'
            players = {seat: {'owner': principal.subject, 'entry': entry_id, 'ready': False}}
            row = dict(id=identifier('match'), mode=mode, kind=kind, status='queued', season=self.settings.season,
                created=time.time(), prepared=None, started=None, seed=secrets.randbelow(2**31),
                scenario=self.settings.scenario, players=players, worker=None,
                rules={'version': 'arena-v1', 'env_revision': self.env_revision, 'turn_seconds': self.settings.turn_seconds,
                       'prepare_seconds': self.settings.prepare_seconds, 'opponent_entry': opponent_entry})
            self.store.insert(db.matches, **row)
            if kind == 'boss':
                self.emit(row['id'], 'match_invitation', {'match_id': row['id'], 'mode': mode}, boss['owner'])
            return self.public_match(row)

    async def join_match(self, principal, match_id, entry_id):
        self.auth.invited(principal)
        entry = self.store.one(db.entries, id=entry_id, owner=principal.subject)
        if not entry:
            raise PermissionError('Entry is not owned by this account')
        async with self.management:
            row = self.store.one(db.matches, id=match_id)
            if not row or row['status'] != 'queued' or row['kind'] == 'ranked':
                raise ValueError('Only an open private or BOSS invitation can be joined')
            if row['kind'] == 'boss' and row['rules']['opponent_entry'] != entry_id:
                raise PermissionError('This invitation is for a different BOSS')
            if principal.subject in [p['owner'] for p in row['players'].values()]:
                raise ValueError('Cannot play both sides of a match')
            if any(m['status'] not in TERMINAL and principal.subject in [p['owner'] for p in m['players'].values()] for m in self.store.all(db.matches)):
                raise ValueError('Account already has an active match')
            seat = 'shu' if 'wei' in row['players'] else 'wei'
            players = dict(row['players'], **{seat: {'owner': principal.subject, 'entry': entry_id, 'ready': False}})
            self.store.update(db.matches, {'id': match_id}, players=players, status='preparing', prepared=time.time())
            await self.prepare(match_id)
            return self.public_match(self.store.one(db.matches, id=match_id))

    async def prepare(self, match_id):
        match = self.store.one(db.matches, id=match_id)
        try:
            worker = await self.workers.launch(match)
            self.store.update(db.matches, {'id': match_id}, worker=worker)
            self.emit(match_id, 'match_ready', {'match_id': match_id})
        except Exception:
            self.store.update(db.matches, {'id': match_id}, status='aborted')
            self.emit(match_id, 'match_aborted', {'reason': 'worker_preparation_failed'})
            raise

    def list_matches(self, principal):
        self.auth.invited(principal)
        result = []
        for m in self.store.all(db.matches):
            mine = principal.subject in [p['owner'] for p in m['players'].values()]
            target = self.store.one(db.entries, id=m['rules'].get('opponent_entry')) if m['kind'] == 'boss' else None
            if mine or (target and target['owner'] == principal.subject and m['status'] == 'queued'):
                result.append(self.public_match(m))
        return result[-100:]

    async def register_agents(self, principal, match_id, names):
        async with self.management:
            match = self.match_for(principal, match_id)
            if match['status'] not in ('preparing', 'running'):
                raise ValueError('Match is not available for registration')
            if not names or len(names) > self.settings.max_agents or len(set(names)) != len(names):
                raise ValueError('Supply distinct logical agent names within the configured limit')
            owned = self.store.all(db.agents, match_id=match_id, owner=principal.subject)
            if len(set(names) | {a['name'] for a in owned}) > self.settings.max_agents:
                raise ValueError('Agent limit exceeded')
            faction = next(f for f,p in match['players'].items() if p['owner'] == principal.subject)
            entry = self.store.one(db.entries, id=match['players'][faction]['entry'])
            registered = []
            for name in names:
                label(name)
                row = self.store.one(db.agents, match_id=match_id, owner=principal.subject, name=name)
                if not row:
                    row = dict(id=identifier('agent'), match_id=match_id, owner=principal.subject, faction=faction, name=name, generation=0)
                    self.store.insert(db.agents, **row)
                params = dict(faction=faction, provider=entry['details'].get('provider', 'self-reported'),
                    model_id=entry['details'].get('model', 'unspecified'), agent_id=row['id'],
                    version=entry['version'], base_url='', note=entry['name'])
                response = await self.workers.call(row, 'register_agent_info', params, 'arena-registration-v1')
                if not response.get('success'):
                    raise RuntimeError('ENV refused registration: ' + json.dumps(response))
                registered.append({'agent_handle': row['id'], 'name': name, 'faction': faction, 'registration': response})
            return registered

    async def ready_match(self, principal, match_id):
        async with self.management:
            match = self.match_for(principal, match_id)
            if match['status'] == 'running':
                return self.public_match(match)
            if match['status'] != 'preparing':
                raise ValueError('Match is not preparing')
            if not self.store.all(db.agents, match_id=match_id, owner=principal.subject):
                raise ValueError('Register at least one Agent before becoming ready')
            players = match['players']
            for player in players.values():
                if player['owner'] == principal.subject:
                    player['ready'] = True
            self.store.update(db.matches, {'id': match_id}, players=players)
            if len(players) == 2 and all(p['ready'] for p in players.values()):
                await self.workers.control(match['worker'], 'start')
                self.store.update(db.matches, {'id': match_id}, status='running', started=time.time())
                self.emit(match_id, 'match_started', {'match_id': match_id})
            return self.public_match(self.store.one(db.matches, id=match_id))

    async def action(self, principal, agent_handle, action, parameters=None, operation_id=None):
        agent, match = self.agent_for(principal, agent_handle)
        terminal = match['status'] in TERMINAL
        if not terminal:
            if match['status'] != 'running' and action not in PREP_ACTIONS:
                raise ValueError('Match is not running')
            if action not in SIDE_ACTIONS:
                catalog = self.catalogs.get(agent_handle)
                if catalog is None:
                    catalog = await self.workers.call(agent, 'get_action_list', {})
                    self.catalogs[agent_handle] = catalog
                if action not in catalog.get('names', []):
                    raise ValueError('Action is not in this ENV action catalog')
        parameters = dict(parameters or {})
        if parameters.get('faction', agent['faction']) != agent['faction'] or parameters.get('agent_id', agent_handle) != agent_handle:
            raise PermissionError('Action identity conflicts with assigned seat')
        if 'faction' in parameters or action in ('get_faction_state', 'end_turn', 'report_llm_stats'):
            parameters['faction'] = agent['faction']
        if 'agent_id' in parameters:
            parameters['agent_id'] = agent_handle
        if action in READ_ACTIONS and operation_id is None:
            if terminal:
                raise ValueError('Match has ended')
            return await self.workers.call(agent, action, parameters)
        if not isinstance(operation_id, str) or not 1 <= len(operation_id) <= 128:
            raise ValueError('A stable operation_id is required for every mutating action')
        fingerprint = hashlib.sha256(json.dumps([action, parameters], sort_keys=True, allow_nan=False).encode()).hexdigest()
        key = (agent_handle, operation_id)
        async with self.operation_locks.setdefault(key, asyncio.Lock()):
            record = self.store.one(db.operations, agent_id=agent_handle, id=operation_id)
            if record:
                if record['fingerprint'] != fingerprint:
                    raise ValueError('operation_conflict')
                if record['state'] == 'completed':
                    return record['result']
            if terminal:
                raise ValueError('Match has ended')
            if record is None:
                self.store.insert(db.operations, agent_id=agent_handle, id=operation_id,
                    fingerprint=fingerprint, state='pending', received=time.time())
            result = await self.workers.call(agent, action, parameters, operation_id)
            self.store.update(db.operations, {'agent_id': agent_handle, 'id': operation_id},
                              state='completed', result=result, completed=time.time())
            return result

    async def submit_actions(self, principal, agent_handle, actions):
        if not actions or len(actions) > 256:
            raise ValueError('Batch must have 1–256 items')
        self.agent_for(principal, agent_handle)
        outcomes = []
        for item in actions:
            try:
                result = await self.action(principal, agent_handle, item['action'], item.get('parameters'), item.get('operation_id'))
            except (KeyError, TypeError, ValueError, PermissionError) as exc:
                result = {'success': False, 'error': str(exc)}
            outcomes.append({'id': item.get('id') if isinstance(item, dict) else None, 'response': result})
        return {'results': outcomes, 'count': len(outcomes)}

    async def get_operation(self, principal, agent_handle, operation_id):
        agent, match = self.agent_for(principal, agent_handle)
        row = self.store.one(db.operations, agent_id=agent_handle, id=operation_id)
        if row and row['state'] == 'completed':
            return {'state': 'completed', 'result': row['result']}
        if match['status'] in TERMINAL:
            return {'state': 'unknown' if row else 'not_found'}
        result = await self.workers.call(agent, 'get_operation', {'operation_id': operation_id})
        if row and result.get('state') == 'completed':
            self.store.update(db.operations, {'agent_id': agent_handle, 'id': operation_id}, state='completed',
                              result=result['result'], completed=time.time())
        return result

    def read_events(self, principal, match_id, cursor=0):
        self.match_for(principal, match_id)
        with self.store.engine.connect() as c:
            rows = c.execute(select(db.events).where(db.events.c.match_id == match_id, db.events.c.id > cursor,
                or_(db.events.c.owner == principal.subject, db.events.c.owner.is_(None))).order_by(db.events.c.id).limit(100)).mappings().all()
        return {'events': [dict(r) for r in rows], 'cursor': rows[-1]['id'] if rows else cursor}

    async def report_usage(self, principal, agent_handle, metrics, operation_id):
        agent, _ = self.agent_for(principal, agent_handle)
        body = {'source': 'self_reported' if metrics else 'unavailable', 'metrics': metrics}
        if len(json.dumps(body)) > 65536:
            raise ValueError('Usage payload is too large')
        result = await self.action(principal, agent_handle, 'report_llm_stats',
            {'api_stats': metrics or {}, 'faction': agent['faction']}, operation_id)
        with self.store.transaction() as c:
            c.execute(db.usage.delete().where(db.usage.c.agent_id == agent_handle))
            c.execute(db.usage.insert().values(agent_id=agent_handle, body=body))
        return result

    async def resume_agent(self, principal, agent_handle):
        agent, match = self.agent_for(principal, agent_handle)
        if match['status'] in TERMINAL:
            raise ValueError('Match has ended')
        generation = agent['generation'] + 1
        self.store.update(db.agents, {'id': agent_handle}, generation=generation)
        return {'agent_handle': agent_handle, 'generation': generation, 'faction': agent['faction'],
                'match_id': agent['match_id']}

    async def cancel_match(self, principal, match_id):
        async with self.management:
            match = self.match_for(principal, match_id)
            if match['status'] not in ('queued', 'preparing'):
                raise ValueError('A running match must be resigned, not cancelled')
            self.store.update(db.matches, {'id': match_id}, status='cancelled')
            self.emit(match_id, 'match_cancelled', {})
            await self.workers.close_match(match)
            return {'status': 'cancelled'}

    async def resign(self, principal, match_id):
        match = self.match_for(principal, match_id)
        if match['status'] != 'running':
            raise ValueError('Match is not running')
        faction = next(f for f,p in match['players'].items() if p['owner'] == principal.subject)
        return await self.workers.control(match['worker'], 'resign/' + faction)
