from types import SimpleNamespace

import pygame

from rotk_env.components import GameStats, MapData, MiniMap
from rotk_env.systems import scale_minimap_system
from rotk_env.systems.scale_map_render_system import ScaleMapRenderSystem
from rotk_env.systems.scale_minimap_system import MiniMapSystem
from rotk_env.systems.scale_statistics_system import StatisticsSystem


class _World:
    def __init__(self, map_data):
        self.map_data = map_data

    def get_singleton_component(self, component_type):
        if component_type is MapData:
            return self.map_data
        return None


def test_statistics_history_trims_only_small_overflow_in_place():
    system = StatisticsSystem()
    stats = GameStats()
    original = stats.unit_observation_history
    stats.unit_observation_history.extend({"i": i} for i in range(10128))

    trimmed = system._trim_observation_history(stats)

    assert trimmed == 128
    assert stats.unit_observation_history is original
    assert len(stats.unit_observation_history) == 10000
    assert stats.unit_observation_history[0]["i"] == 128


def test_overscan_rebuild_reuses_surface_and_clears_previous_content():
    system = ScaleMapRenderSystem()
    surface = pygame.Surface((100, 80), pygame.SRCALPHA)
    surface.fill((255, 0, 0, 255), pygame.Rect(10, 10, 20, 20))
    system._overscan_surface = surface
    system._overscan_content_rect = pygame.Rect(10, 10, 20, 20)

    acquired, cleared_pixels = system._acquire_overscan_surface((100, 80))

    assert acquired is surface
    assert cleared_pixels == 400
    assert acquired.get_at((15, 15)).a == 0
    assert system._overscan_surface_reuses == 1


def test_minimap_unit_layer_refreshes_at_15hz_not_every_frame(monkeypatch):
    map_data = MapData(width=2, height=1)
    map_data.tiles[(0, 0)] = 1
    map_data.tiles[(1, 0)] = 2

    system = MiniMapSystem()
    system.world = _World(map_data)
    monkeypatch.setattr(system, "_get_screen_rect", lambda _m: (0, 0, 100, 60))
    monkeypatch.setattr(system, "_calculate_world_bounds", lambda _m: None)
    monkeypatch.setattr(scale_minimap_system.RMS, "draw", lambda *args, **kwargs: None)

    refreshes = []
    monkeypatch.setattr(
        system,
        "_render_units",
        lambda *args, **kwargs: refreshes.append(1),
    )

    clock = iter([0.0, 0.01, 0.08])
    monkeypatch.setattr(scale_minimap_system.time, "perf_counter", lambda: next(clock))

    minimap = MiniMap(show_terrain=False, show_camera_viewport=False)
    system._render_minimap(minimap)
    system._render_minimap(minimap)
    system._render_minimap(minimap)

    assert len(refreshes) == 2
    assert system._unit_refresh_count == 2


def test_minimap_caches_layout_and_gates_refresh_on_spatial_revision(monkeypatch):
    map_data = MapData(width=2, height=1)
    map_data.tiles[(0, 0)] = 1
    map_data.tiles[(1, 0)] = 2

    world = _World(map_data)
    spatial_index = SimpleNamespace(revision=1)
    world._unit_spatial_index = spatial_index
    system = MiniMapSystem()
    system.world = world
    monkeypatch.setattr(system, "_get_screen_rect", lambda _m: (0, 0, 100, 60))
    monkeypatch.setattr(system, "_calculate_world_bounds", lambda _m: None)
    monkeypatch.setattr(scale_minimap_system.RMS, "draw", lambda *args, **kwargs: None)

    refreshes = []
    monkeypatch.setattr(
        system,
        "_render_units",
        lambda *args, **kwargs: refreshes.append(spatial_index.revision),
    )
    clock = iter([0.0, 0.08, 0.16])
    monkeypatch.setattr(scale_minimap_system.time, "perf_counter", lambda: next(clock))

    minimap = MiniMap(show_terrain=False, show_camera_viewport=False)
    system._render_minimap(minimap)
    system._render_minimap(minimap)  # interval elapsed, but revision is unchanged
    spatial_index.revision = 2
    system._render_minimap(minimap)

    assert refreshes == [1, 2]
    assert system._layout_rebuild_count == 1
