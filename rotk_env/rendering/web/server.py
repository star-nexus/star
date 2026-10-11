"""Bounded, authenticated display transport; never an Agent protocol endpoint."""

import asyncio
from contextlib import suppress
from dataclasses import dataclass, field
import json
import mimetypes
from pathlib import Path
import secrets
import time
from urllib.parse import unquote, urlsplit

from websockets.asyncio.server import serve
from websockets.datastructures import Headers
from websockets.exceptions import ConnectionClosed
from websockets.http11 import Response

from framework.presentation import SnapshotMailbox
from rotk_env.rendering.commands import CommandGateway, ViewGrant
from rotk_env.rendering.projection import diff_snapshot
from rotk_env.runtime.authority import AuthorityRuntime

CLIENT = Path(__file__).with_name('client')
ASSETS = Path(__file__).resolve().parents[2] / 'assets'


@dataclass(eq=False)
class Viewer:
    socket: object
    grant: ViewGrant
    mailbox: SnapshotMailbox = field(default_factory=SnapshotMailbox)
    replies: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=16))
    wake: asyncio.Event = field(default_factory=asyncio.Event)
    previous: dict | None = None
    selected_id: str | None = None

    def publish(self, snapshot):
        self.mailbox.offer(diff_snapshot(self.previous, snapshot), snapshot)
        self.previous = snapshot
        self.wake.set()


class WebHost:
    def __init__(self, session, *, grants=None, host='127.0.0.1', port=8765,
                 hub=None, display_hz=20, max_viewers=16):
        if session.renderer.renderer_id != 'threejs':
            raise ValueError('WebHost requires the web renderer')
        if not isinstance(session.runtime, AuthorityRuntime):
            raise ValueError('WebHost requires the single authority executor')
        if not 1 <= display_hz <= 60 or max_viewers < 1:
            raise ValueError('Invalid Web display limits')
        self.session, self.hub = session, hub
        self.gateway = CommandGateway(session)
        self.host, self.port = host, port
        self.display_hz, self.max_viewers = display_hz, max_viewers
        self.grants = dict(grants) if grants is not None else {
            secrets.token_urlsafe(32): ViewGrant(f, kind == 'human')
            for f, kind in session.renderer.player_types.items()}
        if grants is None:
            self.grants[secrets.token_urlsafe(32)] = ViewGrant('spectator')
        self.viewers = set()
        self._server = self._pump_task = None
        self._pending_connections = 0

    @property
    def url(self):
        address = '127.0.0.1' if self.host in ('0.0.0.0', '::') else self.host
        return f'http://{address}:{self.port}/'

    async def start(self, *, clock=True):
        if self._server is not None:
            raise RuntimeError('WebHost already started')
        if not (CLIENT / 'node_modules/three/build/three.module.js').exists():
            raise RuntimeError(f'Install Web assets first: npm ci --prefix {CLIENT}')
        origins = [None, f'http://127.0.0.1:{self.port}', f'http://localhost:{self.port}',
                   f'http://{self.host}:{self.port}']
        self._server = await serve(self._connect, self.host, self.port, origins=origins,
            process_request=self._http, max_size=8192, max_queue=8,
            write_limit=32768, open_timeout=5, close_timeout=1)
        self.port = self._server.sockets[0].getsockname()[1]
        # Port 0 is useful for tests. Apply the actual browser origins as well.
        origins.extend([f'http://127.0.0.1:{self.port}', f'http://localhost:{self.port}',
                        f'http://{self.host}:{self.port}'])
        if clock:
            self.session.runtime.start_clock(1/60)
        self._pump_task = asyncio.create_task(self._pump(), name='star-web-publications')
        return self

    def _http(self, connection, request):
        path = unquote(urlsplit(request.path).path)
        if path == '/stream':
            return None
        files = {'/': CLIENT / 'index.html', '/index.html': CLIENT / 'index.html',
                 '/style.css': CLIENT / 'style.css', '/app.js': CLIENT / 'app.js',
                 '/renderer.js': CLIENT / 'renderer.js', '/state.js': CLIENT / 'state.js',
                 '/hex.js': CLIENT / 'hex.js',
                 '/performance.js': CLIENT / 'performance.js',
                 '/batches.js': CLIENT / 'batches.js', '/motion.js': CLIENT / 'motion.js',
                 '/ranges.js': CLIENT / 'ranges.js',
                 '/vendor/three.module.js': CLIENT / 'node_modules/three/build/three.module.js',
                 '/vendor/three.core.js': CLIENT / 'node_modules/three/build/three.core.js'}
        target = files.get(path)
        if path.startswith('/assets/'):
            candidate = (ASSETS / path[len('/assets/'):]).resolve()
            if candidate.is_relative_to(ASSETS) and candidate.suffix.lower() in ('.png', '.jpg', '.otf'):
                target = candidate
        if target is None or not target.is_file():
            return Response(404, 'Not Found', Headers({'Content-Type': 'text/plain'}), b'Not found')
        data = target.read_bytes()
        mime = mimetypes.guess_type(target.name)[0] or 'application/octet-stream'
        headers = Headers({'Content-Type': mime, 'Content-Length': str(len(data)),
            'Cache-Control': 'no-cache', 'X-Content-Type-Options': 'nosniff',
            'Content-Security-Policy': "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self'; img-src 'self' data:; connect-src 'self'"})
        return Response(200, 'OK', headers, data)

    async def _connect(self, socket):
        if len(self.viewers) + self._pending_connections >= self.max_viewers:
            await socket.close(1013, 'Viewer limit reached')
            return
        self._pending_connections += 1
        viewer = sender = None
        pending = True
        try:
            if urlsplit(socket.request.path).path != '/stream':
                await socket.close(1008, 'Unknown endpoint')
                return
            hello = json.loads(await asyncio.wait_for(socket.recv(), 5))
            grant = self.grants.get(hello.get('token')) if isinstance(hello, dict) else None
            if not grant or hello.get('kind') != 'hello':
                await socket.close(1008, 'Invalid view credential')
                return
            self._pending_connections -= 1
            pending = False
            viewer = Viewer(socket, grant)
            self.viewers.add(viewer)
            viewer.replies.put_nowait(dict(kind='welcome', view=grant.view, can_control=grant.can_control))
            viewer.publish(self.session.renderer.model.snapshot(grant.view))
            sender = asyncio.create_task(self._send(viewer))
            allowance, updated = 12.0, time.monotonic()
            async for raw in socket:
                now = time.monotonic()
                allowance = min(12.0, allowance + (now-updated)*8)
                updated = now
                if allowance < 1:
                    await socket.close(1008, 'Command rate exceeded')
                    break
                allowance -= 1
                request = json.loads(raw)
                if not isinstance(request, dict):
                    raise ValueError('Message must be an object')
                if request.get('kind') == 'resync':
                    viewer.previous = None
                    viewer.publish(self._snapshot(viewer))
                    continue
                if request.get('kind') == 'selection':
                    self.session.refresh()
                    uid = request.get('unit_id')
                    if (str(request.get('epoch')) != str(self.session.controls.epoch) or
                            (uid is not None and (not isinstance(uid, str) or not uid.isascii()
                            or not uid.isdecimal() or len(uid) > 20 or int(uid) >= 2**64))):
                        raise ValueError('Invalid display selection')
                    # Selection is read-only. The projection accepts only units
                    # visible to this grant and never adds enemy private ranges.
                    viewer.selected_id = uid
                    viewer.publish(self._snapshot(viewer))
                    continue
                if request.get('kind') != 'command' or not isinstance(request.get('id'), str) or len(request['id']) > 64:
                    raise ValueError('Invalid command envelope')
                try:
                    result = self.gateway.dispatch(grant, request)
                    accepted = result is not None and result is not False
                    if isinstance(result, dict):
                        accepted = result.get('success', result.get('status', '') == 'success')
                    error = (result.get('message') if isinstance(result, dict) else None)
                    reply = dict(kind='command_result', id=request['id'], success=bool(accepted),
                                 error=None if accepted else error or 'The action failed or missed')
                except (ValueError, TypeError, PermissionError) as exc:
                    reply = dict(kind='command_result', id=request['id'], success=False, error=str(exc))
                # Reliable command results are separate from disposable frames.
                # A slow client is disconnected before this bounded queue fills.
                viewer.replies.put_nowait(reply)
                viewer.publish(self._snapshot(viewer))
        except (ConnectionClosed, asyncio.TimeoutError):
            pass
        except (ValueError, TypeError, asyncio.QueueFull):
            await socket.close(1008, 'Invalid message or slow receiver')
        finally:
            if pending:
                self._pending_connections -= 1
            if viewer:
                self.viewers.discard(viewer)
                viewer.mailbox.close()
            if sender:
                sender.cancel()
                with suppress(asyncio.CancelledError):
                    await sender

    async def _send(self, viewer):
        try:
            while True:
                await viewer.wake.wait()
                viewer.wake.clear()
                while not viewer.replies.empty():
                    await asyncio.wait_for(viewer.socket.send(json.dumps(viewer.replies.get_nowait())), 2)
                packet = viewer.mailbox.take()
                if packet is not None:
                    await asyncio.wait_for(viewer.socket.send(json.dumps(packet, allow_nan=False)), 2)
        except (ConnectionClosed, asyncio.TimeoutError):
            await viewer.socket.close(1013, 'Display receiver stalled')

    def _snapshot(self, viewer, baseline=None):
        model = self.session.renderer.model
        baseline = baseline if baseline is not None else model.snapshot(viewer.grant.view)
        return model.with_selection(baseline, viewer.selected_id)

    async def _pump(self):
        next_display = 0
        while True:
            # Drain all native publications; rendering packets alone may coalesce.
            self.session.refresh()
            if self.hub:
                self.hub.update(time.time())
            now = time.monotonic()
            if self.viewers and now >= next_display:
                views = {v.grant.view for v in self.viewers}
                snapshots = {view: self.session.renderer.model.snapshot(view) for view in views}
                for viewer in tuple(self.viewers):
                    viewer.publish(self._snapshot(viewer, snapshots[viewer.grant.view]))
                next_display = now + 1/self.display_hz
            await asyncio.sleep(1/60)

    async def wait(self):
        await self._pump_task

    async def close(self):
        failure = None
        if self._pump_task:
            self._pump_task.cancel()
            try:
                await self._pump_task
            except asyncio.CancelledError:
                pass
            except Exception as exc:
                failure = exc
            self._pump_task = None
        try:
            if self._server:
                self._server.close()
                await self._server.wait_closed()
                self._server = None
        finally:
            try:
                if self.hub:
                    self.hub.close()
            finally:
                self.session.close()
        if failure:
            raise failure
