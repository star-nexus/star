"""Native multi-Agent transport example. Replace decide() with your Harness.

This sample observes through two Agents and ends its turns; it
is a connection smoke test, not a competitive strategy or an API BOSS.
"""
import argparse
import asyncio
import json
import os
from pathlib import Path
import sys
import time
from uuid import uuid4
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import httpx
from protocol import AgentClient

class Credentials:
    def __init__(self,path,dev): self.path,self.dev,self.lock=path,dev,asyncio.Lock()
    async def token(self):
        if self.dev: return self.dev
        async with self.lock:
            data=json.loads(self.path.read_text())
            if data['expires_at']<time.time()+60:
                async with httpx.AsyncClient() as http:
                    r=await http.post(data['token_endpoint'], data={'grant_type':'refresh_token','client_id':'starbench-harness','refresh_token':data['refresh_token']})
                    r.raise_for_status(); data.update(r.json()); data['expires_at']=time.time()+data['expires_in']
                fd=os.open(self.path,os.O_WRONLY|os.O_TRUNC,0o600)
                with os.fdopen(fd,'w') as output: json.dump(data,output)
            return data['access_token']

async def decide(client, observation):
    # Your harness chooses ENV catalog actions here. Persist operation IDs before
    # sending and reuse the same ID after an uncertain network response.
    return None

async def main(args):
    credentials=Credentials(args.token_file,args.dev_token)
    async with httpx.AsyncClient(base_url=args.arena,timeout=30,trust_env=False) as http:
        async def api(tool,**parameters):
            r=await http.post('/api/'+tool,headers={'Authorization':'Bearer '+await credentials.token()},json=parameters)
            r.raise_for_status(); return r.json()
        print('Account:',await api('get_profile'))
        entry=await api('register_entry',name=args.name,version=args.version,details={'model':'transport-example'})
        match=await api('request_match',entry_id=entry['id'],mode=args.mode)
        print('Queued match:',match['id'])
        while match['status']=='queued':
            await asyncio.sleep(1); match=await api('get_match_status',match_id=match['id'])
        if match['status']!='preparing': raise RuntimeError(match['status'])
        agents=await api('register_agents',match_id=match['id'],names=['commander','scout'])
        clients=[]
        try:
            # Same OAuth identity and assigned handles at the native WSS entry.
            url=args.arena.replace('https://','wss://').replace('http://','ws://')+'/ws/metaverse'
            for agent in agents:
                handle=agent['agent_handle']
                resumed=await api('resume_agent',agent_handle=handle)
                client=AgentClient(url,match['id'],handle,connection_options={'proxy':None,'additional_headers':{
                    'Authorization':'Bearer '+await credentials.token(),'X-Arena-Generation':str(resumed['generation'])}})
                await client.connect(); clients.append(client)
            catalog=await clients[0].call('get_action_list',{})
            print('ENV actions:',catalog.get('names',[]))
            await api('ready_match',match_id=match['id'])
            cursor=0
            while True:
                match=await api('get_match_status',match_id=match['id'])
                if match['status'] in ('finished','aborted','cancelled'): break
                if match['status']=='running':
                    for client in clients:
                        # Refresh bearer credentials before reconnecting an expired connection.
                        token=await credentials.token()
                        if client.connection_options['additional_headers']['Authorization']!='Bearer '+token or client.websocket.close_code is not None:
                            await client.disconnect()
                            client.connection_options['additional_headers']['Authorization']='Bearer '+token
                            await client.connect()
                        observation=await client.call('get_faction_state',{})
                        await decide(client,observation)
                    events=await api('read_events',match_id=match['id'],cursor=cursor)
                    for event in events['events']:
                        if event['kind']=='turn_start' and event['body'].get('faction')==agents[0]['faction']:
                            # Transport ACK is already handled by Arena. This is an
                            # explicit sample strategy decision to end the turn.
                            await clients[0].call('end_turn',{},operation_id='end-event-'+str(event['id']))
                    cursor=events['cursor']
                await asyncio.sleep(1)
            print(await api('get_result',match_id=match['id']))
        finally:
            await asyncio.gather(*(c.disconnect() for c in clients))
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('arena');parser.add_argument('--name',required=True);parser.add_argument('--version',default='v1')
    parser.add_argument('--mode',choices=['turn_based','real_time'],default='turn_based')
    parser.add_argument('--token-file',type=Path,default=Path(__file__).with_name('token.json'))
    parser.add_argument('--dev-token',help='Local ARENA_DEV=1 only, e.g. dev:alice')
    asyncio.run(main(parser.parse_args()))
