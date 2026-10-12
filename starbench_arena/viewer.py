"""Reuse Three.js assets and ENV permission projection through a readonly relay."""
import asyncio
import hashlib
import json
from pathlib import Path
import secrets
import time
from fastapi import HTTPException, WebSocket
from fastapi.responses import Response, FileResponse
from websockets.asyncio.client import connect
from . import store as db
from .auth import Principal

CLIENT = Path(__file__).resolve().parents[1] / 'rotk_env/rendering/web/client'

def issue_ticket(arena, who, match_id):
    match = arena.match_for(who, match_id)
    if match['status'] not in ('preparing', 'running'):
        raise ValueError('Match has no live view')
    faction = next(f for f, p in match['players'].items() if p['owner'] == who.subject)
    token = secrets.token_urlsafe(32)
    expires = time.time() + 3600
    arena.store.insert(db.view_tickets, id=hashlib.sha256(token.encode()).hexdigest(), owner=who.subject,
                       match_id=match_id, faction=faction, expires=expires)
    return {'url': arena.settings.public_url.rstrip('/') + '/watch/#token=' + token,
            'expires_at': expires, 'faction': faction, 'can_control': False}

def install_viewer(app, arena):
    @app.get('/watch/')
    async def page():
        text = (CLIENT / 'index.html').read_text().replace('"/', '"/watch/')
        return Response(text, media_type='text/html', headers={'Referrer-Policy': 'no-referrer'})

    @app.get('/watch/{asset:path}')
    async def asset(asset: str):
        allowed = {'app.js', 'state.js', 'renderer.js', 'style.css'}
        if asset in allowed:
            text = (CLIENT / asset).read_text().replace("'/assets/", "'/watch/assets/").replace('${location.host}/stream', '${location.host}/watch/stream')
            # Do not reuse local renderer credentials in a public Arena tab.
            text = text.replace('star-view-token', 'star-arena-view-token')
            return Response(text, media_type='text/css' if asset.endswith('.css') else 'text/javascript')
        if asset == 'vendor/three.module.js':
            return FileResponse(CLIENT / 'node_modules/three/build/three.module.js')
        if asset == 'vendor/three.core.js':
            return FileResponse(CLIENT / 'node_modules/three/build/three.core.js')
        if asset.startswith('assets/'):
            # Same static art root used by the existing WebHost; no private files.
            from rotk_env.rendering.web.server import ASSETS
            path = (ASSETS / asset[7:]).resolve()
            if path.is_relative_to(ASSETS.resolve()) and path.is_file():
                return FileResponse(path)
        raise HTTPException(404)

    @app.websocket('/watch/stream')
    async def stream(ws: WebSocket):
        if ws.headers.get('origin') not in (None, arena.settings.public_url.rstrip('/')):
            await ws.close(code=1008); return
        await ws.accept()
        tasks = []
        try:
            hello = await asyncio.wait_for(ws.receive_json(), 5)
            token = hello.get('token', '')
            ticket = arena.store.one(db.view_tickets, id=hashlib.sha256(token.encode()).hexdigest())
            if not ticket or ticket['expires'] <= time.time():
                raise ValueError('View ticket expired')
            match = arena.match_for(Principal(ticket['owner']), ticket['match_id'])
            if match['status'] not in ('preparing', 'running'):
                raise ValueError('Match ended')
            target = await arena.workers.control(match['worker'], 'view/' + ticket['faction'])
            async with connect(target['url'], proxy=None, max_size=4*1024*1024) as upstream:
                await upstream.send(json.dumps({'kind': 'hello', 'token': target['token']}))
                async def outward():
                    async for message in upstream:
                        if time.time() >= ticket['expires']:
                            return
                        await ws.send_text(message)
                async def inward():
                    while True:
                        message = await ws.receive_text()
                        if len(message) > 8192:
                            return
                        # ENV's readonly ViewGrant remains the authority for commands.
                        await upstream.send(message)
                tasks = [asyncio.create_task(outward()), asyncio.create_task(inward())]
                await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        except Exception:
            pass
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            try:
                await ws.close(code=1000)
            except RuntimeError:
                pass
