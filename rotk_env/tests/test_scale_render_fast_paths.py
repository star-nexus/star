"""Regression tests for the scale-up rendering/query fast paths."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from rotk_env.components import Terrain
from rotk_env.prefabs.world_builder import build_skirmish_world
from rotk_env.systems.fast_render_systems import (
    FastEffectRenderSystem,
    FastMapRenderSystem,
)
from rotk_env.utils.map_query import impassable_terrain, invalidate_static_map_cache


def setup_module():
    pygame.init()
    if pygame.display.get_surface() is None:
        pygame.display.set_mode((64, 64))


def teardown_module():
    pygame.quit()


def test_terrain_texture_is_scaled_once_per_zoom_size(monkeypatch):
    renderer = FastMapRenderSystem()
    source = pygame.Surface((100, 100), pygame.SRCALPHA)
    real_scale = pygame.transform.scale
    calls = []

    def counted_scale(surface, size):
        calls.append(size)
        return real_scale(surface, size)

    monkeypatch.setattr(pygame.transform, "scale", counted_scale)
    first = renderer._scaled_terrain_texture(source, 0.50)
    second = renderer._scaled_terrain_texture(source, 0.50)

    assert first is second
    assert calls == [(50, 50)]

    renderer._scaled_terrain_texture(source, 0.60)
    assert calls[-1] == (60, 60)
    assert len(calls) == 2


def test_movement_overlay_surface_is_reused():
    renderer = FastEffectRenderSystem()
    first, radius1 = renderer._movement_overlay(0.5)
    second, radius2 = renderer._movement_overlay(0.5)
    assert radius1 == radius2
    assert first is second


def test_static_impassable_terrain_scan_is_cached():
    world = build_skirmish_world(display="none", scenario="chibi")
    invalidate_static_map_cache(world)

    original_get_component = world.get_component
    terrain_reads = 0

    def counted_get_component(entity, component_type):
        nonlocal terrain_reads
        if component_type is Terrain:
            terrain_reads += 1
        return original_get_component(entity, component_type)

    world.get_component = counted_get_component
    first = impassable_terrain(world)
    reads_after_first = terrain_reads
    second = impassable_terrain(world)

    assert first == second
    assert reads_after_first > 0
    assert terrain_reads == reads_after_first
