"""Regression coverage for the Phase-5 C1 window Vision cache-hit fast path."""

from framework.ecs.world import World

from rotk_env.systems.window_vision_system import VisionSystem


def _system():
    world = World()
    system = VisionSystem()
    system.initialize(world)
    return system


def test_window_geometry_cache_hit_skips_terrain_bonus_lookup(monkeypatch):
    system = _system()
    calls = 0

    def counted_bonus(_center):
        nonlocal calls
        calls += 1
        return 2

    monkeypatch.setattr(system, "_get_vision_terrain_bonus", counted_bonus)

    first = system._visibility_for((0, 0), 1)
    second = system._visibility_for((0, 0), 1)

    assert second is first
    assert calls == 1
    assert ((0, 0), 1, system._terrain_revision) in system._geometry_cache

    stats = system.get_stats()
    assert stats["geometry_cache_misses"] == 1
    assert stats["geometry_cache_hits"] == 1


def test_window_geometry_cache_rechecks_terrain_after_invalidation(monkeypatch):
    system = _system()
    calls = 0
    bonus = 0

    def dynamic_bonus(_center):
        nonlocal calls
        calls += 1
        return bonus

    monkeypatch.setattr(system, "_get_vision_terrain_bonus", dynamic_bonus)

    original = system._visibility_for((0, 0), 1)
    assert calls == 1

    # Within one terrain revision the cached geometry is authoritative, so a
    # hit must not consult terrain even if this test changes the mocked source.
    bonus = 2
    assert system._visibility_for((0, 0), 1) is original
    assert calls == 1

    old_revision = system._terrain_revision
    system.invalidate_all()
    assert system._terrain_revision == old_revision + 1
    assert not system._geometry_cache

    recomputed = system._visibility_for((0, 0), 1)
    assert calls == 2
    assert recomputed != original
    assert len(recomputed) > len(original)
    assert ((0, 0), 1, system._terrain_revision) in system._geometry_cache

    stats = system.get_stats()
    assert stats["geometry_cache_misses"] == 2
    assert stats["geometry_cache_hits"] == 1
