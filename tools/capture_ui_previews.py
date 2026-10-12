"""Capture exact-size UI previews without input, networking or world ticks."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
SIZES = ((1200, 800), (1200, 900), (1440, 900), (1920, 1080), (2480, 1263))
PAINTERS = {'MapRenderSystem', 'UnitRenderSystem', 'EffectRenderSystem',
            'PanelRenderSystem', 'UIRenderSystem', 'MiniMapSystem',
            'UnitActionButtonSystem', 'UIButtonSystem'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--backend', choices=('rust', 'python'), default='rust')
    args = parser.parse_args(argv)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    os.environ['HEADLESS'] = '0'
    os.environ['SDL_VIDEODRIVER'] = 'dummy'

    import pygame
    from framework.engine import RMS
    from framework.engine.renders import FRAME_CLEAR_COLOR
    from framework.engine.game_engine import GameEngine
    from rotk_env import components as c
    from rotk_env.prefabs.config import GameConfig, Faction, PlayerType
    from rotk_env.prefabs.world_builder import build_skirmish_world
    from rotk_env.runtime.bootstrap import export_initial_state
    from rotk_env.scenes.start_scene import StartScene
    from rotk_env.ui.context import VISUAL_VERSION
    from rotk_env.utils.hex_utils import HexConverter

    engine = GameEngine(width=1200, height=800)
    engine.runtime_backend = args.backend
    session = world = scene = None
    captures = {}

    def resize(size):
        engine.screen = pygame.display.set_mode(size, pygame.RESIZABLE)
        RMS.screen = engine.screen
        GameConfig.sync_from_display()
        assert engine.screen.get_size() == size

    def save(name):
        path = output / name
        pygame.image.save(engine.screen, path)
        captures[name] = dict(size=engine.screen.get_size(), sha256=hashlib.sha256(path.read_bytes()).hexdigest())

    try:
        scene = StartScene(engine)
        scene.enter()
        for size in SIZES:
            resize(size)
            scene.update(0)
            RMS.update()
            save(f'menu-{size[0]}x{size[1]}.png')
        scene.exit()
        scene = None

        options = dict(display='window', scenario='river_split', seed=42,
                       hub_url=None, mode='real_time',
                       players={Faction.WEI: PlayerType.HUMAN,
                                Faction.SHU: PlayerType.AI, Faction.WU: PlayerType.AI})
        if args.backend == 'rust':
            from rotk_env.runtime.session import NativeSession
            session = NativeSession(authority_scheduling=False, **options)
            world = session.world
        else:
            world = build_skirmish_world(**options)
        ui = world.get_singleton_component(c.UIState)
        ui.selected_unit = next(uid for uid in world.query().with_component(c.Unit).ordered_entities()
                                if world.get_component(uid, c.Unit).faction == Faction.WEI)
        position = world.get_component(ui.selected_unit, c.HexPosition)
        x, y = HexConverter(GameConfig.HEX_SIZE, GameConfig.HEX_ORIENTATION).hex_to_pixel(position.col, position.row)
        for size in SIZES:
            resize(size)
            ctx = world._ui_context
            ctx.sync(world)
            camera = world.get_singleton_component(c.Camera)
            for pose in ('initial', 'selected', 'help'):
                if pose == 'initial':
                    ctx.frame_map(world)
                    ui.selected_unit = None
                else:
                    ui.selected_unit = next(uid for uid in world.query().with_component(c.Unit).ordered_entities()
                                            if world.get_component(uid, c.Unit).faction == Faction.WEI)
                    camera.zoom = .85
                    camera.set_offset(ctx.layout.viewport.centerx-x*.85, ctx.layout.viewport.centery-y*.85)
                ui.show_help = pose == 'help'
                before = session.runtime.export_state() if session else export_initial_state(world, display='window')
                for _ in range(8):
                    engine.screen.fill(FRAME_CLEAR_COLOR)
                    if session:
                        session.update_display(0, inputs=False)
                    else:
                        for system in world.systems:
                            if type(system).__name__ in PAINTERS:
                                system.update(0)
                    RMS.update()
                after = session.runtime.export_state() if session else export_initial_state(world, display='window')
                assert before == after, 'paint changed authoritative state'
                save(f'battle-{pose}-{size[0]}x{size[1]}.png')
        record = dict(visual_version=VISUAL_VERSION, backend=args.backend,
                      source_sha=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
                      source_dirty=bool(subprocess.check_output(['git', 'status', '--porcelain'], text=True).strip()),
                      driver=pygame.display.get_driver(), pure_paint_authority_equal=True,
                      scope='Exact-size raster QA; no real-window, network or capacity claim.', files=captures)
        if session:
            from star_rust_runtime import _native
            record['extension_sha256'] = hashlib.sha256(Path(_native.__file__).read_bytes()).hexdigest()
        (output/'result.json').write_text(json.dumps(record, indent=2)+'\n')
        print(json.dumps(record))
    finally:
        if scene:
            scene.exit()
        if session:
            session.close()
        elif world:
            world._ui_context.close()
            world.reset()
        engine.quit()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
