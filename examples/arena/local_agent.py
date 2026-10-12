"""Attach two logical Agents to an existing ENV through the local MCP bridge API."""
import argparse
import asyncio
from pathlib import Path
import sys
from uuid import uuid4
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import httpx
from starbench_arena.local import load_config

async def main(args):
    config = load_config(args.config)
    async with httpx.AsyncClient(base_url=config['public_url'], trust_env=False, timeout=60,
        headers={'Authorization': 'Bearer ' + config['tokens'][args.faction]}) as http:
        async def call(tool, **params):
            result = await http.post('/api/' + tool, json=params)
            result.raise_for_status()
            return result.json()
        agents = await call('register_agents', match_id=config['env_id'], names=['commander', 'scout'])
        handle = agents[0]['agent_handle']
        print('Registered:', [a['agent_handle'] for a in agents])
        print('ENV action catalog:', await call('get_action_list', agent_handle=handle))
        if args.units:
            print('Claim:', await call('claim_units', agent_handle=handle, unit_ids=args.units, operation_id=uuid4().hex))
        while True:
            print('Observation:', await call('get_observation', agent_handle=handle))
            if args.once:
                break
            # Put your harness decision loop here; submit only ENV catalog actions.
            await asyncio.sleep(2)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=Path('.arena/local.json'))
    parser.add_argument('--faction', choices=['wei', 'shu'], default='shu')
    parser.add_argument('--units', type=int, nargs='+')
    parser.add_argument('--once', action='store_true')
    asyncio.run(main(parser.parse_args()))
