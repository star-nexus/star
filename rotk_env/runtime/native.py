"""Owned Python interface to the native world; no mutable ECS proxy objects."""
import datetime
import json
import sys
import time
from functools import wraps
from threading import RLock
from dataclasses import dataclass
from typing import Any
from rotk_env.components.agent_info import AgentInfoRegistry
from .bootstrap import ORACLE_VERSION, NATIVE_API_VERSION

_UNSET = object()


def load_native():
    try:
        import star_native
        from star_native import NativeRuntime, RULES_VERSION
    except ImportError as exc:
        raise RuntimeError('Rust backend is unavailable. Install star-native (developer: uv sync --extra native).') from exc
    if RULES_VERSION != ORACLE_VERSION:
        raise RuntimeError(f'Rust rules version mismatch: {RULES_VERSION}; expected {ORACLE_VERSION}')
    actual_api = getattr(star_native, 'API_VERSION', None)
    if actual_api != NATIVE_API_VERSION:
        raise RuntimeError(f'Rust API version mismatch: {actual_api}; expected {NATIVE_API_VERSION}. Rebuild/install the matching star-native wheel.')
    return NativeRuntime


@dataclass(frozen=True)
class ActionRequest:
    """Local ingress envelope. Identity comes from the trusted caller, not parameters."""
    agent_id: str | None
    action: str | None
    parameters: dict[str, Any] | None = None
    wall_time: float | None = None
    registration_time: str | None = None
    connected_agents: int = 0

    def to_wire(self):
        # Transport already normalizes raw payloads. This boundary accepts detached
        # JSON dictionaries; accepting arbitrary Python ECS objects is not a goal.
        params = {} if self.parameters is None else self.parameters
        if not isinstance(params, dict):
            raise TypeError("parameters must be a normalized dictionary")
        if type(self.connected_agents) is not int or not 0 <= self.connected_agents < 2**64:
            raise ValueError("connected_agents must be a nonnegative u64 transport count")
        registering = self.action == "register_agent_info"
        request = dict(
            agent_id=self.agent_id, action=self.action, parameters=params,
            wall_time=time.time() if self.wall_time is None else self.wall_time,
            registration_time=(self.registration_time if self.registration_time is not None
                               else datetime.datetime.now().isoformat()) if registering else "",
            sanitized_base_url=AgentInfoRegistry.sanitize_url(params.get("base_url", "")) if registering else "",
            connected_agents=self.connected_agents,
        )
        if self.action == "report_llm_stats":
            request["integer_string_limit"] = sys.get_int_max_str_digits()
        return request


def _decode_result(result):
    if (result.get('operation') == 'get_observation' and result.get('success')
            and result.get('metadata', {}).get('observation_level') == 'unit'):
        area = result['data']['visible_area']
        result['data']['visible_area'] = {tuple(cell) for cell in area['$set']}
    return result


def _serialized(method):
    """Keep native queries plus Python display capture in one admission boundary."""
    @wraps(method)
    def invoke(self, *args, **kwargs):
        with self._admission_lock:
            return method(self, *args, **kwargs)
    return invoke


def _complete_result(action, result):
    result = _decode_result(result)
    if action == 'get_faction_state_vlm' and result.get('success'):
        from framework.engine.frame_capture import capture_rendered_frame
        frame, error = capture_rendered_frame()
        result['frame_base64'] = frame
        result['frame_format'] = 'png' if frame else None
        if error is not None:
            result['frame_error'] = error
    return result


class _AdmittedObservationSegment:
    """Private bounded research scope; ordinary methods remain native barriers."""
    def __init__(self, runtime, mode, max_requests, diagnostics):
        if mode not in ('single', 'segment_no_reuse', 'segment_encoded'):
            raise ValueError('invalid observation segment mode')
        if type(max_requests) is not int or not 2 <= max_requests <= 4:
            raise ValueError('invalid observation segment limit')
        self.runtime = runtime
        self.mode = mode
        self.maximum = max_requests
        self.diagnostics = diagnostics
        self.token = None
        self.report = None
        self.entered = False

    def __enter__(self):
        if self.entered:
            raise RuntimeError('observation segment context already entered')
        self.runtime._admission_lock.acquire()
        try:
            if self.mode != 'single':
                self.token = self.runtime._native._begin_observation_segment_json(
                    self.mode, self.maximum, self.diagnostics)
            self.entered = True
            return self
        except BaseException:
            self.runtime._admission_lock.release()
            raise

    def get_faction_state_json(self, faction, *, agent_id, unit_ids=_UNSET, wall_time=None):
        if not self.entered:
            raise RuntimeError('observation segment context is not active')
        with self.runtime._admission_lock:
            if self.token is None:
                return self.runtime.get_faction_state_json(
                    faction, unit_ids=unit_ids, agent_id=agent_id, wall_time=wall_time)
            params = {'faction': faction}
            if unit_ids is not _UNSET:
                params['unit_ids'] = unit_ids
            request = ActionRequest(agent_id, 'get_faction_state', params, wall_time)
            return self.runtime._native._observation_segment_request_json(
                self.token, json.dumps(request.to_wire(), allow_nan=False))

    def __exit__(self, exc_type, exc, tb):
        try:
            if self.token is not None:
                try:
                    report = self.runtime._native._end_observation_segment_json(self.token)
                    self.report = None if report is None else json.loads(report)
                except BaseException:
                    # Preserve the initiating failure when its native mutex is
                    # already poisoned. The context cannot be used again.
                    if exc_type is None:
                        raise
        finally:
            self.entered = False
            self.token = None
            self.runtime._admission_lock.release()


class RustRuntime:
    """Owned native runtime; supported requests do not imply full gameplay readiness."""
    backend = 'rust'

    def __init__(self, initial_state, *, threads=1):
        self._admission_lock = RLock()
        native = load_native()
        self._native = native(json.dumps(initial_state, allow_nan=False), threads)

    def _admitted_observation_segment(self, mode, *, max_requests=4, diagnostics=False):
        return _AdmittedObservationSegment(self, mode, max_requests, diagnostics)

    @_serialized
    def reset(self, initial_state):
        self._native.reset(json.dumps(initial_state, allow_nan=False))

    @_serialized
    def step(self, dt, *, wall_time=None):
        self._native.step(dt, time.time() if wall_time is None else wall_time)

    @_serialized
    def host_status(self, *, expected_epoch=None):
        """Small authoritative lifecycle facts; no world/display export."""
        return json.loads(self._native.host_status_json(expected_epoch))

    @_serialized
    def record_message(self, agent_id, *, expected_epoch=None):
        """Trusted transport accounting, once per admitted inbound message.

        Preserve legacy placement: after a single action, before a batch. An
        unregistered sender increments its own counter then raises, as in Python.
        """
        self._native.record_message(agent_id, expected_epoch)

    @_serialized
    def turn_start_context(self, *, wall_time=None, expected_epoch=None):
        """Read after successful Agent end_turn on the owner admission thread.

        Return registry-then-stats candidates for the transport's legacy set
        insertion and connected-ID filtering. Calling this does not send, ACK,
        retry or change a turn. Human turn notifications are not added implicitly.
        """
        return json.loads(self._native.turn_start_context_json(
            time.time() if wall_time is None else wall_time, expected_epoch))

    @_serialized
    def prepare_game_end(self, connected_agents, *, wall_time=None, expected_epoch=None):
        """Update native collection counters and return an ordered delivery plan.

        Called by the scene host, never by an Agent verb. Transport delivery,
        once-only notification tracking and retries remain with that host.
        """
        return json.loads(self._native.prepare_game_end_json(
            list(connected_agents), time.time() if wall_time is None else wall_time, expected_epoch))

    @_serialized
    def execute_control(self, kind, *, wall_time=None, expected_epoch=None, **parameters):
        """Trusted local UI input; never use this method for Agent/Hub requests.

        UI selection/targeting determines local human control. This boundary
        mirrors existing MovementSystem/CombatSystem/button calls, without an
        Agent registration, ownership override or transport request counter.
        """
        command = dict(kind=kind, **parameters)
        return json.loads(self._native.execute_control_json(
            json.dumps(command, allow_nan=False),
            time.time() if wall_time is None else wall_time,
            expected_epoch,
        ))

    @_serialized
    def execute_action(self, action, parameters=None, *, agent_id, wall_time=None, registration_time=None, connected_agents=0):
        request = ActionRequest(agent_id, action, parameters, wall_time, registration_time, connected_agents)
        return _complete_result(action, json.loads(self._native.execute_action_json(json.dumps(request.to_wire(), allow_nan=False))))

    def execute_actions(self, requests):
        """Execute supplied envelopes in order; prior commands are not rolled back on failure.

        Adjacent faction queries share only this call's read context. Caller controls
        admission order; this method never waits to accumulate requests.
        """
        return self.execute_actions_diagnostic(requests)["results"]

    @_serialized
    def execute_actions_diagnostic(self, requests):
        """The same request path plus per-read-segment cache-build counts for Lab."""
        wire = [request.to_wire() for request in requests]
        payload = json.dumps(wire, allow_nan=False)
        if not any(request['action'] == 'get_faction_state_vlm' for request in wire):
            report = json.loads(self._native.execute_actions_json(payload))
            report['results'] = [_decode_result(result) for result in report['results']]
            return report
        # Decode the entire batch first: a malformed later envelope must not
        # cause an earlier action to execute just because a display read split it.
        self._native._validate_requests_json(payload)
        wire = json.loads(payload)  # Freeze the entire admitted batch before a capture can yield.
        report = dict(results=[], observation_segments=[])
        def flush(segment):
            if not segment:
                return
            partial = json.loads(self._native.execute_actions_json(json.dumps(segment, allow_nan=False)))
            offset = len(report['results'])
            report['results'].extend(_decode_result(result) for result in partial['results'])
            for item in partial['observation_segments']:
                report['observation_segments'].append({**item, 'start': item['start'] + offset,
                                                      'end': item['end'] + offset})
        segment = []
        for request in wire:
            if request['action'] != 'get_faction_state_vlm':
                segment.append(request)
                continue
            flush(segment)
            segment = []
            result = json.loads(self._native.execute_action_json(json.dumps(request, allow_nan=False)))
            report['results'].append(_complete_result(request['action'], result))
        flush(segment)
        return report

    def get_faction_state(self, faction, *, agent_id, unit_ids=_UNSET, wall_time=None):
        parameters = {"faction": faction}
        if unit_ids is not _UNSET:
            parameters["unit_ids"] = unit_ids
        return self.execute_action("get_faction_state", parameters, agent_id=agent_id, wall_time=wall_time)

    @_serialized
    def get_faction_state_json(self, faction, *, agent_id, unit_ids=_UNSET, wall_time=None):
        """Return owned JSON for transport without a server decode/encode round trip.

        Uses the ordinary authenticated action gate and admission lock. The caller
        may forward this immutable string; the client still decodes the complete
        response. No fields, freshness or permission checks are omitted. JSON
        spelling is not a byte-level compatibility contract with Python encoders.
        """
        parameters = {"faction": faction}
        if unit_ids is not _UNSET:
            parameters["unit_ids"] = unit_ids
        request = ActionRequest(agent_id, "get_faction_state", parameters, wall_time)
        return self._native.execute_action_json(json.dumps(request.to_wire(), allow_nan=False))

    @_serialized
    def finish_human_turn(self, *, wall_time=None, expected_epoch=None):
        """Trusted Framework input, with the legacy human reset-before-check semantics."""
        self._native.finish_human_turn(time.time() if wall_time is None else wall_time, expected_epoch)

    @_serialized
    def start_capture(self, unit_id, position, *, wall_time=None, expected_epoch=None):
        """Trusted Framework input for timed capture; Agent occupy is immediate."""
        return self._native.start_capture(unit_id, position, time.time() if wall_time is None else wall_time, expected_epoch)

    @_serialized
    def set_clock(self, *, paused, time_scale=1.0):
        self._native.set_clock(paused, time_scale)

    @_serialized
    def export_state(self, *, expected_epoch=None):
        return json.loads(self._native.export_state_json(expected_epoch))

    @_serialized
    def diagnostics(self):
        return json.loads(self._native.diagnostics_json())

    @_serialized
    def take_presentation_delta(self, *, expected_epoch=None):
        return json.loads(self._native.take_presentation_delta_json(expected_epoch))

    @_serialized
    def close(self):
        self._native.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
