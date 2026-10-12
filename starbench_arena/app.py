import asyncio
from contextlib import asynccontextmanager
import json
import logging
import time
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import ValidationError
from .config import Settings
from .store import Store
from . import store as db
from .backend import Workers
from .service import Arena
from .api import build_tools, http_principal

log = logging.getLogger('starbench.arena')

def create_app(settings=None, store=None, workers=None):
    settings = (settings or Settings()).validate()
    store = store or Store(settings.database_url)
    store.initialize()
    arena = Arena(settings, store, workers or Workers(settings))
    mcp, registry = build_tools(arena)
    from .events import EventService
    events_service = EventService(arena)
    events_service.install(mcp)
    mcp_app = mcp.streamable_http_app(stateless_http=True, json_response=True,
        host=settings.public_url.split('://')[-1].split('/')[0].split(':')[0])

    @asynccontextmanager
    async def lifespan(app):
        with store.gateway_lease():
            from .policy import monitor
            task = asyncio.create_task(monitor(arena))
            event_task = asyncio.create_task(events_service.run())
            async with mcp_app.router.lifespan_context(mcp_app):
                try:
                    yield
                finally:
                    task.cancel()
                    event_task.cancel()
                    await asyncio.gather(task, event_task, return_exceptions=True)
                    await arena.workers.close()
    app = FastAPI(title='StarBench Arena', lifespan=lifespan)
    app.state.arena = arena
    app.state.mcp = mcp
    app.state.events = events_service

    async def authenticate(header):
        if not header.startswith('Bearer '):
            raise HTTPException(401, 'Bearer token required')
        try:
            return await arena.auth.principal(header[7:])
        except Exception:
            raise HTTPException(401, 'Invalid credentials') from None

    @app.get('/health')
    async def health():
        with store.engine.connect() as c:
            from sqlalchemy import text
            c.execute(text('SELECT 1'))
        return {'status': 'ok'}

    @app.post('/api/{tool}')
    async def invoke(tool: str, request: Request):
        who = await authenticate(request.headers.get('authorization', ''))
        if tool not in registry:
            raise HTTPException(404)
        payload = await request.body()
        if len(payload) > 1024 * 1024:
            raise HTTPException(413)
        context = http_principal.set(who)
        try:
            return await registry[tool](**json.loads(payload or b'{}'))
        except PermissionError as exc:
            raise HTTPException(403, str(exc)) from None
        except (ValueError, TypeError, ValidationError) as exc:
            raise HTTPException(400, str(exc)) from None
        finally:
            http_principal.reset(context)

    @app.websocket('/ws/metaverse/env/{match_id}/agent/{agent_id}')
    async def native_socket(ws: WebSocket, match_id: str, agent_id: str):
        try:
            bearer = ws.headers.get('authorization', '')
            who = await authenticate(bearer)
            expires_at = (await arena.auth.claims(bearer[7:]))['exp']
            agent, match = arena.agent_for(who, agent_id)
            if match['id'] != match_id:
                raise PermissionError('Wrong match')
            # Explicit resume_agent obtains the generation; reconnect does not change it.
            generation = int(ws.headers.get('x-arena-generation', '0'))
            if generation != agent['generation']:
                raise PermissionError('Controller was superseded')
        except (HTTPException, PermissionError, ValueError):
            await ws.close(code=1008)
            return
        await ws.accept()
        async def send(kind, payload):
            await ws.send_json({'type': kind, 'sender': {'type': 'hub'},
                'recipient': {'type': 'agent', 'id': agent_id}, 'timestamp': time.time(), 'payload': payload})
        await send('connect', 'Authenticated Arena connection')
        cursor = 0
        async def push_events():
            nonlocal cursor
            while True:
                if time.time() >= expires_at or store.one(db.agents, id=agent_id)['generation'] != generation:
                    await ws.close(code=1008)
                    return
                data = arena.read_events(who, match_id, cursor)
                for event in data['events']:
                    kind = 'game_end_notification' if event['kind'] == 'game_finished' else event['kind']
                    await send('message', {**event['body'], 'type': kind})
                cursor = data['cursor']
                await asyncio.sleep(.25)
        events_task = asyncio.create_task(push_events())
        try:
            while True:
                message = await ws.receive_json()
                if time.time() >= expires_at or store.one(db.agents, id=agent_id)['generation'] != generation:
                    await ws.close(code=1008)
                    return
                if not isinstance(message, dict) or not isinstance(message.get('payload', {}), (dict, type(None))):
                    await ws.close(code=1008)
                    return
                sender = message.get('sender', {})
                if sender != {'type': 'agent', 'id': agent_id}:
                    await ws.close(code=1008)
                    return
                if message.get('type') == 'heartbeat':
                    await send('heartbeat', {})
                    continue
                if message.get('recipient') != {'type': 'env', 'id': match_id}:
                    await ws.close(code=1008)
                    return
                payload = message.get('payload') or {}
                request_id = payload.get('id')
                try:
                    if payload.get('type') == 'action_batch':
                        result = await arena.submit_actions(who, agent_id, payload.get('actions', []))
                    elif payload.get('type') == 'action':
                        action = payload.get('action')
                        if action == 'turn_start_ack':
                            result = {'success': True}
                        elif action == 'register_agent_info':
                            params = payload.get('parameters') or {}
                            if params.get('faction', agent['faction']) != agent['faction'] or params.get('agent_id', agent_id) != agent_id:
                                raise PermissionError('Registration identity conflicts with assigned seat')
                            result = (await arena.register_agents(who, match_id, [agent['name']]))[0]['registration']
                        elif action == 'get_operation':
                            result = await arena.get_operation(who, agent_id, payload.get('parameters', {}).get('operation_id'))
                        else:
                            result = await arena.action(who, agent_id, action, payload.get('parameters'), payload.get('operation_id'))
                    else:
                        raise ValueError('Only STAR action, action_batch and heartbeat messages are accepted')
                except (ValueError, PermissionError) as exc:
                    result = {'success': False, 'error': str(exc)}
                await send('message', {'type': 'outcome', 'id': request_id, 'outcome': result, 'outcome_type': 'json'})
        except (WebSocketDisconnect, ValueError):
            pass
        finally:
            events_task.cancel()
            await asyncio.gather(events_task, return_exceptions=True)

    @app.get('/', response_class=HTMLResponse)
    async def index():
        from pathlib import Path
        return Path(__file__).with_name('leaderboard.html').read_text()

    @app.get('/leaderboard/{mode}')
    async def ranking(mode: str, season: str = 's1'):
        from .ranking import leaderboard
        try:
            return leaderboard(store, mode, season)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from None

    from .viewer import install_viewer
    install_viewer(app, arena)
    app.mount('/', mcp_app)
    return app
