"""Cocoa Space/End Turn resource regression with production SDL dispatch.

Run with this worktree's .venv/bin/python, repository path, and output path.
No Hub, Agent or simulation ticks are started.
"""
import hashlib
import json
import os
import sys
from pathlib import Path

source, out = (Path(arg).resolve() for arg in sys.argv[1:3])
os.chdir(source)
sys.path.insert(0, str(source))
os.environ['HEADLESS'] = '0'
os.environ['SDL_VIDEODRIVER'] = 'cocoa'
out.mkdir(parents=True, exist_ok=True)

import pygame
from framework.engine import RMS
from framework.engine.events import EBS
from framework.engine.game_engine import GameEngine
from framework.engine.renders import FRAME_CLEAR_COLOR
from rotk_env import components as c
from rotk_env.prefabs.config import Faction, GameConfig, PlayerType
from rotk_env.prefabs.world_builder import build_skirmish_world
from rotk_env.runtime.bootstrap import export_initial_state
from rotk_env.runtime.session import NativeSession
from rotk_env.ui.context import VISUAL_VERSION
from rotk_env.utils.env_events import TurnStartEvent

engine = GameEngine(width=1200, height=900, title='STARBench turn parity validation')
GameConfig.sync_from_display()
records = []
for backend in ('python', 'rust'):
    seen = []
    options = dict(display='window', scenario='river_split', mode='turn_based', seed=42,
                   hub_url=None, players={Faction.WEI: PlayerType.HUMAN, Faction.SHU: PlayerType.AI})
    def native_events(events):
        seen.extend(event['fields']['faction'] for event in events if event['type'] == 'TurnStartEvent')
    session = NativeSession(authority_scheduling=True, on_events=native_events, **options) if backend == 'rust' else None
    world = session.world if session else build_skirmish_world(**options)
    unit = next(uid for uid in world.query().with_all(c.Unit, c.ActionPoints).ordered_entities()
                if world.get_component(uid, c.Unit).faction == Faction.WEI)
    world.get_singleton_component(c.UIState).selected_unit = unit
    actions = next(s for s in world.systems if type(s).__name__ == 'UnitActionButtonSystem')
    def state():
        game = world.get_singleton_component(c.GameState)
        return [game.current_player.value, game.turn_number]
    def authority():
        return session.runtime.export_state() if session else export_initial_state(world, display='window')
    def python_event(event):
        seen.append(event.faction.value)
    if not session:
        EBS.subscribe(TurnStartEvent, python_event)
    def draw():
        engine.screen.fill(FRAME_CLEAR_COLOR)
        if session:
            session.update_display(0, inputs=False)
        else:
            for system in world.systems:
                if type(system).__name__ in {'MapRenderSystem', 'UnitRenderSystem', 'EffectRenderSystem',
                    'PanelRenderSystem', 'UIRenderSystem', 'MiniMapSystem', 'UnitActionButtonSystem', 'UIButtonSystem'}:
                    system.update(0)
        RMS.update()
        pygame.display.flip()
    try:
        for _ in range(8):
            draw()
        pygame.event.clear()
        for entry, expected in (('space', ['shu', 1]), ('button', ['wei', 2])):
            before = state()
            for _ in range(world.get_component(unit, c.ActionPoints).current_ap):
                actions._execute_wait_action(unit)
            ap_before = world.get_component(unit, c.ActionPoints).current_ap
            assert ap_before == 0
            if entry == 'space':
                pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE, mod=0))
                pygame.event.post(pygame.event.Event(pygame.KEYUP, key=pygame.K_SPACE))
            else:
                point = world._ui_context.layout.footer.center
                pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=point))
                pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=point))
            engine.input_manager.update()
            ap = world.get_component(unit, c.ActionPoints)
            assert ap.current_ap == ap.max_ap and state() == expected
            for uid in world.query().with_component(c.MovementPoints).ordered_entities():
                movement = world.get_component(uid, c.MovementPoints)
                count = world.get_component(uid, c.UnitCount)
                effective = movement.get_effective_movement(count) if count else movement.max_mp
                assert movement.current_mp == effective and not movement.has_moved
            draw()
            auth = authority()
            for _ in range(5):
                draw()
            assert authority() == auth and state() == expected
            path = out / f'turn-parity-{backend}-{entry}.png'
            pygame.image.save(engine.screen, path)
            records.append(dict(backend=backend, entry=entry, driver=pygame.display.get_driver(),
                size=engine.screen.get_size(), before=before, after=state(),
                ap_before=ap_before, ap_after=ap.current_ap, ap_max=ap.max_ap,
                movement_reset=True, paint_authority_equal=True,
                image=path.name, image_sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
        assert seen == ['shu', 'wei']
    finally:
        if session:
            session.close()
        else:
            EBS.unsubscribe(TurnStartEvent, python_event)
            world._ui_context.close()
            world.reset()
(out / 'turn-parity-cocoa.json').write_text(json.dumps(dict(passed=True,
    visual_version=VISUAL_VERSION, records=records,
    scope='Cocoa SDL input and post-command display; no authority ticks, Agents or network'), indent=2) + '\n')
engine.quit()
