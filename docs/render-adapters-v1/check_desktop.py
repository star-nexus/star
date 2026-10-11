"""Compare the merged UI session with the adapter session using identical pixels.

Run from the repository root with its .venv/bin/python. The baseline source is
read from Git; no branch, checkout or native binary is changed by this probe.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import types

os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'
os.environ['HEADLESS'] = '0'
time.time = lambda: 1700000000.0

import pygame
from framework.engine import RMS
from framework.engine.game_engine import GameEngine
from framework.engine.renders import FRAME_CLEAR_COLOR
from rotk_env.prefabs.config import GameConfig
from rotk_env.runtime.session import NativeSession
from rotk_env.ui.context import VISUAL_VERSION

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
baseline = types.ModuleType('rotk_env.runtime.desktop_baseline')
baseline.__package__ = 'rotk_env.runtime'
exec(subprocess.check_output(['git', 'show', '2598697:rotk_env/runtime/session.py'], cwd=ROOT, text=True), baseline.__dict__)
engine = GameEngine(width=1200, height=900, title='Renderer parity probe')
GameConfig.sync_from_display()
records = []
def gameplay(state):
    return sorted((row['components'] for row in state['entities'] if 'Unit' in row['components']),
                  key=lambda row: row['Unit']['name'])

def profile(state):
    return {name: {key: state['systems'][name][key] for key in ('window', 'indexed')}
            for name in ('VisionSystem', 'StatisticsSystem')}

try:
    for label, session_class in [('before', baseline.NativeSession), ('after', NativeSession)]:
        with session_class(display='window', scenario='river_split', seed=42) as session:
            authority = session.runtime.export_state()
            if label == 'after': desktop_initial = authority
            for _ in range(8):
                engine.screen.fill(FRAME_CLEAR_COLOR)
                session.update_display(0, inputs=False)
                RMS.update()
            rgb = pygame.image.tobytes(engine.screen, 'RGB')
            frame, error = session._capture_frame() if label == 'before' else session.frame_provider.capture()
            assert not error and session.runtime.export_state() == authority
            path = OUT / f'pygame-{label}.png'; pygame.image.save(engine.screen, path)
            records.append(dict(label=label, rgb_sha256=hashlib.sha256(rgb).hexdigest(),
                capture_sha256=hashlib.sha256(base64.b64decode(frame)).hexdigest(),
                paint_authority_equal=True, image=path.name))
    with NativeSession(renderer='web', scenario='river_split', seed=42) as web:
        streamed = web.runtime.export_state()
        assert gameplay(streamed) == gameplay(desktop_initial)
        assert streamed['singletons']['FogOfWar'] == desktop_initial['singletons']['FogOfWar']
        assert profile(streamed) == profile(desktop_initial)
        assert all(all(flags.values()) for flags in profile(streamed).values())
        assert 'AnimationSystem' in streamed['systems'] and web.world.systems == []
    assert records[0]['rgb_sha256'] == records[1]['rgb_sha256']
    assert records[0]['capture_sha256'] == records[1]['capture_sha256']
    (OUT / 'desktop-parity.json').write_text(json.dumps(dict(passed=True,
        baseline='2598697', visual_version=VISUAL_VERSION, size=engine.screen.get_size(),
        driver=pygame.display.get_driver(), records=records,
        web_desktop_gameplay_initial_equal=True, web_desktop_fog_initial_equal=True,
        web_interactive_profile=profile(streamed)), indent=2) + '\n')
finally:
    engine.quit()
