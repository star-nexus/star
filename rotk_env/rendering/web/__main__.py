"""Launch a Rust-authoritative match and serve its Three.js views."""
import argparse
import asyncio
import os
import signal

# Scene preparation still imports pygame for existing ENV assets and fonts.
# Its support banner does not describe the selected browser renderer.
os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')

from rotk_env.prefabs.config import Faction, PlayerType, PLAYER_PRESETS
from rotk_env.runtime.session import NativeSession
from .server import WebHost


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description='STARBench Web renderer (server-side Rust)')
    parser.add_argument('--renderer', choices=['web'], default='web')
    parser.add_argument('--backend', choices=['rust'], default='rust')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--mode', choices=['turn_based', 'real_time'], default='turn_based')
    parser.add_argument('--scenario', default='chibi-small')
    parser.add_argument('--seed', type=int, default=None)
    parser.add_argument('--native-threads', choices=[1, 2, 4], type=int, default=1)
    parser.add_argument('--players', choices=['human_vs_human', *PLAYER_PRESETS], default='human_vs_human')
    parser.add_argument('--hub-url', default=None, help='Attach the existing Agent Hub transport')
    parser.add_argument('--env-id', default=None)
    parser.add_argument('--no-hub', action='store_true', help='Explicit offline match (Web default)')
    return parser.parse_args(argv)


async def run(args):
    players = ({Faction.WEI: PlayerType.HUMAN, Faction.SHU: PlayerType.HUMAN}
               if args.players == 'human_vs_human' else PLAYER_PRESETS[args.players])
    session = NativeSession(display='none', renderer='web', mode=args.mode,
        scenario=args.scenario, seed=args.seed, players=players, threads=args.native_threads)
    host = WebHost(session, host=args.host, port=args.port)
    try:
        hub_url = None if args.no_hub else args.hub_url or os.environ.get('STAR_HUB_URL')
        if hub_url:
            from rotk_env.runtime.hub import NativeHubHost
            host.hub = NativeHubHost(session, hub_url, args.env_id)
        await host.start()
        print(f'Rust ENV / Three.js | {args.scenario} | {args.mode}', flush=True)
        for token, grant in host.grants.items():
            role = 'control' if grant.can_control else 'read only'
            print(f'{grant.view} ({role}): {host.url}#token={token}', flush=True)
        print('Ctrl+C stops this match. View links are credentials for this session.', flush=True)
        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop.set)
        done = asyncio.create_task(stop.wait())
        try:
            await asyncio.wait([done, host._pump_task], return_when=asyncio.FIRST_COMPLETED)
            if host._pump_task.done():
                await host.wait()
        finally:
            done.cancel()
    finally:
        await host.close()


def main(argv=None):
    asyncio.run(run(parse_args(argv)))


if __name__ == '__main__':
    main()
