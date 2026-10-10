from types import SimpleNamespace
import os
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
import pygame
import pytest
from framework import World
from framework.engine import RMS
from rotk_env import components as c
from rotk_env.ui.context import UiContext, controller_available
from rotk_env.components.start_menu import start_panel_layout, scenario_option_rects, StartMenuConfig
from rotk_env.prefabs.controls import binding_for_key
from rotk_env.prefabs.config import Faction, UnitType
from rotk_env.tests.test_window_input_picking import _World, _system
from rotk_env.systems.minimap_system import MiniMapSystem


@pytest.fixture
def context():
    pygame.init(); pygame.display.set_mode((1200, 800))
    ctx = UiContext()
    yield ctx
    ctx.close(); RMS.clear()


@pytest.mark.parametrize('size', [(1200,800),(1440,900),(1920,1080),(2480,1263)])
def test_layout_bounds_and_menu_draw_hit_geometry(context, size):
    pygame.display.set_mode(size); context.sync()
    l = context.layout
    assert not l.viewport.colliderect(l.sidebar)
    assert l.sidebar.contains(l.content) and l.sidebar.contains(l.footer)
    assert l.content.bottom < l.footer.top
    g = start_panel_layout(60, *size)
    cfg = StartMenuConfig(scenario_catalog=[{'scenario':str(i)} for i in range(60)], scenario_scroll=3)
    visible = scenario_option_rects(cfg, g)
    assert len(visible) == 2*g['scenario_visible_rows']
    for _, rect in visible:
        assert g['scenario_clip'].contains(rect)
        assert not rect.colliderect(g['start_rect'])
    assert g['summary_rect'].bottom < g['start_rect'].top
    for i, rect in enumerate(g['mode_rects']+g['player_rects']+g['controller_rects']):
        assert rect.bottom < g['scenario_clip'].top
        for other in (g['mode_rects']+g['player_rects']+g['controller_rects'])[i+1:]:
            assert not rect.colliderect(other)


def test_resize_preserves_world_center_and_minimap_zoom(context):
    w = World(); camera = c.Camera(offset_x=150, offset_y=90, zoom=2.25)
    w.add_singleton_component(camera); context.attach(w)
    before = ((context.layout.viewport.centerx-camera.offset_x)/camera.zoom,
              (context.layout.viewport.centery-camera.offset_y)/camera.zoom)
    pygame.display.set_mode((1920,1080)); context.sync(w)
    assert ((context.layout.viewport.centerx-camera.offset_x)/camera.zoom,
            (context.layout.viewport.centery-camera.offset_y)/camera.zoom) == before
    mm = MiniMapSystem(); mm.world = w
    mm._move_camera_to_position((3,2))
    x, y = mm.hex_converter.hex_to_pixel(3,2)
    assert x*camera.zoom+camera.offset_x == context.layout.viewport.centerx
    assert y*camera.zoom+camera.offset_y == pytest.approx(context.layout.viewport.centery)


def test_tactical_alpha_and_bounded_owned_cache(context):
    points = [(1,1),(19,1),(19,19),(1,19)]
    surface = context.tactical_surface('move',(21,21),points)
    assert surface.get_flags() & pygame.SRCALPHA
    assert surface.get_at((10,10)).a == 38
    target = pygame.Surface((21,21)); target.fill((100,100,100)); target.blit(surface,(0,0))
    assert target.get_at((10,10))[:3] != surface.get_at((10,10))[:3]
    for n in range(150): context.tactical_surface('enemy',(n+10,n+10))
    assert context.cache_stats()['tactical_entries'] <= 128
    assert context.cache_stats()['tactical_bytes'] <= 32*1024*1024
    context.close(); assert context.cache_stats()['tactical_bytes'] == 0


def test_shortcuts_modifier_conflicts_and_rust_capabilities():
    assert binding_for_key(pygame.K_1).action == 'select_infantry'
    assert binding_for_key(pygame.K_1,pygame.KMOD_SHIFT).action == 'toggle_fog'
    assert binding_for_key(pygame.K_a).action == 'unit_attack'
    assert binding_for_key(pygame.K_w).action == 'unit_wait'
    assert binding_for_key(pygame.K_1,pygame.KMOD_CTRL) is None
    assert controller_available('rust','none')
    assert not controller_available('rust','hub')
    assert not controller_available('rust','mock_ai')


def test_panel_background_and_modal_block_map_clicks(context):
    w = _World(); context.attach(w); system = _system(w)
    system._get_visible_unit_at_screen_position = lambda pos: pytest.fail('HUD click reached map')
    system._handle_mouse_click(SimpleNamespace(button=1,pos=context.layout.sidebar.center))
    system._handle_mouse_click(SimpleNamespace(button=1,pos=(20,context.layout.viewport.y+15)))
    system._handle_mouse_click(SimpleNamespace(button=1,pos=(20,context.layout.viewport.bottom-15)))
    w.ui_state.show_help = True
    system._handle_mouse_click(SimpleNamespace(button=1,pos=context.layout.viewport.center))


def test_slots_are_distinct_stable_alive_and_escape_has_two_steps(context):
    w = _World(); system = _system(w)
    for i in (8,3,9):
        w.units[i] = SimpleNamespace(faction=Faction.WEI,unit_type=UnitType.ARCHER)
        w.counts[i] = SimpleNamespace(current_count=100)
        w.positions[i] = c.HexPosition(0,0)
    system._action_select_archer_1(); assert w.ui_state.selected_unit == 3
    system._action_select_archer_2(); assert w.ui_state.selected_unit == 8
    system._action_select_archer_3(); assert w.ui_state.selected_unit == 9
    w.counts[8].current_count = 0
    system._action_select_archer_2(); assert w.ui_state.selected_unit == 9
    system._action_select_archer_3(); assert w.ui_state.selected_unit == 9
    system._targeting_action = 'attack'; system._targeting_unit = 9
    system._action_clear_selection(); assert w.ui_state.selected_unit == 9 and system._targeting_action is None
    system._action_clear_selection(); assert w.ui_state.selected_unit is None


def test_pointer_zoom_preserves_pick_and_sidebar_wheel_leaves_camera(context):
    w = _World(); context.attach(w); system = _system(w)
    system.min_zoom, system.max_zoom = .15, 3
    point = system._hex_to_screen((3,4))
    assert system._screen_to_hex(point) == (3,4)
    system._handle_mouse_wheel(SimpleNamespace(pos=point,y=1))
    assert system._screen_to_hex(point) == (3,4)
    zoom, offset = w.camera.zoom, w.camera.get_offset()
    system._handle_mouse_wheel(SimpleNamespace(pos=context.layout.sidebar.center,y=-3))
    assert w.camera.zoom == zoom and w.camera.get_offset() == offset
    assert context.scroll > 0


def test_minimap_inverse_matches_terrain_world_projection(context):
    w = World(); w.add_singleton_component(c.Camera(zoom=.7))
    w.add_singleton_component(c.MapData(width=7,height=7,tiles={(q,r):1 for q in range(-3,4) for r in range(-3,4)}))
    context.attach(w); system = MiniMapSystem(); system.world=w
    system._calculate_world_bounds(w.get_singleton_component(c.MapData)); b=system._world_bounds
    for pos in ((-2,-2),(0,0),(3,2)):
        x,y = system.hex_converter.hex_to_pixel(*pos)
        rel=((x-b['min_x'])/(b['max_x']-b['min_x']), (y-b['min_y'])/(b['max_y']-b['min_y']))
        assert system._minimap_to_world_pos(rel) == pos
