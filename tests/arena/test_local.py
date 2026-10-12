import json
from pathlib import Path
import socket
import subprocess
import time
import urllib.request
import pytest
from fastapi.testclient import TestClient
from starbench_arena.local import initialize, load_config, make_app
from tests.arena.test_live import hub


def test_config_is_private_and_cannot_be_overwritten(tmp_path):
    path = tmp_path/'local.json'
    config = initialize(path, 'local-env', 'turn_based', 'ws://127.0.0.1:8000/ws/metaverse', 8780)
    assert path.stat().st_mode & 0o777 == 0o600
    assert config['tokens']['wei'] != config['tokens']['shu']
    assert load_config(path) == config
    with pytest.raises(FileExistsError): initialize(path, 'other', 'turn_based', config['hub_url'], 8780)
    config['public_url'] = 'http://0.0.0.0:8780'
    path.write_text(json.dumps(config))
    with pytest.raises(ValueError): load_config(path)


@pytest.mark.parametrize('mode', ['turn_based', 'real_time'])
def test_attach_existing_rust_web_env(hub, mode, tmp_path):
    root = Path.cwd()
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]
    env_id = 'local-' + mode
    with (tmp_path/'env.log').open('wb') as log:
        env = subprocess.Popen([str(root/'.venv/bin/python'), '-m', 'rotk_env.rendering.web',
            '--backend', 'rust', '--players', 'ai_vs_ai', '--mode', mode, '--seed', '42',
            '--env-id', env_id, '--hub-url', hub, '--port', str(port)], stdout=log, stderr=log)
    try:
        for _ in range(150):
            if env.poll() is not None: pytest.fail((tmp_path/'env.log').read_text())
            try:
                urllib.request.urlopen(f'http://127.0.0.1:{port}/', timeout=.2).close(); break
            except OSError: time.sleep(.1)
        else: pytest.fail('External Web ENV did not start')
        config = initialize(tmp_path/'local.json', env_id, mode, hub, 8780)
        app = make_app(config)
        def headers(faction): return {'Authorization': 'Bearer '+config['tokens'][faction]}
        with TestClient(app, base_url=config['public_url']) as client:
            def call(faction, tool, **params):
                r = client.post('/api/'+tool, headers=headers(faction), json=params)
                assert r.status_code == 200, r.text
                return r.json()
            assert client.post('/api/list_matches',headers={'Authorization':'Bearer dev:wei'},json={}).status_code==401
            assert call('wei','list_matches')[0]['id'] == env_id
            assert client.post('/api/request_match',headers=headers('wei'),json={}).status_code==404
            aa = call('wei', 'register_agents', match_id=env_id, names=['commander','scout'])
            bb = call('shu', 'register_agents', match_id=env_id, names=['opponent'])
            ah, scout, bh = aa[0]['agent_handle'], aa[1]['agent_handle'], bb[0]['agent_handle']
            assert 'move' in call('wei','get_action_list',agent_handle=ah)['names']
            observed = call('wei','get_observation',agent_handle=ah)
            assert observed['success']
            assert client.post('/api/get_observation',headers=headers('shu'),json={'agent_handle':ah}).status_code==403
            call('wei','broadcast_team_message',agent_handle=ah,text='local bridge',operation_id='send')
            received=call('wei','read_team_messages',agent_handle=scout,operation_id='drain')
            assert received['count']==1
            assert call('wei','read_team_messages',agent_handle=scout,operation_id='drain')==received
            # Actual MCP HTTP requests, not only the helper REST wrapper.
            for tool, params in [('get_action_list',{'agent_handle':ah}), ('end_turn',{'agent_handle':ah,'operation_id':'turn'})] if mode=='turn_based' else [('get_observation',{'agent_handle':ah})]:
                response=client.post('/mcp',headers={**headers('wei'),'Accept':'application/json, text/event-stream',
                    'MCP-Protocol-Version':'2026-07-28','Mcp-Method':'tools/call','Mcp-Name':tool},json={
                    'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':tool,'arguments':params,
                    '_meta':{'io.modelcontextprotocol/protocolVersion':'2026-07-28','io.modelcontextprotocol/clientCapabilities':{}}}})
                assert response.status_code==200 and not response.json()['result'].get('isError'),response.text
        assert env.poll() is None, 'Closing MCP must not stop the external ENV'
        # Restarting the bridge reuses Agent handles and the same operation cache.
        with TestClient(make_app(config),base_url=config['public_url']) as client:
            response=client.post('/api/read_team_messages',headers=headers('wei'),json={'agent_handle':scout,'operation_id':'drain'})
            assert response.status_code==200 and response.json()==received
            response=client.post('/api/get_observation',headers=headers('wei'),json={'agent_handle':ah})
            assert response.status_code==200 and response.json()['success']
        assert env.poll() is None
    finally:
        env.terminate(); env.wait(timeout=10)


def test_stdio_relay_has_faction_identity_and_no_lifecycle_tools(tmp_path):
    import selectors
    root = Path.cwd()
    with socket.socket() as s:
        s.bind(('127.0.0.1',0)); port=s.getsockname()[1]
    path=tmp_path/'local.json'
    config=initialize(path,'stdio-env','turn_based','ws://127.0.0.1:8000/ws/metaverse',port)
    with (tmp_path/'http.log').open('wb') as log:
        server=subprocess.Popen([str(root/'.venv/bin/python'),'-m','starbench_arena.local','serve','--config',str(path)],stdout=log,stderr=log)
    relay=None
    try:
        for _ in range(100):
            if server.poll() is not None: pytest.fail((tmp_path/'http.log').read_text())
            try: urllib.request.urlopen(config['public_url']+'/health',timeout=.2).close();break
            except OSError: time.sleep(.1)
        else: pytest.fail('Local MCP bridge not ready')
        with (tmp_path/'stdio.log').open('wb') as log:
            relay=subprocess.Popen([str(root/'.venv/bin/python'),'-m','starbench_arena.local','stdio','--config',str(path),'--faction','wei'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=log,text=True)
            def rpc(method,params=None):
                body={'jsonrpc':'2.0','id':1,'method':method,'params':{**(params or {}),'_meta':{
                    'io.modelcontextprotocol/protocolVersion':'2026-07-28','io.modelcontextprotocol/clientCapabilities':{}}}}
                relay.stdin.write(json.dumps(body)+'\n');relay.stdin.flush()
                with selectors.DefaultSelector() as selector:
                    selector.register(relay.stdout,selectors.EVENT_READ)
                    assert selector.select(timeout=15), (tmp_path/'stdio.log').read_text()
                line=relay.stdout.readline()
                assert line, (tmp_path/'stdio.log').read_text()
                response=json.loads(line)
                assert 'error' not in response,response
                return response['result']
            names={t['name'] for t in rpc('tools/list')['tools']}
            assert 'get_observation' in names and 'request_match' not in names
            assert 'events' in rpc('server/discover')['capabilities']
            assert 'turn_start' in {e['name'] for e in rpc('events/list')['events']}
            profile=rpc('tools/call',{'name':'get_profile','arguments':{}})
            assert profile['structuredContent']['id']=='local:wei',profile
            assert not any(t in json.dumps(profile) for t in config['tokens'].values())
    finally:
        if relay:
            relay.terminate();relay.wait(timeout=10)
        server.terminate();server.wait(timeout=10)
