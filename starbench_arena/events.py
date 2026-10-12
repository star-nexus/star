"""MCP Events draft adapter, isolated from the stable SDK tool transport."""
import asyncio
import base64
from datetime import datetime, timezone
import hashlib
import hmac
import http.client
import ipaddress
import json
import logging
import secrets
import socket
import ssl
import time
from urllib.parse import urlsplit
from mcp import types
from mcp.shared.exceptions import MCPError
from pydantic import Field
from sqlalchemy import select, or_, func
from . import store as db
from .api import principal

NAMES = {'match_ready': 'A match is prepared for Agent registration.',
         'match_invitation': 'A player invited your webpage BOSS to a match.',
         'turn_start': 'Your faction has a new turn; its public deadline is running.',
         'game_finished': 'A match has a durable server result.',
         'decision_due': 'A coalesced realtime decision reminder; read fresh observations.'}

def iso(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat().replace('+00:00', 'Z')

def signing_key(secret):
    if not isinstance(secret, str) or not secret.startswith('whsec_'):
        raise ValueError('Expected a whsec_ signing secret')
    key = base64.b64decode(secret[6:], validate=True)
    if not 24 <= len(key) <= 64:
        raise ValueError('Signing secret must contain 24–64 bytes')
    return key

class PublicHTTPSConnection(http.client.HTTPSConnection):
    def connect(self):
        addresses = socket.getaddrinfo(self.host, self.port, type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(row[4][0]).is_global for row in addresses):
            raise ValueError('Callback address is not public')
        # Connect to the validated address, never re-resolve through the HTTP client.
        sock = socket.create_connection(addresses[0][4][:2], timeout=self.timeout)
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)

class PermanentCallbackError(ValueError):
    pass

def deliver(url, secret, subscription_id, event_id, payload):
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.fragment or parsed.port not in (None, 443):
        raise ValueError('Callback must be public HTTPS on port 443 without credentials or a fragment')
    body = json.dumps(payload, separators=(',', ':'), ensure_ascii=False).encode()
    if len(body) > 262144:
        raise ValueError('Event is too large')
    stamp = str(int(time.time()))
    keys = secret if isinstance(secret, list) else [secret]
    signatures = ['v1,' + base64.b64encode(hmac.new(signing_key(key), event_id.encode() + b'.' + stamp.encode() + b'.' + body, hashlib.sha256).digest()).decode() for key in keys]
    connection = PublicHTTPSConnection(parsed.hostname, 443, timeout=10, context=ssl.create_default_context())
    try:
        connection.request('POST', parsed.path + ('?' + parsed.query if parsed.query else '') or '/', body=body,
            headers={'Content-Type': 'application/json', 'webhook-id': event_id, 'webhook-timestamp': stamp,
                     'webhook-signature': ' '.join(signatures), 'X-MCP-Subscription-Id': subscription_id})
        response = connection.getresponse()
        content = response.read(262145)
        if response.status in (410, 413):
            raise PermanentCallbackError('Callback permanently rejected delivery')
        if not 200 <= response.status < 300:
            raise ValueError('Callback did not acknowledge delivery')
        return json.loads(content) if content else {}
    finally:
        connection.close()

class EventList(types.Result):
    events: list[dict]

class SubscriptionResult(types.Result):
    id: str
    refresh_before: str = Field(alias='refreshBefore')
    cursor: str | None = None
    truncated: bool = False

class SubscribeParams(types.RequestParams):
    name: str
    arguments: dict = Field(default_factory=dict)
    delivery: dict
    cursor: str | None = None
    ttl_ms: int | None = Field(default=86400000, alias='ttlMs', ge=1000)

class UnsubscribeParams(types.RequestParams):
    name: str
    arguments: dict = Field(default_factory=dict)
    delivery: dict

def subscription_id(who, name, arguments, url):
    identity = json.dumps([who.subject, url, name, arguments], sort_keys=True)
    return 'sub_' + hashlib.sha256(identity.encode()).hexdigest()

class EventService:
    def __init__(self, arena, sender=deliver):
        self.arena = arena
        self.sender = sender
        self.next_decision = {}

    def install(self, mcp):
        server = mcp._lowlevel_server
        # SDK v2 sieves core capabilities before middleware returns. Keep the
        # draft Events capability at this isolated, wire-level extension seam.
        async def advertise_events(ctx, call_next):
            result = await call_next(ctx)
            if ctx.method == 'server/discover' and isinstance(result, dict):
                result = {**result, 'capabilities': {**result['capabilities'], 'events': {}}}
            return result
        server.middleware.append(advertise_events)
        async def list_events(ctx, params):
            self.arena.auth.invited(principal())
            return EventList(events=[{'name': name, 'description': description, 'delivery': ['webhook'],
                'inputSchema': {'type': 'object', 'properties': {'match_id': {'type': 'string'}},
                    'required': [] if name == 'match_invitation' else ['match_id'], 'additionalProperties': False},
                'payloadSchema': {'type': 'object', 'properties': {'match_id': {'type': 'string'}},
                    'required': ['match_id'], 'additionalProperties': True}}
                for name, description in NAMES.items()])
        async def subscribe(ctx, params):
            return await self.subscribe(principal(), params)
        async def unsubscribe(ctx, params):
            who = principal()
            sid = subscription_id(who, params.name, params.arguments, params.delivery.get('url'))
            with self.arena.store.transaction() as c:
                c.execute(db.subscriptions.delete().where(db.subscriptions.c.id == sid, db.subscriptions.c.owner == who.subject))
            return types.EmptyResult()
        server.add_request_handler('events/list', types.RequestParams, list_events)
        server.add_request_handler('events/subscribe', SubscribeParams, subscribe)
        server.add_request_handler('events/unsubscribe', UnsubscribeParams, unsubscribe)

    async def subscribe(self, who, params):
        self.arena.auth.invited(who)
        if params.name not in NAMES or set(params.arguments) - {'match_id'}:
            raise ValueError('Unknown event or filter')
        match_id = params.arguments.get('match_id', '*')
        if match_id == '*' and params.name != 'match_invitation':
            raise ValueError('match_id is required')
        if match_id != '*':
            self.arena.match_for(who, match_id)
        if params.delivery.get('mode') != 'webhook':
            raise ValueError('Only webhook delivery is supported')
        url, secret = params.delivery['url'], params.delivery['secret']
        signing_key(secret)
        sub_id = subscription_id(who, params.name, params.arguments, url)
        old = self.arena.store.one(db.subscriptions, id=sub_id)
        if not old and len(self.arena.store.all(db.subscriptions, owner=who.subject)) >= 64:
            raise ValueError('Subscription limit reached')
        challenge = secrets.token_urlsafe(32)
        try:
            reply = await asyncio.to_thread(self.sender, url, secret, sub_id,
                'verify_' + secrets.token_hex(16), {'type': 'verification', 'challenge': challenge})
            if not isinstance(reply.get('challenge'), str) or not secrets.compare_digest(reply['challenge'], challenge):
                raise ValueError('challenge_failed')
        except Exception as exc:
            raise MCPError(code=-32015, message='Callback verification failed',
                data={'reason': 'timeout' if isinstance(exc, TimeoutError) else 'challenge_failed'}) from None
        expires = time.time() + min(86400, (params.ttl_ms or 86400000) / 1000)
        # New subscriptions start now; refresh preserves the acknowledged cursor.
        with self.arena.store.transaction() as c:
            latest = c.execute(select(func.max(db.events.c.id))).scalar() or 0
            cursor = old['cursor'] if old else latest
            if params.cursor is not None:
                cursor = max(0, min(int(params.cursor), latest))
            if old:
                c.execute(db.subscriptions.update().where(db.subscriptions.c.id == sub_id).values(
                    secret=secret, expires=expires, cursor=cursor, next_attempt=0, failures=0, pending_event=None,
                    previous_secret=old['secret'] if old['secret'] != secret else old['previous_secret'],
                    rotation_until=time.time()+300 if old['secret'] != secret else old['rotation_until']))
            else:
                c.execute(db.subscriptions.insert().values(id=sub_id, owner=who.subject, match_id=match_id,
                    event=params.name, url=url, secret=secret, cursor=cursor, expires=expires, next_attempt=0, failures=0))
        return SubscriptionResult(id=sub_id, refreshBefore=iso(expires), cursor=str(cursor))

    async def tick(self):
        now = time.time()
        for match in self.arena.store.all(db.matches, status='running', mode='real_time'):
            if now >= self.next_decision.get(match['id'], 0):
                self.arena.emit(match['id'], 'decision_due', {'match_id': match['id']})
                self.next_decision[match['id']] = now + 5
        async def dispatch(subscription):
            if subscription['expires'] < now or subscription['next_attempt'] > now:
                return
            who = __import__('starbench_arena.auth', fromlist=['Principal']).Principal(subscription['owner'])
            try:
                self.arena.auth.invited(who)
                if subscription['match_id'] != '*':
                    self.arena.match_for(who, subscription['match_id'])
                query = select(db.events).where(db.events.c.id > subscription['cursor'],
                    db.events.c.kind == subscription['event'],
                    or_(db.events.c.owner == who.subject, db.events.c.owner.is_(None)))
                if subscription['match_id'] != '*':
                    query = query.where(db.events.c.match_id == subscription['match_id'])
                else:
                    query = query.where(db.events.c.owner == who.subject)
                if subscription['pending_event'] is not None:
                    query = query.where(db.events.c.id == subscription['pending_event'])
                order = db.events.c.id.desc() if subscription['event'] == 'decision_due' else db.events.c.id
                with self.arena.store.engine.connect() as c:
                    event = c.execute(query.order_by(order).limit(1)).mappings().first()
                if not event:
                    return
                event_id = 'evt_' + str(event['id']) + '_' + subscription['id']
                payload = {'eventId': event_id, 'name': subscription['event'], 'timestamp': iso(event['created']),
                    'data': {**event['body'], 'match_id': event['match_id']}, 'cursor': str(event['id'])}
                self.arena.store.update(db.subscriptions, {'id': subscription['id']}, pending_event=event['id'])
                keys = [subscription['secret'], subscription['previous_secret']] if subscription['previous_secret'] and (subscription['rotation_until'] or 0) > now else subscription['secret']
                await asyncio.to_thread(self.sender, subscription['url'], keys, subscription['id'], event_id, payload)
                self.arena.store.update(db.subscriptions, {'id': subscription['id']}, cursor=event['id'], failures=0, next_attempt=0, pending_event=None)
            except (PermanentCallbackError, PermissionError):
                self.arena.store.update(db.subscriptions, {'id': subscription['id']}, expires=0)
            except Exception:
                failures = subscription['failures'] + 1
                self.arena.store.update(db.subscriptions, {'id': subscription['id']}, failures=failures,
                    next_attempt=now + min(300, 2 ** min(failures, 8)),
                    expires=0 if failures >= 8 else subscription['expires'])

        gate = asyncio.Semaphore(8)
        async def bounded(subscription):
            async with gate:
                await dispatch(subscription)
        await asyncio.gather(*(bounded(s) for s in self.arena.store.all(db.subscriptions)))

    async def run(self):
        while True:
            try:
                await self.tick()
            except Exception:
                logging.getLogger('starbench.arena').exception('Event dispatcher will retry')
            await asyncio.sleep(1)
