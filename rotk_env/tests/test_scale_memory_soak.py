"""Tests for safe-point memory soak commands."""

from framework.ecs.world import World

from rotk_env.components import UnitObservation, VisibilityTracker
from rotk_env.prefabs.config import Faction
from rotk_env.testing import scale_memory_soak
from rotk_env.testing.scale_memory_soak import install_scale_memory_soak


class _Policy:
    def __init__(self, *, active=False):
        self.active = active

    def tick(self):
        return False

    def snapshot(self):
        return {
            "mode": "realtime_defer" if self.active else "auto",
            "active": self.active,
            "automatic_gc_enabled": not self.active,
        }


class _Harness:
    def __init__(self, *, policy_active=False):
        self._realtime_gc_policy = _Policy(active=policy_active)
        self.original_calls = []

    def handle_command(self, command):
        self.original_calls.append(command)
        return {"ok": True, "forwarded": command.get("command")}

    def _active_moving_units(self):
        return 3

    def _living_units(self):
        return [1, 2, 3, 4]


class _VisionLikeSystem:
    def get_stats(self):
        return {
            "geometry_cache_size": 123,
            "geometry_cache_capacity": 4096,
            "geometry_cache_hits": 10,
            "geometry_cache_misses": 20,
            "geometry_cache_evictions": 3,
        }


def _fake_memory():
    return {
        "rss_bytes": 100 * 1024 * 1024,
        "rss_mb": 100.0,
        "max_rss_bytes": 120 * 1024 * 1024,
        "max_rss_mb": 120.0,
        "rss_source": "test",
    }


def test_memory_snapshot_reports_process_gc_world_workload_and_vision(monkeypatch):
    monkeypatch.setattr(scale_memory_soak, "process_memory_snapshot", _fake_memory)
    world = World()
    entity = world.create_entity()
    world.systems.append(_VisionLikeSystem())
    harness = _Harness()
    install_scale_memory_soak(harness, world)

    result = harness.handle_command({"command": "memory_snapshot"})

    assert result["ok"] is True
    assert result["memory"]["rss_mb"] == 100.0
    assert result["world"]["entities"] == 1
    assert result["workload"]["active_moving_units"] == 3
    assert result["workload"]["living_units"] == 4
    assert result["workload"]["density"] == 0.75
    assert result["vision"] == {
        "geometry_cache_size": 123,
        "geometry_cache_capacity": 4096,
        "geometry_cache_hits": 10,
        "geometry_cache_misses": 20,
        "geometry_cache_evictions": 3,
    }
    assert result["statistics"] == {
        "unit_observation_history_records": 0,
        "visibility_history_units": 0,
        "visibility_history_records": 0,
        "visibility_history_max_per_unit": 0,
        "unit_observation_components": 0,
        "movement_path_entries": 0,
    }
    assert result["gc_policy"]["active"] is False
    assert harness.original_calls == []


def test_memory_snapshot_reports_retained_statistics_history(monkeypatch):
    monkeypatch.setattr(scale_memory_soak, "process_memory_snapshot", _fake_memory)
    world = World()
    tracker = VisibilityTracker(
        visibility_history={
            7: [
                {"timestamp": 1.0, "visible_to": [Faction.WEI]},
                {"timestamp": 2.0, "visible_to": [Faction.WEI, Faction.SHU]},
            ],
            8: [{"timestamp": 3.0, "visible_to": [Faction.SHU]}],
        }
    )
    world.add_singleton_component(tracker)
    entity = world.create_entity()
    observation = UnitObservation(movement_path=[(0, 0), (1, 0), (2, 0)])
    world.add_component(entity, observation)

    harness = _Harness()
    install_scale_memory_soak(harness, world)
    result = harness.handle_command({"command": "memory_snapshot"})

    assert result["statistics"]["visibility_history_units"] == 2
    assert result["statistics"]["visibility_history_records"] == 3
    assert result["statistics"]["visibility_history_max_per_unit"] == 2
    assert result["statistics"]["unit_observation_components"] == 1
    assert result["statistics"]["movement_path_entries"] == 3


def test_memory_snapshot_without_vision_system_reports_empty_vision(monkeypatch):
    monkeypatch.setattr(scale_memory_soak, "process_memory_snapshot", _fake_memory)
    harness = _Harness()
    install_scale_memory_soak(harness, World())

    result = harness.handle_command({"command": "memory_snapshot"})

    assert result["ok"] is True
    assert result["vision"] == {}


def test_safe_gc_collect_rejects_collection_inside_realtime_window(monkeypatch):
    monkeypatch.setattr(scale_memory_soak, "process_memory_snapshot", _fake_memory)
    harness = _Harness(policy_active=True)
    install_scale_memory_soak(harness, World())

    result = harness.handle_command({"command": "safe_gc_collect"})

    assert result["ok"] is False
    assert result["error"] == "realtime_gc_policy_active"


def test_safe_gc_collect_runs_only_at_safe_point(monkeypatch):
    monkeypatch.setattr(scale_memory_soak, "process_memory_snapshot", _fake_memory)
    monkeypatch.setattr(scale_memory_soak.gc, "collect", lambda generation=2: 7)
    harness = _Harness(policy_active=False)
    install_scale_memory_soak(harness, World())

    result = harness.handle_command({"command": "safe_gc_collect"})

    assert result["ok"] is True
    assert result["collected"] == 7
    assert result["rss_delta_mb"] == 0.0
    assert "before" in result and "after" in result


def test_unrelated_commands_still_forward_to_existing_harness():
    harness = _Harness()
    install_scale_memory_soak(harness, World())

    result = harness.handle_command({"command": "status"})

    assert result == {"ok": True, "forwarded": "status"}
    assert harness.original_calls[-1]["command"] == "status"
