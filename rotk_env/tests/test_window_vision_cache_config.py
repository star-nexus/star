"""Regression contract for the accepted large-window Vision cache default."""

from rotk_env.systems.window_vision_system import VisionSystem


def test_window_vision_cache_keeps_validated_headroom_default():
    system = VisionSystem()

    # STAR Lab 2026-09-vision-cache established that 4096 thrashes the measured
    # 5K working set, 8192 is the minimum sufficient capacity, and 16384 is the
    # accepted bounded window/scale default with headroom. Keep that operational
    # decision protected independently from the generic base VisionSystem default.
    assert system.get_stats()["geometry_cache_capacity"] == 16384
