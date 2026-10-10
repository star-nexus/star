"""ENV transport parity: real authority ownership, legacy wire/count prefixes."""
from copy import deepcopy
import time
import pytest
pytest.importorskip('star_native')
from framework import World
from rotk_env.runtime import session as module
from rotk_env.runtime.session import NativeSession
from rotk_env.runtime.hub import NativeHubHost
from rotk_env.systems.llm_system import SyncEnvClient
from rotk_env.runtime.bootstrap import export_initial_state
from rotk_env.tests.test_native_turn import setup
from rotk_env.tests.test_native_request_batch import frozen
from rotk_env import components as c

REG = dict(faction='wei', provider='synthetic', model_id='fixture', base_url='https://host')

class Client(SyncEnvClient):
    def __init__(self, server_url='ws://fixture', env_id='fixture'):
        super().__init__(server_url, env_id)
        self.packets = []
        self.fail_send = False
    def connect(self):
        self.connected = True
        for callback in self.hub_event_handlers['connect']:
            callback({'env_id': self.client_info.id})
        return True
    def disconnect(self):
        self.connected = False
    def send_message(self, instruction, data=None, target=None):
        if self.fail_send:
            self.fail_send = False
            raise RuntimeError('fixture send failed')
        self.packets.append(deepcopy((instruction, data, target)))
        return True

def wait(session, condition):
    deadline = time.monotonic()+5
    while not condition():
        session.runtime.pump()
        assert time.monotonic() < deadline, 'host did not finish'
        time.sleep(.001)
    session.runtime.pump()

@pytest.fixture(params=[1,4])
def hosts(monkeypatch, frozen, request):
    world, ids, _, oracle = setup('none')
    from rotk_env.prefabs.config import Faction
    world.get_singleton_component(c.GameStats).initial_unit_counts = {Faction.WEI:2, Faction.SHU:1}
    initial = export_initial_state(world)
    monkeypatch.setattr(module, 'prepare_display_world', lambda **kw: (World(), deepcopy(initial)))
    oracle.client = Client()
    with NativeSession(display='none',threads=request.param) as session:
        host = NativeHubHost(session, 'ws://fixture', client_factory=Client)
        def check(payload, agent='a', send_failure=False):
            envelope = dict(sender=dict(type='agent', id=agent), payload=payload)
            oracle.client.fail_send = host.client.fail_send = send_failure
            oracle.on_message(deepcopy(envelope))
            n = host.snapshot()['completed_messages']
            host._enqueue('message', envelope)
            wait(session, lambda: host.snapshot()['completed_messages'] == n+1)
            assert host.snapshot()['failure'] is None
            assert host.client.packets == oracle.client.packets
            assert session.runtime.export_state() == export_initial_state(world)
        try:
            yield world, ids, oracle, session, host, check
        finally:
            host.close(); host.close()
    world.reset()

def single(action, parameters=None, id=0):
    return dict(type='action', id=id, action=action, parameters=parameters or {})

def test_wire_permissions_team_batch_and_malformed_prefix(hosts):
    world, (a,b,cid), oracle, session, host, check = hosts
    check(single('get_action_list'), agent='unknown')
    check(single('register_agent_info', REG))
    check(single('register_agent_info', dict(REG, faction='shu')), agent='b')
    check(single('get_faction_state', {'faction':'shu', 'agent_id':'b'}))
    check(single('claim_units', {'unit_ids':[a,b]}))
    check(single('claim_units', {'unit_ids':[a]}), agent='b')
    check(single('broadcast_to_team', {'message':'hello'}))
    check(single('read_team_messages'))
    check(dict(type='action_batch', id='batch', actions=[
        {'action':'get_faction_state','parameters':{'faction':'wei'}},
        {'id':'','action':'get_faction_state','parameters':'{"faction":"wei"}'},
        {'action':'release_units','parameters':{'unit_ids':[a,{}]}},
        {'id':None,'action':'get_faction_state','parameters':{'faction':'wei'}},
        {'id':5}, {'action':'not-a-game-action'}]))
    assert host.snapshot()['observation_batch'] == dict(segments=2,requests=3)
    check(dict(type='action_batch', id='broken', actions=[
        {'action':'claim_units','parameters':{'unit_ids':[a]}}, 7]))
    check(single('end_turn', {'faction':'wei'}))
    check(single('ack_turn_start', {'turn_number':2,'faction':'shu'}), agent='b')
    check(single('register_agent_info', REG, id='failed-send'), send_failure=True)

def test_game_end_wait_and_authoritative_report(hosts, frozen, monkeypatch):
    world, ids, oracle, session, host, check = hosts
    check(single('register_agent_info', REG))
    # Reset both to the same ended world before any lifecycle poll; fresh epoch.
    world.get_singleton_component(c.GameState).game_over = True
    world.get_singleton_component(c.GameState).winner = __import__('rotk_env.prefabs.config',fromlist=['Faction']).Faction.WEI
    session.runtime.reset(export_initial_state(world))
    host.epoch = session.controls.epoch = session.runtime.diagnostics()['epoch']
    saved=[]
    from rotk_env.runtime.settlement import NativeSettlementFormatter
    monkeypatch.setattr(NativeSettlementFormatter,'_save_report_to_files',lambda self,data:saved.append(data))
    wait(session, lambda: host.snapshot()['settlement_started'])
    frozen[0] += 59
    time.sleep(.04)
    assert not saved
    frozen[0] += 1
    wait(session, lambda: host.snapshot()['report_generated'])
    host.update(frozen[0])
    assert len(saved)==1 and session.world.get_singleton_component(__import__('rotk_env.components.settlement_report',fromlist=['SettlementReport']).SettlementReport)
    assert saved[0]['units_info']['wei']['total_units']==2

def test_connection_failure_releases_transport_and_authority(monkeypatch):
    class Broken(Client):
        def connect(self): raise RuntimeError('fixture connection refused')
    with NativeSession(display='none',scenario='chibi-small',seed=42) as session:
        with pytest.raises(RuntimeError,match='connection refused'):
            NativeHubHost(session,'ws://fixture',client_factory=Broken)
        assert not any(t.name=='star-env-hub' for t in __import__('threading').enumerate())
        assert session.runtime.export_state()['singletons']
