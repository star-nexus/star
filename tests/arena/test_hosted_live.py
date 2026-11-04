"""Signed OAuth identity -> real Rust ENV, independent of public ingress/GitHub UI."""
from dataclasses import replace
import socket
import subprocess
import time
from pathlib import Path
from types import SimpleNamespace
import urllib.request
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from starbench_arena.hosted import make_app,set_grant
from tests.arena.test_hosted import settings
from tests.arena.test_live import hub


@pytest.mark.parametrize('mode',['turn_based','real_time'])
def test_oauth_to_existing_rust_env(hub,mode,tmp_path):
    root=Path.cwd()
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    env_id='oauth-'+mode
    logpath=tmp_path/'env.log'
    with logpath.open('wb') as log:
        env=subprocess.Popen([str(root/'.venv/bin/python'),'-m','rotk_env.rendering.web','--backend','rust',
            '--players','ai_vs_ai','--mode',mode,'--seed','42','--env-id',env_id,'--hub-url',hub,'--port',str(port)],stdout=log,stderr=log)
    try:
        for _ in range(150):
            if env.poll() is not None:pytest.fail(logpath.read_text())
            try:urllib.request.urlopen(f'http://127.0.0.1:{port}/',timeout=.2).close();break
            except OSError:time.sleep(.1)
        else:pytest.fail('ENV startup timeout')
        s=replace(settings(tmp_path),hub_url=hub)
        app=make_app(s,{'env_id':env_id,'mode':mode})
        key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        app.state.arena.auth.keys=SimpleNamespace(get_signing_key_from_jwt=lambda _:SimpleNamespace(key=key.public_key()))
        tokens={owner:jwt.encode({'sub':owner,'iss':s.issuer,'aud':s.audience,'scope':'arena:play',
            'iat':int(time.time()),'exp':int(time.time())+120},key,algorithm='RS256') for owner in ('alice','bob')}
        def headers(owner):return {'Authorization':'Bearer '+tokens[owner]}
        with TestClient(app,base_url=s.public_url) as client:
            def call(owner,tool,**params):
                r=client.post('/api/'+tool,headers=headers(owner),json=params)
                assert r.status_code==200,r.text
                return r.json()
            for owner,faction in (('alice','wei'),('bob','shu')):set_grant(app.state.arena.store,s.issuer,owner,env_id,faction)
            agents=call('alice','register_agents',match_id=env_id,names=['commander','scout'])
            opponent=call('bob','register_agents',match_id=env_id,names=['commander'])
            handle,scout=(a['agent_handle'] for a in agents)
            assert 'move' in call('alice','get_action_list',agent_handle=handle)['names']
            observation=call('alice','get_observation',agent_handle=handle)
            assert observation['success']
            assert 'units' in observation, list(observation)
            units=observation['units']
            assert isinstance(units,list) and units, type(units)
            unit=next(u for u in units if u.get('reachable'))
            assert 'unit_id' in unit, list(unit)
            assert 'position' in unit, list(unit)
            target=next(pos for pos in unit['reachable'] if pos!=unit['position'])
            call('alice','claim_units',agent_handle=handle,unit_ids=[unit['unit_id']],operation_id='claim-1')
            action={'action':'move','parameters':{'unit_id':unit['unit_id'],'target_position':target},'operation_id':'move-1'}
            moved=call('alice','submit_actions',agent_handle=handle,actions=[action])
            assert moved['results'][0]['response']['success'],moved
            assert call('alice','submit_actions',agent_handle=handle,actions=[action])==moved
            for _ in range(50):
                after=call('alice','get_observation',agent_handle=handle)
                positioned=next(u for u in after['units'] if u['unit_id']==unit['unit_id'])
                if positioned['position']==target:break
                time.sleep(.05)
            assert positioned['position']==target
            assert client.post('/api/get_observation',headers=headers('bob'),json={'agent_handle':handle}).status_code==403
            call('alice','broadcast_team_message',agent_handle=handle,text='OAuth team',operation_id='msg-1')
            messages=call('alice','read_team_messages',agent_handle=scout,operation_id='read-1')
            assert messages['count']==1
            assert call('alice','read_team_messages',agent_handle=scout,operation_id='read-1')==messages
            if mode=='turn_based':
                result=call('alice','end_turn',agent_handle=handle,operation_id='end-1')
                assert result['success']
                assert call('alice','end_turn',agent_handle=handle,operation_id='end-1')==result
            set_grant(app.state.arena.store,s.issuer,'alice',env_id,'wei',active=False)
            assert client.post('/api/get_observation',headers=headers('alice'),json={'agent_handle':handle}).status_code==403
            set_grant(app.state.arena.store,s.issuer,'alice',env_id,'wei')
            assert call('alice','register_agents',match_id=env_id,names=['commander'])[0]['agent_handle']==handle
        assert env.poll() is None
        restarted=make_app(s,{'env_id':env_id,'mode':mode})
        restarted.state.arena.auth.keys=app.state.arena.auth.keys
        with TestClient(restarted,base_url=s.public_url) as client:
            result=client.post('/api/read_team_messages',headers=headers('alice'),json={'agent_handle':scout,'operation_id':'read-1'})
            assert result.status_code==200 and result.json()==messages
        assert env.poll() is None
    finally:
        env.terminate();env.wait(timeout=10)
