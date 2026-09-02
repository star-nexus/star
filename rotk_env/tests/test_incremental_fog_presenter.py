from collections import defaultdict

import pygame

from framework.ecs.world import World
from framework.engine import RMS

from rotk_env.components import FogOfWar, GameState, UIState
from rotk_env.prefabs.config import Faction, GameConfig
from rotk_env.systems.fog_surface_presenter import IncrementalFogSurfacePresenter
from rotk_env.utils.fog_visibility_journal import (
    FogVisibilityChangeJournal,
    publish_fog_visibility_delta,
)
from rotk_env.utils.hex_utils import HexConverter


class _Renderer:
    def __init__(self, world):
        self.world = world
        self.hex_converter = HexConverter(
            GameConfig.HEX_SIZE, GameConfig.HEX_ORIENTATION
        )


def _world():
    world = World()
    world.add_singleton_component(GameState(current_player=Faction.WEI))
    world.add_singleton_component(UIState(view_faction=Faction.WEI))
    world.add_singleton_component(
        FogOfWar(
            faction_vision={Faction.WEI: set()},
            explored_tiles={Faction.WEI: set()},
            enabled=True,
        )
    )
    return world


def _center(renderer, tile, camera_offset, zoom):
    x, y = renderer.hex_converter.hex_to_pixel(*tile)
    return (
        int(round(x * zoom + camera_offset[0])),
        int(round(y * zoom + camera_offset[1])),
    )


def test_incremental_patch_matches_authoritative_fog_state():
    world = _world()
    renderer = _Renderer(world)
    presenter = IncrementalFogSurfacePresenter(renderer)
    tile = (0, 0)
    visible_tiles = {tile}
    camera = [120.0, 120.0]
    zoom = 1.0
    pixel = _center(renderer, tile, camera, zoom)

    surface = presenter.update_surface(visible_tiles, camera, zoom)
    assert surface is not None
    assert surface.get_at(pixel)[3] > 0
    assert presenter.full_builds == 1

    fog = world.get_singleton_component(FogOfWar)
    fog.faction_vision[Faction.WEI].add(tile)
    fog.explored_tiles[Faction.WEI].add(tile)
    publish_fog_visibility_delta(world, {Faction.WEI: {tile}})

    same_surface = presenter.update_surface(visible_tiles, camera, zoom)
    assert same_surface is surface
    assert same_surface.get_at(pixel)[3] == 0
    assert presenter.full_builds == 1
    assert presenter.patch_updates == 1

    fog.faction_vision[Faction.WEI].remove(tile)
    publish_fog_visibility_delta(world, {Faction.WEI: {tile}})
    presenter.update_surface(visible_tiles, camera, zoom)
    assert presenter.surface.get_at(pixel)[3] == GameConfig.FOG_EXPLORED_COLOR[3]
    assert presenter.patch_updates == 2


def test_camera_change_forces_full_rebuild_not_incremental_patch():
    world = _world()
    renderer = _Renderer(world)
    presenter = IncrementalFogSurfacePresenter(renderer)
    tile = (0, 0)

    presenter.update_surface({tile}, [120.0, 120.0], 1.0)
    publish_fog_visibility_delta(world, {Faction.WEI: {tile}})
    presenter.update_surface({tile}, [121.0, 120.0], 1.0)

    assert presenter.full_builds == 2
    assert presenter.patch_updates == 0


def test_history_gap_falls_back_to_authoritative_full_rebuild():
    world = _world()
    setattr(
        world,
        "_fog_visibility_change_journal",
        FogVisibilityChangeJournal(max_events=8),
    )
    renderer = _Renderer(world)
    presenter = IncrementalFogSurfacePresenter(renderer)
    visible_tiles = {(0, 0)}

    presenter.update_surface(visible_tiles, [120.0, 120.0], 1.0)
    for index in range(12):
        publish_fog_visibility_delta(world, {Faction.WEI: {(index, 0)}})

    presenter.update_surface(visible_tiles, [120.0, 120.0], 1.0)
    assert presenter.full_builds == 2
    assert presenter.patch_updates == 0


def test_presentation_bounds_include_currently_transparent_visible_tiles(monkeypatch):
    monkeypatch.setattr(GameConfig, "WINDOW_WIDTH", 320)
    monkeypatch.setattr(GameConfig, "WINDOW_HEIGHT", 240)

    world = _world()
    renderer = _Renderer(world)
    presenter = IncrementalFogSurfacePresenter(renderer)
    tile = (0, 0)
    camera = [160.0, 120.0]
    pixel = _center(renderer, tile, camera, 1.0)
    fog = world.get_singleton_component(FogOfWar)

    # Start with the tile fully visible, so its fog pixels are transparent.
    fog.faction_vision[Faction.WEI].add(tile)
    surface = presenter.update_surface({tile}, camera, 1.0)
    rect = presenter.presentation_rect
    assert surface is not None
    assert rect is not None
    assert rect.collidepoint(pixel)
    assert surface.get_at(pixel)[3] == 0

    # A later semantic patch can make the same tile fogged without changing view
    # geometry. The precomputed map-content bound must still cover it.
    fog.faction_vision[Faction.WEI].remove(tile)
    publish_fog_visibility_delta(world, {Faction.WEI: {tile}})
    presenter.update_surface({tile}, camera, 1.0)

    assert presenter.presentation_rect == rect
    assert presenter.surface.get_at(pixel)[3] > 0
    assert presenter.presentation_rect.collidepoint(pixel)


def test_bounded_composite_is_pixel_identical_to_full_surface_blit(monkeypatch):
    monkeypatch.setattr(GameConfig, "WINDOW_WIDTH", 320)
    monkeypatch.setattr(GameConfig, "WINDOW_HEIGHT", 240)

    world = _world()
    renderer = _Renderer(world)
    presenter = IncrementalFogSurfacePresenter(renderer)
    visible_tiles = {(0, 0), (0, 1), (1, 0)}
    camera = [160.0, 120.0]

    surface = presenter.update_surface(visible_tiles, camera, 1.0)
    rect = presenter.presentation_rect
    assert surface is not None
    assert rect is not None
    assert rect.width * rect.height < surface.get_width() * surface.get_height()

    expected = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    expected.fill((17, 31, 47, 255))
    actual = expected.copy()

    expected.blit(surface, (0, 0))
    actual.blit(surface, rect.topleft, area=rect)

    assert pygame.image.tostring(actual, "RGBA") == pygame.image.tostring(
        expected, "RGBA"
    )


def test_render_queues_only_content_bounded_fog_blit(monkeypatch):
    monkeypatch.setattr(GameConfig, "WINDOW_WIDTH", 320)
    monkeypatch.setattr(GameConfig, "WINDOW_HEIGHT", 240)
    monkeypatch.setattr(RMS, "_render_queue", defaultdict(list))
    monkeypatch.setattr(RMS, "current_layer", 0)

    world = _world()
    renderer = _Renderer(world)
    presenter = IncrementalFogSurfacePresenter(renderer)
    visible_tiles = {(0, 0), (0, 1), (1, 0)}
    camera = [160.0, 120.0]

    presenter.render(visible_tiles, camera, 1.0)

    commands = RMS._render_queue[0]
    assert len(commands) == 1
    command = commands[0]
    rect = presenter.presentation_rect
    assert rect is not None
    assert command.surface is presenter.surface
    assert command.area == rect
    assert command.dest == rect.topleft
    assert command.batchable is False
