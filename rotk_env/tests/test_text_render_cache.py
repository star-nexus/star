"""Visual/ownership/invalidation contracts for bounded text presentation caches."""
from pathlib import Path

import pygame
import pytest

from framework import World
from framework.engine import RMS
from rotk_env.components import Camera, DamageNumber, UIState
from rotk_env.prefabs.config import GameConfig, HexOrientation
from rotk_env.systems.animation_system import AnimationSystem
from rotk_env.systems.map_render_system import MapRenderSystem


class CountingFont:
    def __init__(self, font):
        self.font = font
        self.renders = 0
        self.sizes = 0

    def render(self, *args):
        self.renders += 1
        return self.font.render(*args)

    def size(self, text):
        self.sizes += 1
        return self.font.size(text)


@pytest.fixture
def setup(monkeypatch):
    pygame.font.init()
    monkeypatch.setattr(GameConfig, 'WINDOW_WIDTH', 240)
    monkeypatch.setattr(GameConfig, 'WINDOW_HEIGHT', 180)
    world = World()
    world.add_singleton_component(UIState(show_coordinates=True))
    world.add_singleton_component(Camera(offset_x=0, offset_y=0, zoom=1.))
    draws = []
    monkeypatch.setattr(RMS, 'draw', lambda surface, dest, **kwargs: draws.append((surface, dest, kwargs)))
    return world, draws


def map_renderer(world):
    renderer = MapRenderSystem()
    renderer.world = world
    return renderer


def damage_renderer(world):
    renderer = AnimationSystem()
    renderer.world = world
    renderer.damage_font = CountingFont(pygame.font.Font(None, 24))
    renderer.font_dict = {28: CountingFont(pygame.font.Font(None, 28))}
    renderer.font_file_path = Path('unused-cached-font')
    return renderer


def add_damage(world, **kwargs):
    entity = world.create_entity()
    component = DamageNumber(**kwargs)
    world.add_component(entity, component)
    return entity, component


def test_coordinates_reuse_whole_overlay_without_tile_work(setup, monkeypatch):
    world, draws = setup
    renderer = map_renderer(world)
    tiles = {(0, 0), (1, 0)}
    font_factory = pygame.font.Font
    fonts = []
    def make_font(*args):
        font = CountingFont(font_factory(*args))
        fonts.append(font)
        return font
    monkeypatch.setattr(pygame.font, 'Font', make_font)
    renderer._render_coordinates_optimized(tiles, [100, 100], 1.)
    assert len(fonts) == 1 and fonts[0].renders == 4
    first = draws[-1][0]
    def forbidden(*args):
        pytest.fail('stable view must not iterate/project/rasterize tiles')
    monkeypatch.setattr(renderer.hex_converter, 'hex_to_pixel', forbidden)
    renderer._render_coordinates_optimized(tiles, [100, 100], 1.)
    assert draws[-1][0] is first and len(draws) == 2
    assert fonts[0].renders == 4


def test_coordinates_view_changes_reuse_labels_and_bound_retention(setup, monkeypatch):
    world, draws = setup
    renderer = map_renderer(world)
    tiles = {(0, 0), (1, 0)}
    renderer._render_coordinates_optimized(tiles, [100, 100], 1.)
    labels = renderer._coordinate_labels.copy()
    first = draws[-1][0]
    renderer._render_coordinates_optimized(tiles, [101.25, 99.5], 1.01)
    assert draws[-1][0] is not first
    assert all(renderer._coordinate_labels[k] is v for k, v in labels.items())
    renderer._render_coordinates_optimized(tiles, [101.25, 99.5], 2.)
    assert all(renderer._coordinate_labels[k] is not v for k, v in labels.items())
    monkeypatch.setattr(GameConfig, 'WINDOW_WIDTH', 300)
    renderer._render_coordinates_optimized(tiles, [101.25, 99.5], 2.)
    assert draws[-1][0].get_size() == (300, 180)
    renderer._render_coordinates_optimized({(2, 0)}, [101.25, 99.5], 2.)
    assert set(renderer._coordinate_labels) == {(2, 0)}
    before = draws[-1][0]
    renderer.set_hex_orientation(HexOrientation.POINTY_TOP if renderer.hex_converter.orientation == HexOrientation.FLAT_TOP else HexOrientation.FLAT_TOP)
    renderer._render_coordinates_optimized({(2, 0)}, [101.25, 99.5], 2.)
    assert draws[-1][0] is not before
    monkeypatch.setattr(renderer, '_load_terrain_textures', lambda: None)
    renderer.initialize(World())
    assert not renderer._coordinate_labels and renderer._coordinate_overlay is None


def test_disabled_or_tiny_coordinates_do_no_raster_work(setup):
    world, draws = setup
    renderer = map_renderer(world)
    renderer._render_coordinates_optimized({(0, 0)}, [100, 100], .15)
    world.get_singleton_component(UIState).show_coordinates = False
    renderer._render_coordinates_optimized({(0, 0)}, [100, 100], 1.)
    assert not draws and renderer._coordinate_font is None


@pytest.mark.parametrize('zoom,offset', [(1., (100.25, 100.5)), (.5, (0., 4.)), (2., (100., 100.))])
def test_coordinate_pixels_match_original_outline(setup, zoom, offset):
    world, draws = setup
    renderer = map_renderer(world)
    tiles = {(0, 0), (1, 0), (-1, 0)}
    renderer._render_coordinates_optimized(tiles, offset, zoom)
    actual = pygame.Surface((240, 180)); actual.fill((83, 121, 147))
    for surface, dest, kwargs in draws:
        actual.blit(surface, dest, **kwargs)
    expected = pygame.Surface((240, 180)); expected.fill((83, 121, 147))
    font = pygame.font.Font(None, max(10, int(12*zoom)))
    for q, r in tiles:
        x, y = renderer.hex_converter.hex_to_pixel(q, r)
        text = f'({q},{r})'
        foreground = font.render(text, True, (255, 255, 255))
        rect = foreground.get_rect(center=(int(x*zoom+offset[0]), int(y*zoom+offset[1])))
        for dx, dy in [(-1,-1),(-1,1),(1,-1),(1,1)]:
            expected.blit(font.render(text, True, (0,0,0)), rect.move(dx,dy))
        expected.blit(foreground, rect)
    # Intermediate alpha surfaces may differ by integer rounding only.
    a, b = pygame.image.tobytes(actual, 'RGB'), pygame.image.tobytes(expected, 'RGB')
    assert max(abs(x-y) for x,y in zip(a,b)) <= 4


def test_damage_reuses_raster_and_keeps_independent_alpha(setup):
    world, draws = setup
    renderer = damage_renderer(world)
    _, first = add_damage(world, text='CRIT!', position=(20,20), font_size=28, elapsed_time=.5)
    _, second = add_damage(world, text='CRIT!', position=(20,50), font_size=28, elapsed_time=1.)
    renderer.render_damage_numbers()
    surfaces = [s for s,_,_ in draws]
    assert surfaces[0] is not surfaces[1]
    assert [s.get_alpha() for s in surfaces] == [191, 127]
    assert renderer.font_dict[28].renders == 2
    draws.clear()
    first.elapsed_time = 0.
    first.position = (40, 30)
    renderer.render_damage_numbers()
    assert draws[0][:2] == (surfaces[0], (40,30))
    assert surfaces[0].get_alpha() == 255 and surfaces[1].get_alpha() == 127
    assert renderer.font_dict[28].renders == 2


def test_damage_changes_replacement_and_deletion_invalidate_cache(setup):
    world, draws = setup
    renderer = damage_renderer(world)
    entity, component = add_damage(world, text='12', position=(20,20))
    renderer.render_damage_numbers()
    component.text = '24'; component.color = (0,255,0)
    renderer.render_damage_numbers()
    assert renderer.damage_font.renders == 2
    component.font_size = 28
    renderer.render_damage_numbers()
    assert renderer.font_dict[28].renders == 1
    world.add_component(entity, DamageNumber(text='24', position=(20,20), font_size=28))
    renderer.render_damage_numbers()
    assert renderer.font_dict[28].renders == 2
    world.destroy_entity(entity)
    renderer.render_damage_numbers()
    assert renderer._damage_text_cache == {}


def test_damage_culls_whole_rect_and_reuses_size_offscreen(setup):
    world, draws = setup
    renderer = damage_renderer(world)
    _, right = add_damage(world, text='12', position=(241,20))
    _, left = add_damage(world, text='12', position=(-1000,20))
    renderer.render_damage_numbers()
    renderer.render_damage_numbers()
    assert not draws and renderer.damage_font.renders == 0
    assert renderer.damage_font.sizes == 1
    right.position = (-1,20)  # partially visible: must render
    left.position = (20,-1)
    renderer.render_damage_numbers()
    assert len(draws) == 2 and renderer.damage_font.renders == 2
    right.elapsed_time = right.lifetime
    left.elapsed_time = left.lifetime
    renderer.render_damage_numbers()
    assert not renderer._damage_text_cache


@pytest.mark.parametrize('text,size,position,elapsed', [
    ('123', 24, (20.75,30.5), 0.), ('CRIT!', 28, (-1.5,20.), .5),
    ('CRIT!', 28, (20.,-1.5), 1.), ('123', 24, (239.,179.), 1.5)])
def test_damage_pixels_match_original_at_edges_and_during_fade(setup, text, size, position, elapsed):
    world, draws = setup
    renderer = damage_renderer(world)
    _, component = add_damage(world, text=text, font_size=size, position=position,
                              elapsed_time=elapsed, color=(255,220,0))
    renderer.render_damage_numbers()
    actual = pygame.Surface((240,180)); actual.fill((83,121,147))
    for surface, dest, kwargs in draws:
        actual.blit(surface, dest, **kwargs)
    expected = pygame.Surface((240,180)); expected.fill((83,121,147))
    font = renderer.font_dict[size] if size != 24 else renderer.damage_font
    surface = font.font.render(text, True, component.color)
    alpha = int(255*(1-elapsed/component.lifetime))
    if alpha < 255:
        surface.set_alpha(alpha)
    expected.blit(surface, position)
    assert pygame.image.tobytes(actual, 'RGB') == pygame.image.tobytes(expected, 'RGB')
