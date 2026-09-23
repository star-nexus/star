"""Transport authority without copying Units, reports or Python gameplay state."""
from copy import deepcopy
import json
import pytest

pytest.importorskip('star_native')
from rotk_env import components as c
from rotk_env.prefabs.config import Faction
from rotk_env.runtime.bootstrap import export_initial_state
from rotk_env.runtime.native import RustRuntime
from rotk_env.runtime.settlement import OfflineSettlementHost
from rotk_env.runtime.session import NativeSession
from rotk_env.systems.llm_system import LLMSystem
from rotk_env.tests.test_native_turn import setup
from rotk_env.tests.test_native_request_batch import frozen

REG = dict(provider='synthetic', model_id='model', base_url='https://host')


def call(llm, runtime, agent, action, params):
    expected = llm._process_action_request(agent_id=agent, action_id=0, action=action,
                                         params=deepcopy(params), send_response=False)
    actual = runtime.execute_action(action, deepcopy(params), agent_id=agent)
    assert actual == json.loads(json.dumps(expected))
    return actual


@pytest.mark.parametrize('threads', [1, 2, 4])
@pytest.mark.parametrize('agent', [None, '', 'unknown', 'a', 'b'])
def test_message_accounting_full_state_and_partial_failure_match_python(threads, agent, frozen):
    world, _, _, llm = setup('none')
    try:
        with RustRuntime(export_initial_state(world), threads=threads) as runtime:
            for aid, faction in [('a', 'wei'), ('b', 'shu')]:
                call(llm, runtime, aid, 'register_agent_info', dict(REG, faction=faction))
            for _ in range(3):
                if agent == 'unknown':
                    with pytest.raises(RuntimeError) as old:
                        llm._record_message(agent, None)
                    with pytest.raises(RuntimeError) as new:
                        runtime.record_message(agent, expected_epoch=1)
                    assert str(new.value) == str(old.value)
                else:
                    llm._record_message(agent, None)
                    runtime.record_message(agent, expected_epoch=1)
                assert runtime.export_state() == export_initial_state(world)
            # Re-registration changes the stats mapping, even though the old
            # faction's registry entry survives. Message stats follow the mapping.
            call(llm, runtime, 'a', 'register_agent_info', dict(REG, faction='shu'))
            llm._record_message('a', None); runtime.record_message('a')
            assert runtime.export_state() == export_initial_state(world)
    finally:
        world.reset()


@pytest.mark.parametrize('count', [0, 2**64-1, 10**100])
def test_message_counters_do_not_overflow_or_change_action_counts(count, frozen):
    world, _, _, llm = setup('none')
    try:
        llm._process_action_request(agent_id='a', action_id=0, action='register_agent_info',
                                   params=dict(REG, faction='wei'), send_response=False)
        stats = world.get_singleton_component(c.GameStats)
        stats.interaction_counts_by_agent['a'] = count
        stats.interaction_counts_by_faction[Faction.WEI] = count
        with RustRuntime(export_initial_state(world)) as runtime:
            llm._record_message('a', None); runtime.record_message('a')
            assert runtime.export_state() == export_initial_state(world)
    finally:
        world.reset()


@pytest.mark.parametrize('batch', [False, True])
def test_first_registration_message_retains_legacy_counting_position(batch, frozen):
    world, _, _, llm = setup('none')
    try:
        with RustRuntime(export_initial_state(world)) as runtime:
            if batch:
                # Legacy on_message aborts this batch before registration.
                with pytest.raises(RuntimeError): llm._record_message('first', None)
                with pytest.raises(RuntimeError): runtime.record_message('first')
            else:
                call(llm, runtime, 'first', 'register_agent_info', dict(REG, faction='wei'))
                llm._record_message('first', None); runtime.record_message('first')
            assert runtime.export_state() == export_initial_state(world)
    finally:
        world.reset()


@pytest.mark.parametrize('threads', [1, 2, 4])
@pytest.mark.parametrize('connected', [[], ['a'], ['b', 'c', 'unknown', 'a'], [f'id{i}' for i in range(30)]])
def test_turn_candidates_reproduce_legacy_notification_order_and_stale_registry(threads, connected, frozen, monkeypatch):
    world, _, _, llm = setup('none')
    sent = []
    monkeypatch.setattr(llm, 'send_message', lambda payload, *, target: sent.append((deepcopy(payload), target['id'])))
    llm.client.connected_agents = dict.fromkeys(connected, {})
    try:
        with RustRuntime(export_initial_state(world), threads=threads) as runtime:
            agents = [('a', 'wei'), ('b', 'shu'), ('c', 'shu')] + [(f'id{i}', 'shu' if i % 2 else 'wei') for i in range(30)]
            for aid, faction in agents:
                call(llm, runtime, aid, 'register_agent_info', dict(REG, faction=faction))
            call(llm, runtime, 'b', 'register_agent_info', dict(REG, faction='wei'))
            # b remains in Shu's registry. Do not "fix" inherited targeting.
            for aid, faction in [('a', 'wei'), ('c', 'shu')]:
                sent.clear()
                assert call(llm, runtime, aid, 'end_turn', {'faction': faction})['success']
                before = runtime.export_state()
                context = runtime.turn_start_context(expected_epoch=1)
                targets = set()
                for candidate in context['candidates']:
                    targets.add(candidate)
                delivered = [(context['notification'], target) for target in targets if target in connected]
                assert delivered == sent
                assert runtime.export_state() == before == export_initial_state(world)
                status = runtime.host_status(expected_epoch=1)
                assert status == {key: before['singletons']['GameState'][key]
                                  for key in ('game_over', 'current_player', 'turn_number', 'winner')}
                context['candidates'].clear(); status['game_over'] = True
                assert runtime.export_state() == before
    finally:
        world.reset()


@pytest.mark.parametrize('method', ['host_status', 'record_message', 'turn_start_context'])
def test_host_boundary_rejects_stale_epoch_and_closed_runtime(method, frozen):
    world, _, _, _ = setup('none')
    try:
        initial = export_initial_state(world)
        with RustRuntime(initial) as runtime:
            args = ('agent',) if method == 'record_message' else ()
            runtime.reset(initial)
            with pytest.raises(RuntimeError, match='epoch'):
                getattr(runtime, method)(*args, expected_epoch=1)
            assert runtime.export_state() == initial
            runtime.close()
            with pytest.raises(RuntimeError, match='closed'):
                getattr(runtime, method)(*args, expected_epoch=2)
    finally:
        world.reset()


@pytest.mark.parametrize('wall', [float('nan'), float('inf'), -float('inf')])
def test_turn_context_rejects_invalid_time_without_writes(wall, frozen):
    world, _, _, _ = setup('none')
    try:
        initial = export_initial_state(world)
        with RustRuntime(initial) as runtime:
            with pytest.raises(RuntimeError, match='finite'):
                runtime.turn_start_context(wall_time=wall)
            assert runtime.export_state() == initial
    finally:
        world.reset()


@pytest.mark.parametrize('ended', [False, True])
def test_settlement_trigger_uses_authority_even_when_display_is_wrong(ended, monkeypatch, frozen):
    with NativeSession(display='none', mode='real_time', scenario='chibi-small', seed=42) as session:
        if ended:
            # Build a new authority epoch, then attach fresh controls as reset
            # users must. The display copy will deliberately contradict it.
            initial = session.runtime.export_state()
            initial['singletons']['GameState'].update(game_over=True, winner='wei')
            session.runtime.reset(initial)
            session.controls.epoch = session.runtime.diagnostics()['epoch']
        session.world.get_singleton_component(c.GameState).game_over = not ended
        monkeypatch.setattr(session.runtime, 'export_state', lambda **kw: pytest.fail('full world exported before deadline'))
        host = OfflineSettlementHost(session)
        host.update(frozen[0])
        assert host.notified is ended
        assert (host.game_end_time is not None) is ended


@pytest.mark.parametrize('agent', [None, '', 'unknown'])
def test_message_creates_missing_stats_like_legacy(agent, frozen):
    world, _, _, llm = setup('none')
    try:
        world.remove_singleton_component(c.GameStats)
        with RustRuntime(export_initial_state(world)) as runtime:
            if agent:
                with pytest.raises(RuntimeError): llm._record_message(agent, None)
                with pytest.raises(RuntimeError): runtime.record_message(agent)
            else:
                llm._record_message(agent, None); runtime.record_message(agent)
            assert runtime.export_state() == export_initial_state(world)
    finally:
        world.reset()


def test_turn_context_retains_game_over_edge_and_is_not_a_new_action(frozen):
    world, _, _, llm = setup('none')
    try:
        state = world.get_singleton_component(c.GameState)
        state.game_over = True
        with RustRuntime(export_initial_state(world)) as runtime:
            context = runtime.turn_start_context()
            assert context['notification']['faction'] == state.current_player.value
            assert context['candidates'] == []
            before = runtime.export_state()
            assert runtime.host_status()['game_over']
            assert runtime.export_state() == before
    finally:
        world.reset()
