import time
import pytest
pytest.importorskip('star_rust_runtime')
from starbench_arena.worker import ArenaHost
from rotk_env.runtime.session import NativeSession
from rotk_env.prefabs.config import PLAYER_PRESETS
from rotk_env.systems.llm_system import SyncEnvClient

REG = dict(faction='wei', provider='synthetic', model_id='fixture', base_url='https://host')


class Client(SyncEnvClient):
    """Transport stub without importing the legacy pygame comparison fixtures."""
    def connect(self):
        self.connected = True
        for callback in self.hub_event_handlers['connect']:
            callback({'env_id': self.client_info.id})
        return True

    def disconnect(self):
        self.connected = False

    def send_message(self, instruction, data=None, target=None):
        return True


def test_deadline_uses_ingress_and_ack_does_not_reset_it():
    with NativeSession(display='none', scenario='chibi-small', seed=42, players=PLAYER_PRESETS['ai_vs_ai']) as session:
        host = ArenaHost(session, 'ws://fixture', client_factory=Client)
        def send(agent, action, params, op, at=None):
            envelope = {'sender': {'type': 'agent', 'id': agent},
                'payload': {'type': 'action', 'id': op, 'operation_id': op, 'action': action, 'parameters': params},
                '_arena_received_at': time.monotonic() if at is None else at}
            host.on_message(envelope)
        try:
            send('wei', 'register_agent_info', dict(REG, faction='wei'), 'rw')
            send('shu', 'register_agent_info', dict(REG, faction='shu'), 'rs')
            host.turn_based = True
            host.start_match()
            deadline = host.turn_deadline
            send('wei', 'turn_start_ack', {}, 'ack')
            assert host.turn_deadline == deadline
            # A command received before the deadline remains admissible even when
            # the worker only executes it afterwards.
            with host.admission:
                host.turn_deadline = time.monotonic() - 1
                send('wei', 'end_turn', {'faction': 'wei'}, 'end', host.turn_deadline - .1)
                assert host.final_result is None
                assert host.turn_key[1] == 'shu'
                assert host.turn_deadline > time.monotonic()
                host.check_deadline(host.turn_deadline)
                assert host.final_result['winner'] == 'wei'
                assert host.final_result['source'] == 'turn_timeout'
                assert host.final_result['units_info']['wei']['surviving_units'] == 5
        finally:
            host.close()
