"""Fresh-process dependency checks; also runnable in a pygame-free environment."""
import argparse
import asyncio
import importlib.abc
import importlib.util
import json
import os
from pathlib import Path
import sys
import time


class RejectImports(importlib.abc.MetaPathFinder):
    def __init__(self, *prefixes):
        self.prefixes = prefixes

    def find_spec(self, fullname, *args):
        if any(fullname == p or fullname.startswith(p + '.') for p in self.prefixes):
            raise AssertionError('Unexpected renderer dependency: ' + fullname)


async def check_web():
    pygame_installed = importlib.util.find_spec('pygame') is not None
    sys.meta_path.insert(0, RejectImports('pygame', 'rotk_env.rendering.pygame',
                                        'rotk_env.rendering.pygame_adapter'))
    import httpx
    from websockets.asyncio.client import connect
    from rotk_env.prefabs.config import Faction, PlayerType
    from rotk_env.runtime.session import NativeSession
    from rotk_env.runtime.native import _complete_result
    from rotk_env.runtime.hub import NativeHubHost
    from rotk_env.systems.llm_system import SyncEnvClient
    from rotk_env.rendering.commands import ViewGrant
    from rotk_env.rendering.web.server import WebHost

    # A misconfigured Web session must fail before it prepares SDL resources.
    try:
        NativeSession(renderer='web', display='dummy')
    except ValueError as exc:
        assert "display='none'" in str(exc)
    else:
        raise AssertionError('Web accepted pygame preparation')

    class Client(SyncEnvClient):
        def __init__(self, **kw):
            super().__init__(**kw)
            self.packets = []

        def connect(self):
            self.connected = True
            for callback in self.hub_event_handlers['connect']:
                callback({'env_id': self.client_info.id})
            return True

        def disconnect(self):
            self.connected = False

        def send_message(self, instruction, data=None, target=None):
            self.packets.append((instruction, data, target))
            return True

    async def receive(socket, kind):
        async with asyncio.timeout(3):
            while True:
                packet = json.loads(await socket.recv())
                if packet['kind'] == kind:
                    return packet

    session = NativeSession(renderer='web', scenario='chibi-small', seed=42,
        players={Faction.WEI: PlayerType.HUMAN, Faction.SHU: PlayerType.HUMAN})
    host = WebHost(session, port=0, grants={'probe': ViewGrant('wei', True)})
    try:
        initial = session.runtime.export_state()
        assert not session.world.systems
        assert initial['systems']['VisionSystem']['indexed']
        assert initial['systems']['StatisticsSystem']['indexed']
        assert 'AnimationSystem' in initial['systems']
        # Exercise the successful VLM completion branch as well as ordinary reads.
        result = _complete_result('get_faction_state_vlm', {'success': True},
                                  session.frame_provider.capture)
        assert result['frame_base64'] is None and result['frame_format'] is None
        assert result['frame_error'] == 'Web renderer does not provide Agent observation frames'

        host.hub = NativeHubHost(session, 'ws://fixture', client_factory=Client)
        for action, params in [
            ('register_agent_info', dict(faction='wei', provider='synthetic',
                                        model_id='fixture', base_url='https://host')),
            ('get_faction_state', {'faction': 'wei'}),
        ]:
            n = host.hub.snapshot()['completed_messages']
            host.hub._enqueue('message', dict(sender=dict(type='agent', id='probe-agent'),
                payload=dict(type='action', id=n, action=action, parameters=params)))
            deadline = time.monotonic() + 5
            while host.hub.snapshot()['completed_messages'] != n + 1:
                session.runtime.pump()
                assert time.monotonic() < deadline, 'Hub request stalled'
                await asyncio.sleep(.001)
            assert host.hub.snapshot()['failure'] is None
        assert host.hub.snapshot()['registered_agents'] == 1
        outcomes = [data['outcome'] for _, data, _ in host.hub.client.packets
                    if isinstance(data, dict) and data.get('type') == 'outcome']
        assert len(outcomes) == 2 and all(row['success'] for row in outcomes)

        await host.start(clock=False)
        async with httpx.AsyncClient(base_url=host.url, trust_env=False) as client:
            for path in ('/', '/renderer.js', '/vendor/three.module.js',
                         '/assets/texture/units/wei/infantry.png'):
                assert (await client.get(path)).status_code == 200
        async with connect(f'ws://127.0.0.1:{host.port}/stream') as socket:
            await socket.send(json.dumps(dict(kind='hello', token='probe')))
            snapshot = await receive(socket, 'snapshot')
            uid = snapshot['units'][0]['id']
            for n, command in enumerate(('wait', 'wait', 'end_turn')):
                await socket.send(json.dumps(dict(kind='command', id=str(n),
                    epoch=snapshot['epoch'], command=command,
                    parameters={} if command == 'end_turn' else {'unit_id': uid})))
                assert (await receive(socket, 'command_result'))['success']
                assert session.renderer.model.snapshot('wei')['units'][0]['ap'] == (2 if n == 2 else 1-n)
        assert session.runtime.host_status()['current_player'] == 'shu'
    finally:
        await host.close()
    assert session.closed and not session.world.entities
    assert not any(n == 'pygame' or n.startswith('pygame.') for n in sys.modules)
    return dict(passed=True, renderer='web', pygame_installed=pygame_installed,
                pygame_imported=False, http_assets=True, websocket_commands=True,
                end_turn_ap_recovered=True, agent_hub=True, indexed=True,
                vlm_no_fallback=True, closed=True)


def check_pygame():
    os.environ.update(SDL_VIDEODRIVER='dummy', SDL_AUDIODRIVER='dummy', HEADLESS='0')
    sys.meta_path.insert(0, RejectImports('rotk_env.rendering.web',
                                        'rotk_env.rendering.projection'))
    from framework.engine.game_engine import GameEngine
    from rotk_env.prefabs.config import GameConfig
    from rotk_env.runtime.session import NativeSession
    engine = GameEngine(width=1200, height=900, title='Dependency probe')
    GameConfig.sync_from_display()
    try:
        with NativeSession(display='window', scenario='chibi-small', seed=42) as session:
            state = session.runtime.export_state()
            session.update_display(0, inputs=False)
            assert session.runtime.export_state() == state
            frame, error = session.frame_provider.capture()
            assert frame and error is None
    finally:
        engine.quit()
    assert 'pygame' in sys.modules
    assert not any(n.startswith('rotk_env.rendering.web') for n in sys.modules)
    return dict(passed=True, renderer='pygame', web_imported=False,
                capture=True, drawing_preserves_authority=True, closed=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('renderer', choices=('web', 'pygame'))
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = asyncio.run(check_web()) if args.renderer == 'web' else check_pygame()
    text = json.dumps(result, indent=2) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    print(text)
