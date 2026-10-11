"""Finite UI snapshots and real-display render regression guard (not capacity)."""
import argparse
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import sys
import time
from rotk_env.rendering.pygame.display import sync_game_config_from_display


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--task', choices=['snapshots', 'performance', 'smoke'], required=True)
    p.add_argument('--backend', choices=['rust', 'python'], default='rust')
    p.add_argument('--units', type=int, default=12)
    p.add_argument('--candidate', action='store_true')
    p.add_argument('--source-sha', default='development')
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=True)
    os.chdir(a.source)
    sys.path.insert(0, str(a.source))
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    os.environ['HEADLESS'] = '0'
    os.environ.pop('SDL_VIDEODRIVER', None)
    import pygame
    from framework.engine.game_engine import GameEngine
    from framework.engine import RMS
    from framework.engine.renders import FRAME_CLEAR_COLOR
    from rotk_env import components as c
    from rotk_env.prefabs.config import Faction, PlayerType, UnitType, GameConfig
    from rotk_env.runtime.session import NativeSession
    from rotk_env.prefabs.world_builder import build_skirmish_world
    from rotk_env.scenes.start_scene import StartScene
    from star_native import _native
    engine = GameEngine(title='STARBench UI validation', width=1200, height=800)
    sync_game_config_from_display()
    assert pygame.display.get_driver() == 'cocoa', 'real-window validation requires Cocoa'
    scene = None
    session = None
    world = None
    fixture_file = a.source / 'rotk_env/maps/lab-p3-canonical-5000.json'
    previous = fixture_file.read_bytes() if fixture_file.exists() else None
    rows = []
    files = []
    try:
        if a.task == 'snapshots':
            engine.runtime_backend = a.backend
            scene = StartScene(engine)
            scene.enter()
            sizes = [(1200, 800), (1440, 900), (1920, 1080), (2480, 1263)] if a.candidate else [(2480, 1263)]
            for w, h in sizes:
                engine.screen = pygame.display.set_mode((w, h), pygame.RESIZABLE)
                RMS.screen = engine.screen
                sync_game_config_from_display()
                scene.update(0)
                RMS.update()
                pygame.display.flip()
                path = a.output / f'menu-{w}x{h}.png'
                pygame.image.save(engine.screen, path)
                files.append(path.name)
            scene.exit()
            scene = None
        scenario = 'river_split'
        if a.units == 5000:
            from p3_local_agents import fixture
            scenario, _ = fixture(a.source, 5000)
        options = dict(display='window', scenario=scenario, seed=42, hub_url=None,
                       mode='real_time', players={Faction.WEI: PlayerType.HUMAN,
                       Faction.SHU: PlayerType.AI, Faction.WU: PlayerType.AI})
        if a.backend == 'rust':
            session = NativeSession(authority_scheduling=a.task == 'smoke', **options)
            world = session.world
        else:
            world = build_skirmish_world(**options)
        units = world.query().with_component(c.Unit).ordered_entities()
        selected = next(i for i in units if world.get_component(i, c.Unit).faction == Faction.WEI)
        ui = world.get_singleton_component(c.UIState)
        ui.selected_unit = selected
        # Fixed projection only: no clock or gameplay update in timed sections.
        def draw():
            engine.screen.fill(FRAME_CLEAR_COLOR)
            if session is not None:
                session.update_display(0, inputs=False)
                # Legacy native capture omitted controls. Include their full paint
                # cost with an empty input set; candidate has pure paint hooks.
                world.get_singleton_component(c.InputState).mouse_pressed.clear()
                for controls in world.systems:
                    if type(controls).__name__ in ('UnitActionButtonSystem', 'UIButtonSystem') and not hasattr(controls, 'render_only'):
                        controls.update(0)
            else:
                for s in world.systems:
                    if type(s).__name__ in ('MapRenderSystem', 'UnitRenderSystem', 'EffectRenderSystem',
                            'PanelRenderSystem', 'UIRenderSystem', 'MiniMapSystem', 'UnitActionButtonSystem', 'UIButtonSystem'):
                        s.update(0)
            RMS.update()
        if a.task == 'snapshots':
            for w, h in sizes:
                engine.screen = pygame.display.set_mode((w, h), pygame.RESIZABLE)
                RMS.screen = engine.screen
                sync_game_config_from_display()
                ctx = getattr(world, '_ui_context', None)
                if ctx:
                    ctx.sync(world)
                camera = world.get_singleton_component(c.Camera)
                pos = world.get_component(selected, c.HexPosition)
                from rotk_env.utils.hex_utils import HexConverter
                x, y = HexConverter(GameConfig.HEX_SIZE, GameConfig.HEX_ORIENTATION).hex_to_pixel(pos.col, pos.row)
                center = ctx.layout.viewport.center if ctx else (w / 2, h / 2)
                camera.zoom = .85
                camera.set_offset(center[0] - x * camera.zoom, center[1] - y * camera.zoom)
                for pose in ('selected', 'help'):
                    ui.show_help = pose == 'help'
                    draw()
                    pygame.display.flip()
                    path = a.output / f'battle-{pose}-{w}x{h}.png'
                    pygame.image.save(engine.screen, path)
                    files.append(path.name)
            ui.show_help = False
        elif a.task == 'performance':
            camera = world.get_singleton_component(c.Camera)
            camera.zoom = .85
            started = time.perf_counter()
            deadline = started
            while time.perf_counter() - started < 40:
                pygame.event.pump()
                t = time.perf_counter() - started
                t0 = time.perf_counter_ns()
                draw()
                t1 = time.perf_counter_ns()
                pygame.display.flip()
                t2 = time.perf_counter_ns()
                rows.append(dict(t=t, draw_ns=t1-t0, present_ns=t2-t1))
                deadline += 1 / 30
                wait = deadline - time.perf_counter()
                if wait > 0:
                    time.sleep(wait)
            pygame.image.save(engine.screen, a.output / 'performance.png')
            files.append('performance.png')
        else:
            # A short main-thread real-window integration check, all actions use existing dispatch.
            from framework.engine import KeyDownEvent, MouseButtonDownEvent
            inp = next(s for s in world.systems if type(s).__name__ == 'InputHandlingSystem')
            from rotk_env.runtime.bootstrap import encode
            def authority_state():
                if session:
                    return session.runtime.export_state()
                return {str(cls): encode(world.get_singleton_component(cls)) for cls in
                        (c.GameState, c.GameTime, c.FogOfWar, c.GameStats)} | {
                        'units': {str(uid): {str(cls): encode(world.get_component(uid,cls))
                        for cls in (c.Unit,c.UnitCount,c.HexPosition,c.MovementPoints,c.Combat,c.ActionPoints)} for uid in units}}
            for _ in range(8):
                draw()
            before = authority_state()
            draw()
            pygame.display.flip()
            assert before == authority_state(), 'pure draw changed authority'
            if session:
                pixels = pygame.image.tobytes(engine.screen, 'RGB')
                _, error = session._capture_frame()
                assert error is None
                pygame.image.save(engine.screen, a.output/'capture.png')
                files.append('capture.png')
                assert pixels == pygame.image.tobytes(engine.screen, 'RGB'), 'VLM paint differs from window'
                assert before == authority_state(), 'VLM capture changed authority'
            for key, mod in [(pygame.K_1, 0), (pygame.K_a, 0), (pygame.K_ESCAPE, 0),
                             (pygame.K_F1, 0), (pygame.K_F1, 0), (pygame.K_1, pygame.KMOD_SHIFT),
                             (pygame.K_1, pygame.KMOD_SHIFT)]:
                inp._handle_key_down(KeyDownEvent(sender='ui-probe', timestamp=0, key=key, mod=mod))
                draw()
            assert ui.selected_unit is not None
            inp._action_unit_move()
            assert inp._targeting_action == 'move'
            inp._action_clear_selection()
            inp._action_unit_wait()
            after_action = authority_state()
            assert after_action != before, 'wait shortcut did not execute'
            ctx = getattr(world, '_ui_context', None)
            if ctx:
                chosen = ui.selected_unit
                inp._handle_mouse_click(MouseButtonDownEvent(sender='ui-probe', timestamp=0,button=1,pos=ctx.layout.sidebar.center))
                assert ui.selected_unit == chosen
                assert authority_state() == after_action, 'panel click admitted a map action'
                ctx.scroll_at(ctx.layout.sidebar.center, -3, world)
                assert ctx.scroll > 0
                mini = next(s for s in world.systems if type(s).__name__ == 'MiniMapSystem')
                mini._move_camera_to_position((0,0))
            engine.screen = pygame.display.set_mode((1440, 900), pygame.RESIZABLE)
            RMS.screen = engine.screen
            sync_game_config_from_display()
            inp._follow_window_resize()
            draw()
            pygame.display.flip()
            pygame.image.save(engine.screen, a.output / f'smoke-{a.backend}.png')
            files.append(f'smoke-{a.backend}.png')
        measured = [r for r in rows if r['t'] >= 10]
        def stats(key):
            values = sorted(r[key] for r in measured)
            return dict(samples=len(values), mean_ns=sum(values)/len(values),
                        p99_ns=values[math.ceil(len(values)*.99)-1], max_ns=values[-1]) if values else None
        ctx = getattr(world, '_ui_context', None)
        raw = a.output / 'samples.json.gz'
        raw.write_bytes(gzip.compress(json.dumps(rows).encode(), mtime=0))
        result = dict(passed=True, source_sha=a.source_sha, probe_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), dependency_lock_sha256=hashlib.sha256((a.source/'uv.lock').read_bytes()).hexdigest(), backend=a.backend, task=a.task, units=len(units),
                      driver=pygame.display.get_driver(), python=sys.version, os=platform.platform(),
                      warmup_s=10 if rows else None, measurement_s=30 if rows else None,
                      render=stats('draw_ns'), present=stats('present_ns'),
                      visual_version=getattr(ctx, 'visual_version', 'legacy'),
                      cache=ctx.cache_stats() if ctx else None,
                      extension_sha256=hashlib.sha256(Path(_native.__file__).read_bytes()).hexdigest(),
                      files={name: hashlib.sha256((a.output/name).read_bytes()).hexdigest() for name in files},
                      raw_sha256=hashlib.sha256(raw.read_bytes()).hexdigest(),
                      authority_scheduling=a.task == 'smoke' and a.backend == 'rust',
                      scope='fixed display projection; no agents/network/authority throughput claim')
        (a.output / 'result.json').write_text(json.dumps(result, indent=2)+'\n')
        print(json.dumps(result), flush=True)
    finally:
        if scene:
            scene.exit()
        if session:
            session.close()
        elif world:
            context = getattr(world, '_ui_context', None)
            if context:
                context.close()
            world.reset()
        if previous is None:
            fixture_file.unlink(missing_ok=True)
        else:
            fixture_file.write_bytes(previous)
        engine.quit()


if __name__ == '__main__':
    main()
