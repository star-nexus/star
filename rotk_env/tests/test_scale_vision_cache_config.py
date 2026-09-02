import pytest

import rotk_env.systems.scale_vision_system as scale_vision_system


def test_scale_vision_cache_capacity_defaults_to_bounded_baseline(monkeypatch):
    monkeypatch.delenv(
        scale_vision_system._SCALE_VISION_CACHE_ENV,
        raising=False,
    )

    system = scale_vision_system.VisionSystem()

    assert system.get_stats()["geometry_cache_capacity"] == 4096


def test_scale_vision_cache_capacity_can_be_selected_per_fresh_process(monkeypatch):
    monkeypatch.setenv(
        scale_vision_system._SCALE_VISION_CACHE_ENV,
        "16384",
    )

    system = scale_vision_system.VisionSystem()

    assert system.get_stats()["geometry_cache_capacity"] == 16384


@pytest.mark.parametrize("value", ["0", "-1", "abc", "12.5"])
def test_scale_vision_cache_capacity_rejects_invalid_values(monkeypatch, value):
    monkeypatch.setenv(scale_vision_system._SCALE_VISION_CACHE_ENV, value)

    with pytest.raises(ValueError, match="STAR_SCALE_VISION_GEOMETRY_CACHE_MAX_ENTRIES"):
        scale_vision_system.VisionSystem()
