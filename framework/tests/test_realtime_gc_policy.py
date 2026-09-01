"""Tests for bounded realtime cyclic-GC control."""

from framework.utils.realtime_gc_policy import (
    GC_POLICY_AUTO,
    GC_POLICY_REALTIME_DEFER,
    RealtimeGCPolicy,
    normalize_gc_policy,
)


class _FakeGC:
    def __init__(self, *, enabled=True):
        self.enabled = enabled
        self.collect_calls = []
        self.counts = (11, 2, 3)

    def isenabled(self):
        return self.enabled

    def enable(self):
        self.enabled = True

    def disable(self):
        self.enabled = False

    def collect(self, generation=2):
        self.collect_calls.append(generation)
        return 7

    def get_count(self):
        return self.counts


def test_realtime_defer_collects_once_disables_then_restores_at_deadline():
    now = [100.0]
    fake = _FakeGC(enabled=True)
    policy = RealtimeGCPolicy(gc_module=fake, clock=lambda: now[0])

    state = policy.activate(GC_POLICY_REALTIME_DEFER, 20.0)

    assert fake.collect_calls == [2]
    assert fake.enabled is False
    assert state["active"] is True
    assert state["full_collect_collected"] == 7
    assert state["deadline_remaining_seconds"] == 20.0

    now[0] = 119.9
    assert policy.tick() is False
    assert fake.enabled is False

    now[0] = 120.0
    assert policy.tick() is True
    assert fake.enabled is True
    assert policy.snapshot()["last_restore_reason"] == "deadline"


def test_restore_preserves_preexisting_disabled_gc_state():
    fake = _FakeGC(enabled=False)
    policy = RealtimeGCPolicy(gc_module=fake, clock=lambda: 50.0)

    policy.activate("realtime-defer", 5.0)
    assert fake.enabled is False
    assert policy.restore("test") is True
    assert fake.enabled is False


def test_auto_mode_is_noop_and_aliases_normalize():
    fake = _FakeGC(enabled=True)
    policy = RealtimeGCPolicy(gc_module=fake, clock=lambda: 1.0)

    state = policy.activate(GC_POLICY_AUTO, 20.0)

    assert state["mode"] == GC_POLICY_AUTO
    assert state["active"] is False
    assert fake.collect_calls == []
    assert fake.enabled is True
    assert normalize_gc_policy("realtime-defer") == GC_POLICY_REALTIME_DEFER
