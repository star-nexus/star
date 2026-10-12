import base64
import json
import pytest
from fastapi.testclient import TestClient
from starbench_arena.api import http_principal
from starbench_arena.auth import Principal
from starbench_arena.events import EventService, SubscribeParams, deliver
from starbench_arena.app import create_app
from starbench_arena.config import Settings
from starbench_arena.store import Store
from tests.arena.test_service import arena, pair, Workers

@pytest.mark.asyncio
async def test_subscription_is_owned_idempotent_and_retries_same_event(arena):
    a,b,mid,*_ = await pair(arena)
    sent = []
    failing = [True]
    def sender(url, secret, sub, event_id, body):
        if body.get('type') == 'verification': return {'challenge': body['challenge']}
        sent.append((event_id, body))
        if failing[0]: raise OSError('response lost')
        return {}
    service = EventService(arena, sender)
    params = SubscribeParams(name='turn_start', arguments={'match_id': mid},
        delivery={'mode':'webhook','url':'https://example.com/callback', 'secret':'whsec_'+base64.b64encode(b'x'*32).decode()})
    sub = await service.subscribe(a, params)
    assert (await service.subscribe(a, params)).id == sub.id
    with pytest.raises(PermissionError):
        await service.subscribe(Principal('outside'), params)
    arena.emit(mid, 'turn_start', {'faction':'wei'}, a.subject)
    await service.tick()
    from starbench_arena import store as db
    arena.store.update(db.subscriptions, {'id':sub.id}, next_attempt=0)
    failing[0] = False
    await service.tick()
    assert len(sent) == 2 and sent[0] == sent[1]
    await service.tick()
    assert len(sent) == 2

@pytest.mark.parametrize('url', ['http://example.com/x','https://127.0.0.1/x','https://[::1]/x','https://user:pass@example.com/x'])
def test_callback_cannot_reach_private_addresses(url):
    with pytest.raises(ValueError):
        deliver(url,'whsec_'+base64.b64encode(b'x'*32).decode(),'sub','event',{})


def test_mcp_event_discovery_and_authentication():
    app=create_app(Settings(development=True), Store('sqlite:///:memory:'), Workers())
    with TestClient(app,base_url='http://127.0.0.1:8780') as client:
        def rpc(method, token='dev:a'):
            return client.post('/mcp',headers={'Authorization':'Bearer '+token,'Accept':'application/json, text/event-stream',
                'MCP-Protocol-Version':'2026-07-28','Mcp-Method':method},json={'jsonrpc':'2.0','id':1,'method':method,
                'params':{'_meta':{'io.modelcontextprotocol/protocolVersion':'2026-07-28',
                                  'io.modelcontextprotocol/clientCapabilities':{}}}})
        discovery=rpc('server/discover')
        assert discovery.status_code==200, discovery.text
        assert discovery.json()['result']['capabilities']['events']=={}
        events=rpc('events/list')
        assert events.status_code==200, events.text
        assert 'turn_start' in [e['name'] for e in events.json()['result']['events']]
        assert rpc('events/list','invalid').status_code==401
