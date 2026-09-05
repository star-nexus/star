from __future__ import annotations

import pytest

from framework.utils.realtime_gc_policy import RealtimeGCPolicy, normalize_gc_policy


class _FakeGC:
    def __init__(self, *, enabled: bool = True):
        self.enabled = enabled
        self.collected_generations = []

    def isenabled(self):
        return self.enabled

    def collect(self, generation):
        self.collected_generations.append(generation)
        return 7

    def disable(self):
        self.enabled = False

    def enable(self):
        self.enabled = True

    def get_count(self):
        return (1, 2, 3)


def test_realtime_defer_collects_gen2_and_restores_at_deadline():
    fake_gc = _FakeGC(enabled=True)
    now = [100.0]
    policy = RealtimeGCPolicy(gc_module=fake_gc, clock=lambda: now[0])

    state = policy.activate("realtime_defer", 2.0)
    assert fake_gc.collected_generations == [2]
    assert state["mode"] == "realtime_defer"
    assert state["active"] is True
    assert state["automatic_gc_enabled"] is False
    assert state["original_automatic_gc_enabled"] is True
    assert state["full_collect_collected"] == 7

    now[0] = 101.9
    assert policy.tick() is False
    assert fake_gc.enabled is False

    now[0] = 102.0
    assert policy.tick() is True
    assert fake_gc.enabled is True
    assert policy.snapshot()["last_restore_reason"] == "deadline"


def test_realtime_defer_restores_original_disabled_state():
    fake_gc = _FakeGC(enabled=False)
    policy = RealtimeGCPolicy(gc_module=fake_gc, clock=lambda: 10.0)

    policy.activate("realtime_defer", 20.0)
    assert fake_gc.enabled is False
    assert policy.restore("test") is True
    assert fake_gc.enabled is False


def test_gc_policy_aliases_and_validation():
    assert normalize_gc_policy("auto") == "auto"
    assert normalize_gc_policy("realtime-defer") == "realtime_defer"
    assert normalize_gc_policy("defer") == "realtime_defer"
    with pytest.raises(ValueError):
        normalize_gc_policy("always-off")
