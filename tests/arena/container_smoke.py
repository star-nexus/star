"""Run inside the Arena image: real private HUB/Rust workers, isolated in-process API.

No development HTTP server is published and no production game database is used.
Usage: docker compose ... exec -T arena python - < tests/arena/container_smoke.py
"""
import json
import tempfile
import time
from pathlib import Path
from fastapi.testclient import TestClient
from starbench_arena.app import create_app
from starbench_arena.config import Settings
from starbench_arena.store import Store


def main():
    runtime=json.loads(Path('/run/arena/runtime.json').read_text())
    results=[]
    with tempfile.TemporaryDirectory(prefix='arena-smoke-') as temporary:
        for mode in ('turn_based','real_time'):
            settings=Settings(development=True,hub_url=runtime['hub_url'],turn_seconds=30)
            app=create_app(settings,Store('sqlite:///'+str(Path(temporary)/(mode+'.db'))))
            with TestClient(app,base_url=settings.public_url) as client:
                def call(owner,tool,**arguments):
                    response=client.post('/api/'+tool,headers={'Authorization':'Bearer dev:'+owner},json=arguments)
                    assert response.status_code==200,(tool,response.status_code,response.text)
                    return response.json()
                first=call('a','register_entry',name='smoke-a',version=mode)['id']
                second=call('b','register_entry',name='smoke-b',version=mode)['id']
                match=call('a','request_match',entry_id=first,mode=mode)['id']
                assert call('b','request_match',entry_id=second,mode=mode)['id']==match
                agents=call('a','register_agents',match_id=match,names=['commander','scout'])
                call('b','register_agents',match_id=match,names=['commander'])
                commander,scout=[a['agent_handle'] for a in agents]
                assert 'move' in call('a','get_action_list',agent_handle=commander)['names']
                call('a','broadcast_team_message',agent_handle=commander,text='container smoke',operation_id='broadcast')
                messages=call('a','read_team_messages',agent_handle=scout,operation_id='read')
                assert messages['count']==1
                assert call('a','read_team_messages',agent_handle=scout,operation_id='read')==messages
                call('a','ready_match',match_id=match);call('b','ready_match',match_id=match)
                assert call('a','get_observation',agent_handle=commander)['success']
                if mode=='turn_based':
                    outcome=call('a','end_turn',agent_handle=commander,operation_id='end')
                    assert outcome.get('success')
                    assert call('a','end_turn',agent_handle=commander,operation_id='end')==outcome
                call('a','resign_match',match_id=match)
                for _ in range(100):
                    result=call('a','get_result',match_id=match)
                    if result['status']=='finished':break
                    time.sleep(.1)
                assert result['status']=='finished',result
                assert result['result']['source']=='resignation'
                board=client.get('/leaderboard/'+mode).json()
                assert len(board['rows'])==2 and board['rows'][0]['elo']==1016
                results.append({'mode':mode,'rust_worker':'passed','team_messages_and_retry':'passed','settlement':'passed'})
    print(json.dumps({'container_smoke':results}))


if __name__=='__main__':main()
