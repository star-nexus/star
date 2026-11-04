import time
from types import SimpleNamespace
from dataclasses import replace
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from starbench_arena.config import Settings
from starbench_arena.auth import Principal
from starbench_arena.hosted import OAuthAttachedArena, set_grant
from starbench_arena.store import Store
from starbench_arena import store as db
from tests.arena.test_service import Workers


def settings(tmp_path):
    return Settings(database_url='sqlite:///'+str(tmp_path/'oauth.db'),
        public_url='https://mcp.test.org:10000',issuer='https://mcp.test.org:10000/auth/realms/starbench',
        audience='https://mcp.test.org:10000/mcp',jwks_url='https://mcp.test.org:10000/auth/realms/starbench/protocol/openid-connect/certs')


@pytest.mark.asyncio
async def test_grants_revocation_resume_and_issuer_isolation(tmp_path):
    s=settings(tmp_path); store=Store(s.database_url);store.initialize()
    arena=OAuthAttachedArena(s,store,Workers(),{'env_id':'env-one','mode':'turn_based'})
    alice=Principal('alice',issuer=s.issuer);bob=Principal('bob',issuer=s.issuer)
    with pytest.raises(PermissionError):arena.list_matches(alice)
    set_grant(store,s.issuer,'alice','env-one','wei')
    set_grant(store,s.issuer,'bob','env-one','shu')
    agent=(await arena.register_agents(alice,'env-one',['commander']))[0]['agent_handle']
    await arena.action(alice,agent,'move',{'unit_id':1},'move-1')
    with pytest.raises(PermissionError):await arena.action(bob,agent,'move',{},'move-2')
    with pytest.raises(PermissionError):arena.list_matches(Principal('alice',issuer='https://another'))
    with pytest.raises(ValueError):set_grant(store,s.issuer,'alice','env-one','shu')
    set_grant(store,s.issuer,'alice','env-one','wei',active=False)
    assert store.one(db.agents,id=agent)['generation']==1
    with pytest.raises(PermissionError):await arena.get_operation(alice,agent,'move-1')
    with pytest.raises(ValueError):set_grant(store,s.issuer,'mallory','env-one','wei')
    set_grant(store,s.issuer,'alice','env-one','wei')
    assert (await arena.register_agents(alice,'env-one',['commander']))[0]['agent_handle']==agent
    assert (await arena.get_operation(alice,agent,'move-1'))['state']=='completed'
    OAuthAttachedArena(s,store,Workers(),{'env_id':'env-two','mode':'real_time'})
    with pytest.raises(PermissionError):arena.match_for(alice,'env-two')


def test_oauth_mcp_profile_discovery_and_database_identity(tmp_path):
    from starbench_arena.hosted import make_app
    s=settings(tmp_path)
    app=make_app(s,{'env_id':'env-one','mode':'turn_based'})
    key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    app.state.arena.auth.keys=SimpleNamespace(get_signing_key_from_jwt=lambda t:SimpleNamespace(key=key.public_key()))
    claims={'sub':'new-user','iss':s.issuer,'aud':s.audience,'iat':int(time.time()),'exp':int(time.time())+60,'scope':'arena:play'}
    token=jwt.encode(claims,key,algorithm='RS256')
    with TestClient(app,base_url=s.public_url) as client:
        auth={'Authorization':'Bearer '+token}
        assert client.post('/api/get_profile',headers=auth,json={}).json()['id']=='new-user'
        assert client.post('/api/list_matches',headers=auth,json={}).status_code==403
        assert client.post('/api/get_profile',headers={'Authorization':'Bearer dev:new-user'},json={}).status_code==401
        metadata=client.get('/.well-known/oauth-protected-resource/mcp')
        assert metadata.status_code==200,metadata.text
        assert metadata.json()['resource']==s.audience
        assert metadata.json()['authorization_servers']==[s.issuer]
        set_grant(app.state.arena.store,s.issuer,'new-user','env-one','wei')
        result=client.post('/mcp',headers={**auth,'Accept':'application/json, text/event-stream','Mcp-Method':'tools/call','Mcp-Name':'list_matches'},json={
            'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':'list_matches','arguments':{},'_meta':{
            'io.modelcontextprotocol/protocolVersion':'2026-07-28','io.modelcontextprotocol/clientCapabilities':{}}}})
        assert result.status_code==200 and not result.json()['result'].get('isError'),result.text
    with pytest.raises(ValueError,match='another OAuth issuer'):
        make_app(replace(s,issuer='https://other.org/realms/starbench'),{'env_id':'env-one','mode':'turn_based'})


def test_local_operator_cli_grant_and_revoke(tmp_path):
    import json
    from starbench_arena.admin import grant_from_config
    s=settings(tmp_path);store=Store(s.database_url);store.initialize()
    OAuthAttachedArena(s,store,Workers(),{'env_id':'env-one','mode':'turn_based'})
    path=tmp_path/'runtime.json'
    path.write_text(json.dumps({'database_url':s.database_url,'issuer':s.issuer,
        'attachment':{'env_id':'env-one','mode':'turn_based'}}))
    assert grant_from_config(path,'alice','wei')['active']
    assert store.one(db.seat_grants,subject='alice')['active']
    assert not grant_from_config(path,'alice','wei',active=False)['active']
    assert not store.one(db.seat_grants,subject='alice')['active']


def test_revoking_seat_closes_existing_native_connection(tmp_path):
    from starlette.websockets import WebSocketDisconnect
    from starbench_arena.app import create_app
    from starbench_arena.local import LOCAL_TOOLS
    s=settings(tmp_path)
    app=create_app(s,workers=Workers(),managed=False,tools_allowed=LOCAL_TOOLS,
        arena_factory=lambda settings,store,workers:OAuthAttachedArena(settings,store,workers,
            {'env_id':'env-one','mode':'turn_based'}))
    key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    app.state.arena.auth.keys=SimpleNamespace(get_signing_key_from_jwt=lambda t:SimpleNamespace(key=key.public_key()))
    token=jwt.encode({'sub':'alice','iss':s.issuer,'aud':s.audience,'iat':int(time.time()),
        'exp':int(time.time())+60,'scope':'arena:play'},key,algorithm='RS256')
    headers={'Authorization':'Bearer '+token}
    with TestClient(app,base_url=s.public_url) as client:
        set_grant(app.state.arena.store,s.issuer,'alice','env-one','wei')
        response=client.post('/api/register_agents',headers=headers,json={'match_id':'env-one','names':['commander']})
        assert response.status_code==200,response.text
        handle=response.json()[0]['agent_handle']
        with client.websocket_connect('/ws/metaverse/env/env-one/agent/'+handle,headers=headers) as socket:
            assert socket.receive_json()['type']=='connect'
            set_grant(app.state.arena.store,s.issuer,'alice','env-one','wei',active=False)
            with pytest.raises(WebSocketDisconnect) as closed:
                for _ in range(20):socket.receive_json()
            assert closed.value.code==1008
