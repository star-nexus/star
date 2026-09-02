from types import SimpleNamespace

import pytest

import rotk_env.testing.scale_vision_cache_ablation as ablation
from rotk_env.testing.scale_vision_cache_ablation import (
    install_scale_vision_cache_ablation,
)


class _VisionLikeSystem:
    def __init__(self, *, capacity=4096):
        self.stats = {
            "geometry_cache_size": capacity,
            "geometry_cache_capacity": capacity,
            "geometry_cache_hits": 100,
            "geometry_cache_misses": 20,
            "geometry_cache_evictions": 5,
        }

    def get_stats(self):
        return dict(self.stats)


class _World:
    def __init__(self, vision):
        self.systems = [vision]


class _Harness:
    def __init__(self):
        self.calls = []

    def handle_command(self, command):
        self.calls.append(command.get("command"))
        if command.get("command") == "start_sustained_batch":
            return {"ok": True, "duration_seconds": 20.0}
        if command.get("command") == "profile_snapshot":
            return {"ok": True, "guards": {}, "context": {}}
        return {"ok": True}


def test_profile_snapshot_reports_measurement_epoch_cache_delta_and_rss(monkeypatch):
    vision = _VisionLikeSystem(capacity=4096)
    harness = _Harness()
    memory_samples = iter(
        [
            {"rss_mb": 300.0, "rss_bytes": 300 * 1024 * 1024},
            {"rss_mb": 312.5, "rss_bytes": int(312.5 * 1024 * 1024)},
        ]
    )
    monkeypatch.setattr(ablation, "process_memory_snapshot", lambda: next(memory_samples))
    install_scale_vision_cache_ablation(harness, _World(vision))

    start = harness.handle_command({"command": "start_sustained_batch"})
    assert start["vision_cache_start"]["geometry_cache_capacity"] == 4096

    vision.stats.update(
        geometry_cache_hits=190,
        geometry_cache_misses=30,
        geometry_cache_evictions=13,
    )
    snapshot = harness.handle_command({"command": "profile_snapshot"})

    delta = snapshot["vision_cache"]["delta"]
    assert delta["geometry_cache_hits"] == 90
    assert delta["geometry_cache_misses"] == 10
    assert delta["geometry_cache_evictions"] == 8
    assert delta["geometry_cache_lookups"] == 100
    assert delta["geometry_hit_rate"] == pytest.approx(0.9)
    assert delta["geometry_cache_capacity"] == 4096
    assert snapshot["memory"]["rss_growth_mb"] == 12.5
    assert snapshot["guards"]["vision_cache_capacity_unchanged"] is True
    assert snapshot["context"]["scale_vision_geometry_cache_capacity"] == 4096


def test_profile_snapshot_rejects_capacity_change_inside_one_measurement(monkeypatch):
    vision = _VisionLikeSystem(capacity=4096)
    harness = _Harness()
    monkeypatch.setattr(
        ablation,
        "process_memory_snapshot",
        lambda: {"rss_mb": 300.0, "rss_bytes": 300 * 1024 * 1024},
    )
    install_scale_vision_cache_ablation(harness, _World(vision))

    harness.handle_command({"command": "start_sustained_batch"})
    vision.stats["geometry_cache_capacity"] = 8192
    snapshot = harness.handle_command({"command": "profile_snapshot"})

    assert snapshot["ok"] is False
    assert snapshot["error"] == "vision_cache_capacity_changed"
    assert snapshot["guards"]["vision_cache_capacity_unchanged"] is False


def test_stop_clears_measurement_baseline(monkeypatch):
    vision = _VisionLikeSystem(capacity=4096)
    harness = _Harness()
    monkeypatch.setattr(
        ablation,
        "process_memory_snapshot",
        lambda: {"rss_mb": 300.0, "rss_bytes": 300 * 1024 * 1024},
    )
    install_scale_vision_cache_ablation(harness, _World(vision))

    harness.handle_command({"command": "start_sustained_batch"})
    assert harness._scale_vision_cache_measurement_start is not None

    harness.handle_command({"command": "stop_sustained"})
    assert harness._scale_vision_cache_measurement_start is None
