"""Worker supervision and persistent STAR client connections (no simulation code)."""
import asyncio
import json
import logging
import time
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import httpx
from protocol import AgentClient

class Workers:
    def __init__(self, settings):
        self.settings = settings
        self.clients = {}
        self.locks = {}
        self.http = httpx.AsyncClient(timeout=5, trust_env=False)
        self.on_event = None
        self.on_spawn = None
        self.processes = {}

    async def launch(self, match):
        with socket.socket() as sock:
            sock.bind(('0.0.0.0', 0))
            port = sock.getsockname()[1]
        token = secrets.token_urlsafe(32)
        config = dict(match_id=match['id'], mode=match['mode'], scenario=match['scenario'],
            seed=match['seed'], hub_url=self.settings.hub_url, port=port, token=token,
            bind=self.settings.worker_bind, turn_seconds=self.settings.turn_seconds)
        logdir = Path(os.getenv('ARENA_LOG_DIR', '.arena/logs'))
        logdir.mkdir(parents=True, exist_ok=True)
        with (logdir / (match['id'] + '.log')).open('ab') as log:
            process = subprocess.Popen([sys.executable, '-m', 'starbench_arena.worker'],
                stdin=subprocess.PIPE, stdout=log, stderr=log, start_new_session=True)
        process.stdin.write((json.dumps(config) + '\n').encode())
        process.stdin.close()
        worker = {'url': f'http://{self.settings.worker_host}:{port}', 'token': token, 'pid': process.pid}
        self.processes[match['id']] = process
        if self.on_spawn:
            self.on_spawn(match['id'], worker)
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError('Worker exited during preparation; inspect match log')
            try:
                await self.control(worker, 'status')
                return worker
            except (httpx.HTTPError, OSError) as exc:
                logging.getLogger('starbench.arena').debug('Worker readiness: %s', type(exc).__name__)
                await asyncio.sleep(.1)
        process.terminate()
        await asyncio.to_thread(process.wait, 10)
        raise RuntimeError('Worker preparation timed out')

    async def control(self, worker, command):
        response = await self.http.request('GET' if command == 'status' else 'POST',
            worker['url'] + '/' + command, headers={'Authorization': 'Bearer ' + worker['token']})
        response.raise_for_status()
        return response.json()

    async def client(self, agent):
        key = agent['id']
        async with self.locks.setdefault(key, asyncio.Lock()):
            client = self.clients.get(key)
            if client and client.websocket and client.websocket.close_code is None:
                return client
            if client:
                await client.disconnect()
            client = AgentClient(self.settings.hub_url, agent['match_id'], key, connection_options={'proxy': None})
            async def event(envelope):
                payload = envelope.get('payload') or {}
                if payload.get('type') in ('turn_start', 'game_end_notification'):
                    if self.on_event:
                        await self.on_event(agent, payload)
                    if payload['type'] == 'turn_start':
                        await client.send_action('turn_start_ack', {}, expect_outcome=False)
            client.add_hub_listener('message', event)
            await client.connect()
            self.clients[key] = client
            return client

    async def call(self, agent, action, parameters, operation_id=None):
        client = await self.client(agent)
        return await client.call(action, parameters, operation_id=operation_id)

    async def close_match(self, match):
        for key, client in list(self.clients.items()):
            if client.env_id == match['id']:
                await client.disconnect()
                del self.clients[key]
        if match.get('worker'):
            try:
                await self.control(match['worker'], 'stop')
            except (httpx.ConnectError, httpx.ConnectTimeout):
                # The private loopback endpoint no longer exists. Never signal a
                # persisted PID: after restart that PID could belong to another app.
                pass
        process = self.processes.pop(match['id'], None)
        if process is not None:
            try:
                await asyncio.to_thread(process.wait, 5)
            except subprocess.TimeoutExpired:
                process.terminate()
                await asyncio.to_thread(process.wait, 5)

    async def close(self):
        for client in self.clients.values():
            await client.disconnect()
        await self.http.aclose()
