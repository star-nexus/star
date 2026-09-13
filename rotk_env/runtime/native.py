"""Owned Python interface to the native world; no mutable ECS proxy objects."""
import datetime
import json
import time
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

    def to_wire(self):
        # Transport already normalizes raw payloads. This boundary accepts detached
        # JSON dictionaries; accepting arbitrary Python ECS objects is not a goal.
        params = {} if self.parameters is None else self.parameters
        if not isinstance(params, dict):
            raise TypeError("parameters must be a normalized dictionary")
        registering = self.action == "register_agent_info"
        return dict(
            agent_id=self.agent_id, action=self.action, parameters=params,
            wall_time=time.time() if self.wall_time is None else self.wall_time,
            registration_time=(self.registration_time if self.registration_time is not None
                               else datetime.datetime.now().isoformat()) if registering else "",
            sanitized_base_url=AgentInfoRegistry.sanitize_url(params.get("base_url", "")) if registering else "",
        )


def _decode_result(result):
    if (result.get('operation') == 'get_observation' and result.get('success')
            and result.get('metadata', {}).get('observation_level') == 'unit'):
        area = result['data']['visible_area']
        result['data']['visible_area'] = {tuple(cell) for cell in area['$set']}
    return result


class RustRuntime:
    """Owned native runtime; supported requests do not imply full gameplay readiness."""
    backend = 'rust'

    def __init__(self, initial_state, *, threads=1):
        native = load_native()
        self._native = native(json.dumps(initial_state, allow_nan=False), threads)

    def reset(self, initial_state):
        self._native.reset(json.dumps(initial_state, allow_nan=False))

    def step(self, dt, *, wall_time=None):
        self._native.step(dt, time.time() if wall_time is None else wall_time)

    def execute_action(self, action, parameters=None, *, agent_id, wall_time=None, registration_time=None):
        request = ActionRequest(agent_id, action, parameters, wall_time, registration_time)
        return _decode_result(json.loads(self._native.execute_action_json(json.dumps(request.to_wire(), allow_nan=False))))

    def execute_actions(self, requests):
        """Execute supplied envelopes in order; prior commands are not rolled back on failure.

        Adjacent faction queries share only this call's read context. Caller controls
        admission order; this method never waits to accumulate requests.
        """
        return self.execute_actions_diagnostic(requests)["results"]

    def execute_actions_diagnostic(self, requests):
        """The same request path plus per-read-segment cache-build counts for Lab."""
        wire = [request.to_wire() for request in requests]
        report = json.loads(self._native.execute_actions_json(json.dumps(wire, allow_nan=False)))
        report['results'] = [_decode_result(result) for result in report['results']]
        return report

    def get_faction_state(self, faction, *, agent_id, unit_ids=_UNSET, wall_time=None):
        parameters = {"faction": faction}
        if unit_ids is not _UNSET:
            parameters["unit_ids"] = unit_ids
        return self.execute_action("get_faction_state", parameters, agent_id=agent_id, wall_time=wall_time)

    def finish_human_turn(self, *, wall_time=None):
        """Trusted Framework input, with the legacy human reset-before-check semantics."""
        self._native.finish_human_turn(time.time() if wall_time is None else wall_time)

    def start_capture(self, unit_id, position, *, wall_time=None):
        """Trusted Framework input for timed capture; Agent occupy is immediate."""
        return self._native.start_capture(unit_id, position, time.time() if wall_time is None else wall_time)

    def set_clock(self, *, paused, time_scale=1.0):
        self._native.set_clock(paused, time_scale)

    def export_state(self):
        return json.loads(self._native.export_state_json())

    def diagnostics(self):
        return json.loads(self._native.diagnostics_json())

    def take_presentation_delta(self):
        return json.loads(self._native.take_presentation_delta_json())

    def close(self):
        self._native.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
