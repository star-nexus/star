"""Cocoa button feedback evidence, using the production event pump and clock."""
import base64
import hashlib
import io
import json
import os
import sys
import time
from pathlib import Path

source = Path(sys.argv[1])
out = Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
os.chdir(source)
sys.path.insert(0, str(source))
os.environ['HEADLESS'] = '0'
os.environ['SDL_VIDEODRIVER'] = 'cocoa'
import pygame
from framework.engine.game_engine import GameEngine
from framework.engine import RMS
from framework.engine.renders import FRAME_CLEAR_COLOR
from rotk_env import components as c
from rotk_env.prefabs.config import GameConfig, Faction, PlayerType
from rotk_env.prefabs.world_builder import build_skirmish_world
from rotk_env.runtime.bootstrap import export_initial_state
from rotk_env.runtime.session import NativeSession
from rotk_env.ui.context import VISUAL_VERSION

engine = GameEngine(width=1200, height=900, title='STARBench button feedback validation')
GameConfig.sync_from_display()
clock = pygame.time.Clock()
records = []
for backend in ('python', 'rust'):
    options = dict(display='window', scenario='river_split', mode='turn_based',
                   seed=42, hub_url=None,
                   players={Faction.WEI: PlayerType.HUMAN, Faction.SHU: PlayerType.AI})
    session = NativeSession(authority_scheduling=True, **options) if backend == 'rust' else None
    world = session.world if session else build_skirmish_world(**options)
    system = next(s for s in world.systems if type(s).__name__ == 'UIButtonSystem')
    entity = world.get_singleton_component(c.UIButtonCollection).get_button('end_turn')
    button = world.get_component(entity, c.UIButton)
    rect = world._ui_context.layout.footer.copy()
    def state():
        game = world.get_singleton_component(c.GameState)
        return [game.current_player.value, game.turn_number]
    def authority():
        return session.runtime.export_state() if session else export_initial_state(world, display='window')
    def draw():
        engine.screen.fill(FRAME_CLEAR_COLOR)
        if session:
            session.update_display(0, inputs=False)
        else:
            for s in world.systems:
                if type(s).__name__ in {'MapRenderSystem', 'UnitRenderSystem', 'EffectRenderSystem',
                                      'PanelRenderSystem', 'UIRenderSystem', 'MiniMapSystem',
                                      'UnitActionButtonSystem', 'UIButtonSystem'}:
                    s.update(0)
        RMS.update()
        pygame.display.flip()
    def save(phase):
        path = out / f'{backend}-{phase}.png'
        pygame.image.save(engine.screen, path)
        pygame.image.save(engine.screen.subsurface(rect), out / f'{backend}-button-{phase}.png')
        return hashlib.sha256(path.read_bytes()).hexdigest()
    def motion(pos):
        pygame.event.post(pygame.event.Event(pygame.MOUSEMOTION, pos=pos,
                                            rel=(0, 0), buttons=(0, 0, 0)))
        engine.input_manager.update()
    for _ in range(8):
        draw()
    pygame.event.clear()
    motion(rect.center)
    assert button.is_hovered
    before = state()
    pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=rect.center))
    pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=rect.center))
    engine.input_manager.update()
    after = state()
    assert before == ['wei', 1] and after == ['shu', 1]
    auth = authority()
    draw()
    assert system._button_is_pressed(button), 'quick click disappeared before its first frame'
    pressed_sha = save('pressed')
    pressed_rgb = pygame.image.tobytes(engine.screen.subsurface(rect), 'RGB')
    pressed_frames = 1
    started = time.monotonic()
    while system._button_is_pressed(button) and time.monotonic() - started < 1:
        clock.tick(60)
        draw()
        pressed_frames += int(system._button_is_pressed(button))
    assert not system._button_is_pressed(button) and button.is_hovered
    assert authority() == auth
    recovered_sha = save('recovered')
    recovered_rgb = pygame.image.tobytes(engine.screen.subsurface(rect), 'RGB')
    assert pressed_rgb != recovered_rgb
    # Compare within one feedback state, with its display clock held constant
    # only for this pair. The production animation above used the real clock.
    pixel_equal = None
    encoded_equal = None
    if session:
        pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=rect.center))
        pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=rect.center))
        engine.input_manager.update()
        assert state() == ['wei', 2]
        auth = authority()
        current_time = time.monotonic()
        system._feedback_clock = lambda: current_time
        draw()
        rgb = pygame.image.tobytes(engine.screen, 'RGB')
        encoded, error = session._capture_frame()
        assert error is None
        repaint_equal = pygame.image.tobytes(engine.screen, 'RGB') == rgb
        decoded = pygame.image.load(io.BytesIO(base64.b64decode(encoded)), 'frame.tga')
        encoded_equal = pygame.image.tobytes(decoded, 'RGB') == rgb
        pixel_equal = repaint_equal
        assert repaint_equal and authority() == auth
        system._feedback_clock = time.monotonic
        release_time = system._press_feedback_until + .01
        while time.monotonic() < release_time:
            clock.tick(60)
    motion((0, 0))
    auth = authority()
    draw()
    rest_sha = save('rest')
    assert not button.is_hovered and not system._button_is_pressed(button)
    assert authority() == auth and world._ui_context.layout.footer == rect
    stats = world._ui_context.cache_stats()
    assert stats['widget_entries'] <= 128 and stats['widget_bytes'] <= 8 * 1024 * 1024
    records.append(dict(backend=backend, driver=pygame.display.get_driver(),
                        size=engine.screen.get_size(), before=before, after_quick_click=after,
                        pressed_frames_at_60fps=pressed_frames, feedback_recovered=True,
                        press_pixels_distinct=True, paint_authority_equal=True,
                        hit_rectangle_unchanged=True, rust_vlm_repaint_window_rgb_equal=pixel_equal,
                        legacy_tga_sdl_decode_rgb_equal=encoded_equal,
                        cache_stats=stats, artifact_sha256=dict(pressed=pressed_sha,
                                                              recovered=recovered_sha, rest=rest_sha)))
    if session:
        session.close()
    else:
        world._ui_context.close()
        world.reset()
(out / 'cocoa.json').write_text(json.dumps(dict(passed=True, visual_version=VISUAL_VERSION,
    scope='Real Cocoa window, SDL event pump, real display feedback clock; no Agents/network or authority ticks',
    records=records), indent=2) + '\n')
engine.quit()
