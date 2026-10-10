"""ENV-owned Hub orchestration. Protocol and participant clients stay unchanged.

One bounded transport worker owns the legacy message/ACK/retry state. Native
operations enter AuthorityRuntime; network waits never occupy its owner thread.
The creating display thread alone publishes the resulting report and HUD facts.
"""
from copy import deepcopy
import json
import os
from queue import Empty, Full, Queue
from threading import Event, Lock, Thread, get_ident
import time

from rotk_env.components.settlement_report import SettlementReport
from rotk_env.prefabs.config import GameConfig
from rotk_env.systems.llm_system import LLMSystem, SyncEnvClient, _inbound_id
from .authority import AuthorityRuntime
from .native import ActionRequest
from .settlement import NativeSettlementFormatter, report_world


class NativeHubHost(LLMSystem):
    """Reuse ENV transport policy, replacing only its World execution boundary."""
    def __init__(self, session, server_url, env_id=None, *, client_factory=SyncEnvClient):
        super().__init__(server_url=server_url, env_id=env_id)
        if not isinstance(session.runtime, AuthorityRuntime):
            raise ValueError('Native Hub requires the single authority executor')
        self.session = session
        self.runtime = session.runtime
        self.epoch = session.controls.epoch
        self._ui_ident = get_ident()
        self._inbox = Queue(maxsize=32)
        self._accepting = Event()
        self._accepting.set()
        self._ready = Event()
        self._lock = Lock()
        self._failure = None
        self._report = None
        self._report_installed = False
        self.report_generated = False
        self.game_end_time = None
        self.timeout_seconds = 60.0
        self._next_service = time.monotonic()
        self._facts = dict(connected=False, registered_agents=0, received_messages=0,
                           completed_messages=0, max_inbox=0, report_pending=False)
        self._registered = set()
        self._batch_metrics = dict(segments=0, requests=0)
        # Membership is all on the worker; these handlers are never Python World calls.
        self.system_actions = self._init_system_actions()
        self.client = client_factory(server_url=server_url,
                                     env_id=env_id or os.environ.get('ENV_ID', 'env_1'))
        for name in ('message', 'connect', 'disconnect', 'error'):
            self.client.add_hub_listener(name, lambda data, name=name: self._enqueue(name, data))
        self._thread = Thread(target=self._run, name='star-env-hub')
        self._thread.start()
        try:
            self.client.connect()
            if not self._ready.wait(10):
                raise RuntimeError('Hub connection confirmation was not received')
        except BaseException:
            self.close()
            raise

    def _enqueue(self, kind, data):
        packet = (kind, deepcopy(data))
        while self._accepting.is_set():
            try:
                self._inbox.put(packet, timeout=.05)
                with self._lock:
                    self._facts['max_inbox'] = max(self._facts['max_inbox'], self._inbox.qsize())
                return
            except Full:
                continue

    def _run(self):
        try:
            while True:
                try:
                    packet = self._inbox.get(timeout=max(0, self._next_service-time.monotonic()))
                except Empty:
                    packet = None
                if packet is not None:
                    kind, data = packet
                    if kind == 'close':
                        break
                    if kind == 'message':
                        with self._lock:
                            self._facts['received_messages'] += 1
                        super().on_message(data)
                        with self._lock:
                            self._facts['completed_messages'] += 1
                    elif kind == 'connect':
                        with self._lock:
                            self._facts['connected'] = True
                        self._ready.set()
                        print('LLMSystem connected', data, flush=True)
                    elif kind == 'disconnect':
                        with self._lock:
                            self._facts['connected'] = False
                        print('LLMSystem disconnected', data, flush=True)
                    else:
                        print('LLMSystem error:', data, flush=True)
                if time.monotonic() >= self._next_service:
                    self._service(time.time())
                    self._next_service = time.monotonic() + 1/GameConfig.FPS
        except BaseException as exc:
            with self._lock:
                self._failure = exc
        finally:
            self._accepting.clear()

    def _record_message(self, agent_id, _params):
        self.runtime.record_message(agent_id, expected_epoch=self.epoch)

    def _process_action_request(self, agent_id, action_id, action, params, *, send_response):
        if action:
            self._pending_turn_start_ack.pop(agent_id, None)
        try:
            report = self.runtime.execute_host_action(action, params, agent_id=agent_id,
                connected_agents=len(self.client.connected_agents), defer_accounting=send_response)
            result = report['response']
            if action == 'register_agent_info' and result.get('success'):
                self._registered.add(agent_id)
                with self._lock:
                    self._facts['registered_agents'] = len(self._registered)
            if report['turn_context'] is not None:
                self._notify_turn(report['turn_context'])
            if send_response and agent_id:
                self.client.response_to_agent(agent_id, action_id, result, 'str')
            if report['accounting'] is not None:
                counted = self.runtime.commit_host_action(report['accounting'], expected_epoch=self.epoch)
                if not counted.get('success'):
                    result = counted
                    if send_response and agent_id:
                        self.client.response_to_agent(agent_id, action_id, result, 'str')
            return result
        except Exception as exc:
            result = self._create_system_error_response(action or 'unknown', str(exc), 2012)
            if send_response and agent_id:
                try:
                    self.client.response_to_agent(agent_id, action_id, result, 'str')
                except Exception as send_error:
                    print(f'[NativeHubHost] Failed to send error response: {send_error}')
            return result

    def _process_batch_actions(self, actions, agent_id, batch_id):
        # Decode in original item order. A malformed later item must not prevent
        # the successful prefix from executing. No wait to accumulate requests.
        results = []
        index = 0
        while index < len(actions):
            item = actions[index]
            if isinstance(item, dict) and item.get('action') == 'get_faction_state':
                requests, identifiers = [], []
                cursor = index
                while cursor < len(actions):
                    row = actions[cursor]
                    if not isinstance(row, dict) or row.get('action') != 'get_faction_state':
                        break
                    params = self._prepare_parameters(row.get('parameters', {}))
                    if not isinstance(params, dict):
                        break
                    try:
                        json.dumps(params, allow_nan=False)
                    except (ValueError, TypeError):
                        break
                    requests.append(ActionRequest(agent_id, 'get_faction_state', params,
                                                  connected_agents=len(self.client.connected_agents)))
                    identifiers.append(_inbound_id(row.get('id'), fallback=f'{batch_id}_{cursor}'))
                    cursor += 1
                if requests:
                    self._pending_turn_start_ack.pop(agent_id, None)
                    replies = self.runtime.execute_actions(requests)
                    self._batch_metrics['segments'] += 1
                    self._batch_metrics['requests'] += len(requests)
                    results.extend(dict(id=identifier, action='get_faction_state', response=reply,
                                        success=reply.get('success', True))
                                   for identifier, reply in zip(identifiers, replies))
                    index = cursor
                    continue
            # Shared legacy hook supplies missing-name/error behavior and IDs.
            row = dict(item) if isinstance(item, dict) else item
            if isinstance(row, dict):
                row['id'] = _inbound_id(row.get('id'), fallback=f'{batch_id}_{index}')
            rows = super()._process_batch_actions([row], agent_id, batch_id)
            results.extend(rows)
            index += 1
        return results

    def _notify_turn(self, context):
        targets = set()
        for candidate in context['candidates']:
            targets.add(candidate)
        now = time.time()
        for agent in (aid for aid in targets if aid in self.client.connected_agents):
            try:
                self.send_message(context['notification'], target=dict(type='agent', id=agent))
                self._pending_turn_start_ack[agent] = dict(
                    turn_number=context['notification']['turn_number'],
                    faction_key=context['notification']['faction'],
                    next_retry_time=now+self._turn_start_retry_interval, retry_count=0,
                    notification=context['notification'])
            except Exception as exc:
                print(f'[NativeHubHost] Failed to send turn_start: {exc}')

    def _service(self, wall_time):
        state = self.runtime.host_status(expected_epoch=self.epoch)
        if not state['game_over']:
            for agent in list(self._pending_turn_start_ack):
                entry = self._pending_turn_start_ack[agent]
                if wall_time < entry['next_retry_time']:
                    continue
                entry['retry_count'] += 1
                if entry['retry_count'] > self._turn_start_max_retries:
                    self._pending_turn_start_ack.pop(agent, None)
                    continue
                try:
                    self.send_message(entry['notification'], target=dict(type='agent', id=agent))
                    entry['next_retry_time'] = wall_time+self._turn_start_retry_interval
                except Exception as exc:
                    print(f'[NativeHubHost] Failed to resend turn_start: {exc}')
            return
        if not self.game_end_notified:
            plan = self.runtime.prepare_game_end(list(self.client.connected_agents),
                                                wall_time=wall_time, expected_epoch=self.epoch)
            for agent in plan['targets']:
                try:
                    self.send_message(plan['notification'], target=dict(type='agent', id=agent))
                except Exception as exc:
                    print(f'[NativeHubHost] Failed to send game_end: {exc}')
            self.game_end_notified = True
            self._pending_turn_start_ack.clear()
        if self.report_generated:
            return
        if self.game_end_time is None:
            self.game_end_time = wall_time
            return
        if wall_time-self.game_end_time < self.timeout_seconds:
            return
        with self._lock:
            self._facts['report_pending'] = True
        snapshot = self.runtime.export_state(expected_epoch=self.epoch)
        view = report_world(snapshot)
        try:
            formatter = NativeSettlementFormatter(snapshot['interface']['report_context'])
            formatter.initialize(view)
            formatter._generate_settlement_report()
            report = view.get_singleton_component(SettlementReport)
            with self._lock:
                self._report = report
                self._facts['report_pending'] = False
            self.report_generated = True
        finally:
            view.reset()

    def snapshot(self):
        with self._lock:
            return dict(self._facts, report_generated=self.report_generated,
                        settlement_started=self.game_end_time is not None,
                        observation_batch=dict(self._batch_metrics),
                        failure=None if self._failure is None else repr(self._failure))

    def update(self, wall_time):
        if get_ident() != self._ui_ident:
            raise RuntimeError('Native Hub presentation requires the display thread')
        with self._lock:
            failure, report = self._failure, self._report
        if failure is not None:
            raise RuntimeError('Native Hub host stopped') from failure
        if report is not None and not self._report_installed:
            self.session.world.add_singleton_component(report)
            self._report_installed = True
        self.session.world._native_hub_facts = self.snapshot()

    def close(self):
        if get_ident() != self._ui_ident:
            raise RuntimeError('Native Hub close requires the display thread')
        if getattr(self, '_closed', False):
            return
        self._accepting.clear()
        error = None
        def drain():
            nonlocal error
            try:
                self.runtime.pump()
            except BaseException as exc:
                error = error or exc
                # Release publication/capture fences even if the projection
                # failed. The authority close path joins its owner safely.
                try:
                    self.runtime.close()
                except BaseException as closed_error:
                    error = error or closed_error
        if self._thread.is_alive():
            while True:
                try:
                    self._inbox.put_nowait(('close', None))
                    break
                except Full:
                    drain()
                    self._thread.join(.01)
                    if not self._thread.is_alive():
                        break
            while self._thread.is_alive():
                drain()
                self._thread.join(.01)
        try:
            self.client.disconnect()
        finally:
            self._closed = True
        if error is not None:
            raise error
