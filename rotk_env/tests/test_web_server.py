"""Real HTTP/WebSocket lifecycle and slow-viewer isolation over the Rust owner."""
import asyncio
import json

import httpx
import pytest
pytest.importorskip('star_rust_runtime')
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed, InvalidStatus

from rotk_env.rendering.commands import ViewGrant
from rotk_env.rendering.web.server import WebHost, Viewer, CLIENT
from rotk_env.runtime.session import NativeSession
from rotk_env.prefabs.config import Faction, PlayerType
from rotk_env.tests.render_fixtures import frozen


@pytest.fixture
async def host(frozen):
    if not (CLIENT / 'node_modules/three/build/three.module.js').exists():
        pytest.skip('Run npm ci in the Web client before Web integration tests')
    scene = NativeSession(renderer='web', scenario='chibi-small', seed=42,
        players={Faction.WEI: PlayerType.HUMAN, Faction.SHU: PlayerType.HUMAN})
    host = WebHost(scene, port=0, grants={'wei-test': ViewGrant('wei', True),
        'shu-test': ViewGrant('shu', True), 'view-test': ViewGrant('spectator')})
    try:
        await host.start(clock=False)
        yield host
    finally:
        await host.close()


async def receive(socket, kind):
    async with asyncio.timeout(3):
        while True:
            packet = json.loads(await socket.recv())
            if packet['kind'] == kind:
                return packet


async def hello(socket, token):
    await socket.send(json.dumps(dict(kind='hello', token=token)))
    return await receive(socket, 'snapshot')


def endpoint(host):
    return f'ws://127.0.0.1:{host.port}/stream'


async def test_http_serves_local_modules_assets_and_rejects_path_escape(host):
    async with httpx.AsyncClient(base_url=host.url, trust_env=False) as client:
        for path, mime in [('/', 'text/html'), ('/app.js', 'javascript'),
                           ('/batches.js', 'javascript'), ('/motion.js', 'javascript'),
                           ('/performance.js', 'javascript'),
                           ('/ranges.js', 'javascript'),
                           ('/vendor/three.module.js', 'javascript'),
                           ('/vendor/three.core.js', 'javascript'),
                           ('/assets/texture/units/wei/infantry.png', 'image/png')]:
            response = await client.get(path)
            assert response.status_code == 200 and mime in response.headers['content-type']
        for path in ('/assets/%2e%2e/%2e%2e/README.md', '/assets/.configs.toml', '/server.py', '/unknown'):
            assert (await client.get(path)).status_code == 404


async def test_authentication_origin_and_granted_view_cannot_be_overridden(host):
    async with connect(endpoint(host)) as socket:
        await socket.send(json.dumps(dict(kind='hello', token='bad', view='spectator')))
        with pytest.raises(ConnectionClosed) as error:
            await socket.recv()
        assert error.value.rcvd.code == 1008
    with pytest.raises(InvalidStatus):
        async with connect(endpoint(host), origin='https://untrusted.example'):
            pass
    async with connect(endpoint(host), origin=host.url.rstrip('/')) as socket:
        await socket.send(json.dumps(dict(kind='hello', token='wei-test', view='spectator')))
        welcome = await receive(socket, 'welcome'); snapshot = await receive(socket, 'snapshot')
        assert welcome['view'] == 'wei' and snapshot['view'] == 'wei'
        assert len(snapshot['units']) == 5 and all(u['faction'] == 'wei' for u in snapshot['units'])


async def test_commands_ack_fresh_state_and_reconnect_baseline(host):
    async with connect(endpoint(host)) as socket:
        initial = await hello(socket, 'wei-test'); uid = initial['units'][0]['id']
        for n in range(2):
            await socket.send(json.dumps(dict(kind='command', id=str(n), epoch=initial['epoch'],
                command='wait', parameters={'unit_id': uid})))
            reply = await receive(socket, 'command_result'); assert reply['success']
        assert host.session.renderer.model.snapshot('wei')['units'][0]['ap'] == 0
        await socket.send(json.dumps(dict(kind='command', id='turn', epoch=initial['epoch'], command='end_turn')))
        assert (await receive(socket, 'command_result'))['success']
        assert host.session.renderer.model.snapshot('wei')['units'][0]['ap'] == 2
        await socket.send(json.dumps(dict(kind='resync')))
        fresh = await receive(socket, 'snapshot')
        assert fresh['epoch'] == initial['epoch']
    async with connect(endpoint(host)) as socket:
        fresh = await hello(socket, 'wei-test')
        assert fresh['kind'] == 'snapshot' and fresh['units'][0]['ap'] == 2
        assert fresh['hud']['current_player'] == 'shu'


async def test_spectator_stale_epoch_and_malformed_messages_leave_host_alive(host):
    async with connect(endpoint(host)) as socket:
        baseline = await hello(socket, 'view-test')
        await socket.send(json.dumps(dict(kind='command', id='turn', epoch=baseline['epoch'], command='end_turn')))
        assert not (await receive(socket, 'command_result'))['success']
        assert host.session.runtime.host_status()['current_player'] == 'wei'
    async with connect(endpoint(host)) as socket:
        await hello(socket, 'wei-test')
        await socket.send(json.dumps(dict(kind='command', id='stale', epoch='0', command='end_turn')))
        assert not (await receive(socket, 'command_result'))['success']
        await socket.send('[]')
        with pytest.raises(ConnectionClosed):
            while True: await socket.recv()
    assert host.session.failure is None and not host._pump_task.done()


async def test_stalled_network_sender_does_not_stop_native_clock(host):
    class StalledSocket:
        def __init__(self): self.closed = False
        async def send(self, data): await asyncio.Event().wait()
        async def close(self, *args): self.closed = True
    stalled = StalledSocket(); viewer = Viewer(stalled, ViewGrant('wei', True))
    host.viewers.add(viewer)
    host.session.runtime.start_clock(1/60)
    task = asyncio.create_task(host._send(viewer))
    initial_tick = host.session.renderer.model.tick
    try:
        await asyncio.wait_for(task, 3)
        assert stalled.closed and host.session.renderer.model.tick > initial_tick + 30
        assert viewer.mailbox.resyncs > 5 and host.session.failure is None
    finally:
        host.viewers.discard(viewer); viewer.mailbox.close(); task.cancel()


async def test_viewer_limit_and_command_rate_are_bounded(host):
    host.max_viewers = 1
    async with connect(endpoint(host)) as first:
        snapshot = await hello(first, 'wei-test')
        async with connect(endpoint(host)) as second:
            with pytest.raises(ConnectionClosed) as error: await second.recv()
            assert error.value.rcvd.code == 1013
        for _ in range(20):
            try: await first.send(json.dumps(dict(kind='resync')))
            except ConnectionClosed: break
        with pytest.raises(ConnectionClosed) as error:
            while True: await first.recv()
        assert error.value.rcvd.code == 1008
    assert snapshot['view'] == 'wei' and host.session.failure is None


async def selected_packet(socket, uid):
    async with asyncio.timeout(3):
        while True:
            packet = json.loads(await socket.recv())
            if packet.get('kind') in ('snapshot', 'delta') and (packet.get('selection') or {}).get('unit_id') == uid:
                return packet


async def test_display_selection_is_connection_local_read_only_and_refreshes_after_commands(host):
    before = host.session.runtime.export_state()
    async with connect(endpoint(host)) as first, connect(endpoint(host)) as second:
        snapshot = await hello(first, 'wei-test'); await hello(second, 'wei-test')
        uid = snapshot['units'][0]['id']
        await first.send(json.dumps(dict(kind='selection', epoch=snapshot['epoch'], unit_id=uid)))
        packet = await selected_packet(first, uid)
        assert packet['selection']['movement'] and packet['selection']['attack']
        assert host.session.runtime.export_state() == before
        await second.send(json.dumps(dict(kind='resync')))
        assert (await receive(second, 'snapshot'))['selection'] is None
        destination = packet['selection']['movement'][0]
        await first.send(json.dumps(dict(kind='command', id='move', epoch=snapshot['epoch'], command='move',
                                         parameters={'unit_id': uid, 'position': destination})))
        assert (await receive(first, 'command_result'))['success']
        assert (await selected_packet(first, uid))['selection']['movement'] == []
        await first.send(json.dumps(dict(kind='selection', epoch=snapshot['epoch'], unit_id=None)))
        assert (await selected_packet(first, None))['selection'] is None


async def test_spectator_selection_and_hidden_enemy_or_stale_requests(host):
    async with connect(endpoint(host)) as socket:
        snapshot = await hello(socket, 'view-test')
        enemy = next(u['id'] for u in snapshot['units'] if u['faction'] == 'shu')
        await socket.send(json.dumps(dict(kind='selection', epoch=snapshot['epoch'], unit_id=enemy)))
        assert (await selected_packet(socket, enemy))['selection']['attack']
    async with connect(endpoint(host)) as socket:
        snapshot = await hello(socket, 'wei-test')
        await socket.send(json.dumps(dict(kind='selection', epoch=snapshot['epoch'], unit_id=enemy)))
        assert (await selected_packet(socket, None))['selection'] is None
        await socket.send(json.dumps(dict(kind='selection', epoch='0', unit_id=snapshot['units'][0]['id'])))
        with pytest.raises(ConnectionClosed) as error:
            while True: await socket.recv()
        assert error.value.rcvd.code == 1008
    assert host.session.failure is None
