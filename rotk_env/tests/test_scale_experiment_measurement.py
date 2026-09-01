"""Tests for formal Dynamic World experiment guards and snapshots."""

from types import SimpleNamespace

from framework.ecs.world import World

from rotk_env.components import Camera, FogOfWar
from rotk_env.testing.scale_experiment_measurement import (
    install_scale_experiment_measurement,
)


class _FakeProfiler:
    sample_window = 300

    def __init__(self):
        self._frame_open = False
        self.metadata = {"scenario": "TestMap-8K-scale-5000"}
        self.reset_count = 0

    def reset(self):
        self.reset_count += 1
        self._frame_open = False

    def start_frame(self):
        self._frame_open = True

    def end_frame(self):
        self._frame_open = False

    def set_metadata(self, **values):
        self.metadata.update(values)

    def get_stats(self):
        return {
            "sample_count": 300,
            "avg_fps": 55.0,
            "min_fps": 40.0,
            "max_fps": 62.0,
            "avg_frame_ms": 18.18,
            "p50_frame_ms": 17.0,
            "p95_frame_ms": 22.0,
            "p99_frame_ms": 25.0,
            "active_ms": 15.0,
            "present_ms": 1.2,
            "fps_limiter_wait_ms": 1.98,
            "slow_frame_count": 1,
            "worst_slow_frame": {
                "frame_index": 20,
                "frame_ms": 31.0,
                "active_ms": 29.8,
                "present_ms": 1.2,
                "fps_limiter_wait_ms": 0.0,
                "frame_metrics": {
                    "scale_active_moving_units": 2500,
                    "scale_actual_density": 0.5,
                    "vision_dirty_units": 83,
                },
                "top_sections": [
                    {
                        "name": "MapRenderSystem",
                        "self_ms": 10.0,
                        "inclusive_ms": 10.0,
                        "category": "work",
                    }
                ],
            },
            "sections": {
                "VisionSystem": {
                    "category": "work",
                    "self_ms": 0.8,
                    "inclusive_ms": 0.8,
                    "max_self_ms": 2.0,
                    "max_inclusive_ms": 2.0,
                    "frame_share_pct": 4.4,
                }
            },
            "metadata": dict(self.metadata),
        }


class _FakeHarness:
    def __init__(self):
        self.prepared = SimpleNamespace(density=0.5)
        self.original_calls = 0

    def handle_command(self, command):
        self.original_calls += 1
        if command.get("command") == "start_sustained_batch":
            return {
                "ok": True,
                "batch_id": 1,
                "duration_seconds": 20.0,
                "motion_phase": command.get("phase", "staggered"),
            }
        return {"ok": True}

    def _active_moving_units(self):
        return 2500

    def _living_units(self):
        return list(range(5000))


def _world(*, fog_enabled=True):
    world = World()
    world.add_singleton_component(FogOfWar(enabled=fog_enabled))
    world.add_singleton_component(Camera(offset_x=10.0, offset_y=-5.0, zoom=1.25))
    return world


def test_formal_density_run_rejects_wrong_fog_before_start():
    world = _world(fog_enabled=False)
    profiler = _FakeProfiler()
    harness = _FakeHarness()
    install_scale_experiment_measurement(harness, world, profiler)

    result = harness.handle_command(
        {
            "command": "start_sustained_batch",
            "phase": "staggered",
            "require_fog": "on",
        }
    )

    assert result["ok"] is False
    assert result["error"] == "fog_state_mismatch"
    assert harness.original_calls == 0


def test_staggered_start_schedules_clean_density_curve_epoch_and_snapshot_guards():
    world = _world(fog_enabled=True)
    profiler = _FakeProfiler()
    harness = _FakeHarness()
    install_scale_experiment_measurement(harness, world, profiler)

    result = harness.handle_command(
        {
            "command": "start_sustained_batch",
            "phase": "staggered",
            "require_fog": "on",
        }
    )

    assert result["ok"] is True
    assert result["experiment_kind"] == "dynamic_world_density_curve"
    assert result["measurement_epoch_pending"] is True
    assert result["required_fog"] == "on"
    assert result["camera_start"] == {
        "offset_x": 10.0,
        "offset_y": -5.0,
        "zoom": 1.25,
    }

    # The next frame boundary excludes both planning and kickoff.
    profiler.start_frame()
    assert profiler.reset_count == 1
    assert profiler.metadata["measurement_epoch"] == (
        "dynamic_world_density_curve.density_0.50.staggered"
    )
    assert profiler.metadata["scale_measurement_density"] == 0.5

    snapshot = harness.handle_command({"command": "profile_snapshot"})
    assert snapshot["ok"] is True
    assert snapshot["rolling_window_full"] is True
    assert snapshot["max_frame_ms"] == 25.0
    assert snapshot["guards"]["fog_matches_required"] is True
    assert snapshot["guards"]["camera_unchanged"] is True
    assert snapshot["guards"]["actual_density"] == 0.5
    assert snapshot["sections"]["VisionSystem"]["self_ms"] == 0.8


def test_synchronized_run_is_labeled_burst_resilience():
    world = _world(fog_enabled=True)
    profiler = _FakeProfiler()
    harness = _FakeHarness()
    harness.prepared = SimpleNamespace(density=1.0)
    install_scale_experiment_measurement(harness, world, profiler)

    result = harness.handle_command(
        {
            "command": "start_sustained_batch",
            "phase": "synchronized",
            "require_fog": "on",
        }
    )

    assert result["ok"] is True
    assert result["experiment_kind"] == "dynamic_world_burst_resilience"
    assert "density_1.00.synchronized" in result["measurement_epoch"]
