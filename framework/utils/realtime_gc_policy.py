"""Controlled cyclic-GC policy for latency-sensitive realtime phases.

CPython reference counting continues to reclaim ordinary short-lived objects when
cyclic GC is disabled. This policy only defers the automatic cyclic collector
inside an explicitly bounded realtime window, then restores the caller's prior
GC-enabled state.

The policy is intentionally generic and side-effect free until ``activate`` is
called. Benchmark/control layers can therefore A/B ``auto`` against
``realtime_defer`` without changing normal application defaults.
"""

from __future__ import annotations

import gc
import time
from typing import Any, Dict, Optional

GC_POLICY_AUTO = "auto"
GC_POLICY_REALTIME_DEFER = "realtime_defer"
_GC_POLICY_ALIASES = {
    "auto": GC_POLICY_AUTO,
    "default": GC_POLICY_AUTO,
    "realtime_defer": GC_POLICY_REALTIME_DEFER,
    "realtime-defer": GC_POLICY_REALTIME_DEFER,
    "defer": GC_POLICY_REALTIME_DEFER,
}


def normalize_gc_policy(value: object) -> str:
    normalized = str(value if value is not None else GC_POLICY_AUTO).strip().lower()
    normalized = _GC_POLICY_ALIASES.get(normalized, normalized)
    if normalized not in {GC_POLICY_AUTO, GC_POLICY_REALTIME_DEFER}:
        raise ValueError(
            "gc_policy must be one of: auto, realtime_defer (or realtime-defer)"
        )
    return normalized


class RealtimeGCPolicy:
    """Temporarily defer CPython cyclic GC during one bounded realtime phase."""

    def __init__(self, *, gc_module=gc, clock=time.monotonic):
        self._gc = gc_module
        self._clock = clock
        self.mode = GC_POLICY_AUTO
        self.active = False
        self._deadline: Optional[float] = None
        self._original_enabled: Optional[bool] = None
        self.activation_serial = 0
        self.full_collect_ms = 0.0
        self.full_collect_collected = 0
        self.last_restore_reason = ""

    def activate(self, mode: object, duration_seconds: float) -> Dict[str, Any]:
        """Activate a policy for ``duration_seconds`` and return its state.

        ``realtime_defer`` performs one generation-2 collection immediately,
        then disables automatic cyclic GC. The caller should invoke this after
        expensive realtime kickoff allocation but before the measured hot loop.
        ``auto`` leaves CPython GC untouched.
        """
        requested = normalize_gc_policy(mode)
        duration = max(0.0, float(duration_seconds))

        # Starting another phase must first restore the previous caller state.
        if self.active:
            self.restore("replaced")

        self.mode = requested
        self.full_collect_ms = 0.0
        self.full_collect_collected = 0
        self.last_restore_reason = ""
        self._deadline = None
        self._original_enabled = None

        if requested == GC_POLICY_AUTO:
            return self.snapshot()

        self._original_enabled = bool(self._gc.isenabled())
        t0 = time.perf_counter_ns()
        self.full_collect_collected = int(self._gc.collect(2))
        self.full_collect_ms = (time.perf_counter_ns() - t0) / 1_000_000.0
        self._gc.disable()
        self.active = True
        self.activation_serial += 1
        self._deadline = self._clock() + duration if duration > 0.0 else self._clock()
        return self.snapshot()

    def tick(self) -> bool:
        """Restore the prior GC state once the bounded realtime window expires."""
        if not self.active or self._deadline is None:
            return False
        if self._clock() < self._deadline:
            return False
        return self.restore("deadline")

    def restore(self, reason: str = "manual") -> bool:
        """Restore the exact automatic-GC enabled state observed at activation."""
        if not self.active:
            return False

        original_enabled = bool(self._original_enabled)
        if original_enabled:
            self._gc.enable()
        else:
            self._gc.disable()

        self.active = False
        self._deadline = None
        self._original_enabled = None
        self.last_restore_reason = str(reason)
        return True

    def snapshot(self) -> Dict[str, Any]:
        remaining = None
        if self.active and self._deadline is not None:
            remaining = max(0.0, self._deadline - self._clock())
        counts = tuple(int(value) for value in self._gc.get_count())
        return {
            "mode": self.mode,
            "active": bool(self.active),
            "automatic_gc_enabled": bool(self._gc.isenabled()),
            "original_automatic_gc_enabled": self._original_enabled,
            "full_collect_ms": round(float(self.full_collect_ms), 6),
            "full_collect_collected": int(self.full_collect_collected),
            "deadline_remaining_seconds": (
                round(float(remaining), 6) if remaining is not None else None
            ),
            "activation_serial": int(self.activation_serial),
            "last_restore_reason": self.last_restore_reason,
            "gc_count": counts,
        }
