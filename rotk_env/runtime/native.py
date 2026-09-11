"""Owned Python interface to the native world; no mutable ECS proxy objects."""
import json
import time
from .bootstrap import ORACLE_VERSION


def load_native():
    try:
        from star_native import NativeRuntime, RULES_VERSION
    except ImportError as exc:
        raise RuntimeError('Rust backend is unavailable. Install star-native (developer: uv sync --extra native).') from exc
    if RULES_VERSION != ORACLE_VERSION:
        raise RuntimeError(f'Rust rules version mismatch: {RULES_VERSION}; expected {ORACLE_VERSION}')
    return NativeRuntime


class RustRuntime:
    """R1 lifecycle/clock interface; gameplay readiness is advertised explicitly."""
    backend = 'rust'

    def __init__(self, initial_state, *, threads=1):
        native = load_native()
        self._native = native(json.dumps(initial_state, allow_nan=False), threads)

    def reset(self, initial_state):
        self._native.reset(json.dumps(initial_state, allow_nan=False))

    def step(self, dt, *, wall_time=None):
        self._native.step(dt, time.time() if wall_time is None else wall_time)

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
