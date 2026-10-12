"""Independent Rust match process. Only the Arena knows its control credential."""
import asyncio
from collections import Counter
from contextlib import asynccontextmanager
import json
import os
import secrets
import sys
import threading
import time
from fastapi import FastAPI, Header, HTTPException
import uvicorn
from rotk_env.prefabs.config import PLAYER_PRESETS
from rotk_env.runtime.session import NativeSession
from rotk_env.runtime.hub import NativeHubHost

PREPARATION_ACTIONS = frozenset({'register_agent_info', 'claim_units', 'release_units',
    'list_team', 'broadcast_to_team', 'read_team_messages', 'get_action_list',
    'get_faction_state', 'turn_start_ack', 'report_llm_stats', 'get_operation'})

class ArenaHost(NativeHubHost):
    def __init__(self, *args, **kwargs):
        self.admission = threading.RLock()
        self.running = False
        self.final_result = None
        self.started_at = None
        self.turn_seconds = 300
        self.turn_key = None
        self.turn_deadline = None
        self.turn_based = False
        super().__init__(*args, **kwargs)

    def _enqueue(self, kind, data):
        if kind == 'message':
            data = dict(data, _arena_received_at=time.monotonic())
        return super()._enqueue(kind, data)

    def check_deadline(self, at):
        if self.running and self.turn_deadline is not None and at >= self.turn_deadline:
            state = self.runtime.host_status()
            if state['game_over']:
                self.finish(state['winner'], 'env')
            else:
                faction = self.turn_key[1]
                self.finish('shu' if faction == 'wei' else 'wei', 'turn_timeout')

    def track_turn(self):
        if not self.running or not self.turn_based:
            return
        state = self.runtime.host_status()
        key = (state['turn_number'], state['current_player'])
        if key != self.turn_key:
            self.turn_key = key
            self.turn_deadline = time.monotonic() + self.turn_seconds

    def on_message(self, envelope):
        with self.admission:
            self.check_deadline(envelope.get('_arena_received_at', time.monotonic()))
            return super().on_message(envelope)

    def _process_action_request(self, agent_id, action_id, action, params, *, send_response):
        if self.final_result or (not self.running and action not in PREPARATION_ACTIONS):
            result = {'success': False, 'error': 'match_not_running'}
            if send_response:
                self.client.response_to_agent(agent_id, action_id, result, 'json')
            return result
        result = super()._process_action_request(agent_id, action_id, action, params, send_response=send_response)
        self.track_turn()
        return result

    def _service(self, wall_time):
        # Arena consumes authoritative results directly; no paper/report wait.
        with self.admission:
            if not self.running or self.final_result:
                return
            state = self.runtime.host_status()
            if state['game_over']:
                self.finish(state['winner'], 'env')
            elif self._inbox.empty():
                self.check_deadline(time.monotonic())
            if self.running:
                super()._service(wall_time)

    def finish(self, winner, source):
        if self.final_result:
            return self.final_result
        self.runtime.stop_clock()
        snapshot = self.runtime.export_state()
        counts = Counter(e['components']['Unit']['faction'] for e in snapshot['entities']
                         if 'Unit' in e['components'] and e['components'].get('UnitCount', {}).get('current_count', 0) > 0)
        stats = snapshot['singletons']['GameStats']
        self.final_result = {'winner': winner, 'is_tie': winner is None, 'source': source,
            'game_duration_seconds': snapshot['clock']['elapsed'],
            'units_info': {f: {'total_units': n, 'surviving_units': counts[f]}
                           for f, n in stats['initial_unit_counts'].items()},
            'env_end_reason': snapshot['singletons']['GameState'].get('end_reason')}
        self.running = False
        return self.final_result

    def start_match(self):
        with self.admission:
            if self.running or self.final_result:
                return
            self.running = True
            self.started_at = time.time()
            self.track_turn()
            self.runtime.start_clock(1 / 60)
            state = self.runtime.host_status()
            snapshot = self.runtime.export_state()
            mapping = snapshot['singletons']['GameStats']['agent_id_to_faction']
            if snapshot['mode'] == 'turn_based':
                self._notify_turn({'candidates': [a for a, f in mapping.items() if f == state['current_player']],
                    'notification': {'type': 'turn_start', 'faction': state['current_player'],
                        'turn_number': state['turn_number'], 'timestamp': time.time()}})


def main():
    import faulthandler, signal
    faulthandler.register(signal.SIGUSR1, all_threads=True)
    config = json.loads(sys.stdin.readline())
    token = config['token']
    session = NativeSession(display='none', mode=config['mode'], scenario=config['scenario'],
                            seed=config['seed'], players=PLAYER_PRESETS['ai_vs_ai'])
    host = ArenaHost(session, config['hub_url'], config['match_id'])
    host.turn_seconds = config.get('turn_seconds', 300)
    host.turn_based = config['mode'] == 'turn_based'
    server = None
    async def pump():
        while True:
            session.runtime.pump()
            if host.snapshot()['failure']:
                raise RuntimeError(host.snapshot()['failure'])
            await asyncio.sleep(1 / 60)
    @asynccontextmanager
    async def lifespan(app):
        task = asyncio.create_task(pump())
        try:
            yield
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            host.close()
            session.close()
    app = FastAPI(lifespan=lifespan)
    def authorize(authorization):
        if not authorization or not secrets.compare_digest(authorization, 'Bearer ' + token):
            raise HTTPException(401)
    @app.get('/status')
    async def status(authorization: str = Header(default='')):
        authorize(authorization)
        if host.snapshot()['failure']:
            raise HTTPException(503, 'ENV host failed')
        return {'running': host.running, 'result': host.final_result, 'started_at': host.started_at,
                'state': session.runtime.host_status()}
    @app.post('/start')
    async def start(authorization: str = Header(default='')):
        authorize(authorization)
        host.start_match()
        return {'started': host.running}
    @app.post('/stop')
    async def stop(authorization: str = Header(default='')):
        authorize(authorization)
        server.should_exit = True
        return {'stopping': True}
    @app.post('/resign/{faction}')
    async def resign(faction: str, authorization: str = Header(default='')):
        authorize(authorization)
        if faction not in ('wei', 'shu') or not host.running:
            raise HTTPException(409)
        with host.admission:
            return host.finish('shu' if faction == 'wei' else 'wei', 'resignation')
    server = uvicorn.Server(uvicorn.Config(app, host=config['bind'], port=config['port'], log_level='warning'))
    server.run()

if __name__ == '__main__':
    main()
