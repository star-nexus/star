"""Integration tests for realtime GC policy in formal scale measurements."""

from dataclasses import dataclass
import gc

from framework.ecs.world import World

from rotk_env.components import Camera, FogOfWar
from rotk_env.testing.scale_experiment_measurement import (
    install_scale_experiment_measurement,
)


@dataclass
class _Batch:
    density: float = 1.0
    plans: list = None
    living_units_at_prepare: int = 10
    seed: int = 42
    requested_units: int = 10

    def __post_init__(self):
        if self.plans is None:
            self.plans = list(range(10))


class _Profiler:
    sample_window = 1

    def __init__(self):
        self._frame_open = False
        self.metadata = {"scenario": "gc-policy-test"}

    def reset(self):
        self._frame_open = False

    def start_frame(self):
        self._frame_open = True

    def end_frame(self):
        self._frame_open = False

    def set_metadata(self, **values):
        self.metadata.update(values)

    def set_frame_metric(self, _name, _value):
        pass

    def get_stats(self):
        return {
            "sample_count": 1,
            "min_fps": 50.0,
            "avg_fps": 50.0,
            "max_fps": 50.0,
            "avg_frame_ms": 20.0,
            "p50_frame_ms": 20.0,
            "p95_frame_ms": 20.0,
            "p99_frame_ms": 20.0,
            "active_ms": 18.0,
            "present_ms": 1.0,
            "fps_limiter_wait_ms": 1.0,
            "slow_frame_count": 0,
            "worst_slow_frame": None,
            "sections": {},
            "metadata": dict(self.metadata),
        }


class _Harness:
    def __init__(self):
        self.prepared = _Batch()
        self.calls = 0

    def handle_command(self, command):
        self.calls += 1
        if command.get("command") == "start_sustained_batch":
            return {
                "ok": True,
                "batch_id": 1,
                "duration_seconds": 20.0,
                "motion_phase": command.get("phase", "staggered"),
            }
        return {"ok": True}

    def _active_moving_units(self):
        return 10

    def _living_units(self):
        return list(range(10))


def _world():
    world = World()
    world.add_singleton_component(FogOfWar(enabled=True))
    world.add_singleton_component(Camera(offset_x=0.0, offset_y=0.0, zoom=1.0))
    return world


def test_realtime_defer_is_active_in_snapshot_and_stop_restores_gc():
    original_enabled = gc.isenabled()
    profiler = _Profiler()
    harness = _Harness()
    install_scale_experiment_measurement(harness, _world(), profiler)

    try:
        start = harness.handle_command(
            {
                "command": "start_sustained_batch",
                "phase": "staggered",
                "require_fog": "on",
                "execution_density": 1.0,
                "gc_policy": "realtime_defer",
            }
        )
        assert start["ok"] is True
        assert start["gc_policy"] == "realtime_defer"
        assert start["gc_policy_active"] is True
        assert start["gc_automatic_enabled"] is False
        assert gc.isenabled() is False

        profiler.start_frame()
        snapshot = harness.handle_command({"command": "profile_snapshot"})
        assert snapshot["guards"]["gc_policy_requested"] == "realtime_defer"
        assert snapshot["guards"]["gc_policy_active"] is True
        assert snapshot["guards"]["gc_automatic_enabled"] is False
        assert snapshot["guards"]["gc_policy_matches_requested"] is True
        assert snapshot["context"]["scale_gc_policy"] == "realtime_defer"

        stopped = harness.handle_command({"command": "stop_sustained"})
        assert stopped["gc_policy_restored"] is True
        assert gc.isenabled() is original_enabled
    finally:
        policy = getattr(harness, "_realtime_gc_policy", None)
        if policy is not None:
            policy.restore("test_finally")
        if original_enabled:
            gc.enable()
        else:
            gc.disable()


def test_invalid_gc_policy_is_rejected_before_kickoff():
    profiler = _Profiler()
    harness = _Harness()
    install_scale_experiment_measurement(harness, _world(), profiler)

    result = harness.handle_command(
        {
            "command": "start_sustained_batch",
            "gc_policy": "mystery",
        }
    )

    assert result["ok"] is False
    assert result["error"] == "invalid_gc_policy"
    assert harness.calls == 0
