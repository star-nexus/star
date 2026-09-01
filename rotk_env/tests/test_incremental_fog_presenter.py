from types import SimpleNamespace

from framework.ecs.world import World

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
