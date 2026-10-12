"""Real private HUB + independent Rust Worker + HTTP/MCP/native gateway integration."""
import os
from pathlib import Path
import socket
import subprocess
import time
import urllib.request
import pytest
from fastapi.testclient import TestClient
from starbench_arena.app import create_app
from starbench_arena.config import Settings
from starbench_arena.store import Store

@pytest.fixture(scope='module')
def hub(tmp_path_factory):
    root = Path(os.getenv('STAR_ARENA_HUB_PATH', str(Path.cwd().parent / 'GameServer')))
    python = root / '.venv/bin/python'
    if not python.exists():
        pytest.skip('Set STAR_ARENA_HUB_PATH to the external GameServer checkout with its runtime installed')
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]
    with (tmp_path_factory.mktemp('hub') / 'hub.log').open('wb') as log:
        process = subprocess.Popen([str(python), '-m', 'uvicorn', 'gameserver.main:app', '--host', '127.0.0.1', '--port', str(port)], cwd=root, stdout=log, stderr=log)
    try:
        for _ in range(100):
            if process.poll() is not None: pytest.fail('HUB exited')
            try:
                urllib.request.urlopen(f'http://127.0.0.1:{port}/', timeout=.2).close()
                break
            except OSError: time.sleep(.05)
        else: pytest.fail('HUB did not start')
        yield f'ws://127.0.0.1:{port}/ws/metaverse'
    finally:
        process.terminate(); process.wait(timeout=10)

@pytest.mark.parametrize('mode', ['turn_based', 'real_time'])
def test_live_match_mcp_and_native(hub, mode, tmp_path):
    settings = Settings(development=True, hub_url=hub, turn_seconds=30)
    app = create_app(settings, Store('sqlite:///' + str(tmp_path / 'arena.db')))
    headers = lambda owner: {'Authorization': 'Bearer dev:' + owner}
    with TestClient(app, base_url=settings.public_url) as client:
        def call(owner, tool, **args):
            r = client.post('/api/' + tool, headers=headers(owner), json=args)
            assert r.status_code == 200, (tool, r.text)
            return r.json()
        a = call('a', 'register_entry', name='a', version='v1')['id']
        b = call('b', 'register_entry', name='b', version='v1')['id']
        match = call('a', 'request_match', entry_id=a, mode=mode)['id']
        try:
            assert call('b', 'request_match', entry_id=b, mode=mode)['id'] == match
            aa = call('a', 'register_agents', match_id=match, names=['commander', 'scout'])
            bb = call('b', 'register_agents', match_id=match, names=['commander'])
            ah, scout, bh = aa[0]['agent_handle'], aa[1]['agent_handle'], bb[0]['agent_handle']
            catalog = call('a', 'get_action_list', agent_handle=ah)
            assert 'move' in catalog['names']
            call('a', 'broadcast_team_message', agent_handle=ah, text='hello', operation_id='broadcast')
            messages = call('a', 'read_team_messages', agent_handle=scout, operation_id='drain')
            assert messages['count'] == 1
            assert call('a', 'read_team_messages', agent_handle=scout, operation_id='drain') == messages
            link = call('a', 'get_view_link', match_id=match)
            assert link['faction'] == 'wei' and link['can_control'] is False
            assert client.get('/watch/').status_code == 200
            with client.websocket_connect('/watch/stream') as view:
                view.send_json({'kind': 'hello', 'token': link['url'].split('token=')[1]})
                welcome = view.receive_json()
                assert welcome['can_control'] is False and welcome['view'] == 'wei', welcome
                snapshot = view.receive_json()
                assert snapshot['kind'] == 'snapshot', snapshot
            call('a', 'ready_match', match_id=match); call('b', 'ready_match', match_id=match)
            assert call('a', 'get_match_status', match_id=match)['status'] == 'running'
            meta = {'io.modelcontextprotocol/protocolVersion': '2026-07-28',
                    'io.modelcontextprotocol/clientCapabilities': {}}
            response = client.post('/mcp', headers={**headers('a'), 'Accept': 'application/json, text/event-stream',
                'MCP-Protocol-Version': '2026-07-28', 'Mcp-Method': 'tools/call', 'Mcp-Name': 'get_observation'}, json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
                'params': {'name': 'get_observation', 'arguments': {'agent_handle': ah}, '_meta': meta}})
            assert response.status_code == 200, response.text
            assert not response.json()['result'].get('isError'), response.text
            with client.websocket_connect(f'/ws/metaverse/env/{match}/agent/{bh}', headers=headers('b')) as ws:
                assert ws.receive_json()['type'] == 'connect'
                ws.send_json({'type': 'message', 'sender': {'type': 'agent', 'id': bh},
                    'recipient': {'type': 'env', 'id': match}, 'timestamp': time.time(),
                    'payload': {'type': 'action', 'id': 'obs', 'action': 'get_faction_state', 'parameters': {}}})
                while True:
                    packet = ws.receive_json()
                    if packet['payload'].get('id') == 'obs':
                        assert packet['payload']['outcome']['success'], packet
                        break
            if mode == 'turn_based':
                outcome = call('a', 'end_turn', agent_handle=ah, operation_id='end-once')
                assert outcome.get('success'), outcome
                assert call('a', 'end_turn', agent_handle=ah, operation_id='end-once') == outcome
            call('a', 'resign_match', match_id=match)
            for _ in range(100):
                result = call('a', 'get_result', match_id=match)
                if result['status'] == 'finished': break
                time.sleep(.1)
            assert result['status'] == 'finished', result
            assert result['result']['source'] == 'resignation'
            assert call('a', 'report_usage', agent_handle=ah, operation_id='usage', metrics=None)['source'] == 'unavailable'
            board = client.get('/leaderboard/' + mode).json()
            assert len(board['rows']) == 2
            assert board['rows'][0]['elo'] == 1016
        finally:
            row = app.state.arena.store.one(__import__('starbench_arena.store', fromlist=['matches']).matches, id=match)
            if row and row['worker']:
                try:
                    urllib.request.urlopen(urllib.request.Request(row['worker']['url'] + '/stop', data=b'', headers={'Authorization': 'Bearer ' + row['worker']['token']}), timeout=2).close()
                except OSError: pass


def test_gateway_restart_recovers_same_worker_and_operations(hub, tmp_path):
    settings = Settings(development=True, hub_url=hub)
    database = 'sqlite:///' + str(tmp_path / 'recover.db')
    headers = {'Authorization': 'Bearer dev:a'}
    app = create_app(settings, Store(database))
    def invoke(client, owner, tool, **args):
        response = client.post('/api/' + tool, headers={'Authorization': 'Bearer dev:' + owner}, json=args)
        assert response.status_code == 200, response.text
        return response.json()
    with TestClient(app, base_url=settings.public_url) as client:
        a = invoke(client, 'a', 'register_entry', name='a', version='v')['id']
        b = invoke(client, 'b', 'register_entry', name='b', version='v')['id']
        mid = invoke(client, 'a', 'request_match', entry_id=a, mode='real_time')['id']
        invoke(client, 'b', 'request_match', entry_id=b, mode='real_time')
        ah = invoke(client, 'a', 'register_agents', match_id=mid, names=['commander'])[0]['agent_handle']
        invoke(client, 'b', 'register_agents', match_id=mid, names=['commander'])
        invoke(client, 'a', 'ready_match', match_id=mid); invoke(client, 'b', 'ready_match', match_id=mid)
        original = invoke(client, 'a', 'broadcast_team_message', agent_handle=ah, text='before restart', operation_id='message')
        from starbench_arena import store as db
        pid = app.state.arena.store.one(db.matches, id=mid)['worker']['pid']
    resumed = create_app(settings, Store(database))
    with TestClient(resumed, base_url=settings.public_url) as client:
        assert resumed.state.arena.store.one(db.matches, id=mid)['worker']['pid'] == pid
        assert invoke(client, 'a', 'get_observation', agent_handle=ah)['success']
        assert invoke(client, 'a', 'broadcast_team_message', agent_handle=ah, text='before restart', operation_id='message') == original
        invoke(client, 'a', 'resign_match', match_id=mid)
        for _ in range(100):
            if invoke(client, 'a', 'get_result', match_id=mid)['status'] == 'finished': break
            time.sleep(.1)
        assert invoke(client, 'a', 'get_result', match_id=mid)['status'] == 'finished'
    # Reap the original child after the recovered gateway stopped it.
    for process in app.state.arena.workers.processes.values():
        process.wait(timeout=10)
