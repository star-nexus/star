"""Verify PNG observation bytes and desktop pixels against the saved v6 baseline.

Run with PYTHONPATH=. .venv/bin/python from the repository root. This compares
the committed acceptance screenshot, without loading old code against new helpers.
"""
import argparse
import base64
import hashlib
import io
import json
import os
from pathlib import Path
from unittest.mock import patch

os.environ.update(SDL_VIDEODRIVER='dummy', SDL_AUDIODRIVER='dummy', HEADLESS='0')

import pygame
from framework.engine import RMS
from framework.engine.game_engine import GameEngine
from framework.engine.renders import FRAME_CLEAR_COLOR
from rotk_env.rendering.pygame.display import sync_game_config_from_display
from rotk_env.runtime.native import _complete_result
from rotk_env.runtime.session import NativeSession
from rotk_env.ui.context import VISUAL_VERSION


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    options = parser.parse_args()
    options.output.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).resolve().parents[2]
    baseline_path = root / 'docs/render-adapters-acceptance/pygame-before.png'
    baseline = pygame.image.load(str(baseline_path))
    digest = lambda data: hashlib.sha256(data).hexdigest()
    engine = GameEngine(width=1200, height=900, title='Renderer fix acceptance')
    sync_game_config_from_display()
    try:
        with patch('time.time', lambda: 1700000000.0):
            with NativeSession(display='window', scenario='river_split', seed=42) as scene:
                authority = scene.runtime.export_state()
                for _ in range(8):
                    engine.screen.fill(FRAME_CLEAR_COLOR)
                    scene.update_display(0, inputs=False)
                    RMS.update()
                result = _complete_result('get_faction_state_vlm', {'success': True},
                    scene.frame_provider.capture)
                assert result['frame_format'] == 'png' and not result.get('frame_error')
                data = base64.b64decode(result['frame_base64'])
                assert data.startswith(b'\x89PNG\r\n\x1a\n')
                decoded = pygame.image.load(io.BytesIO(data), 'frame.png')
                rgb = pygame.image.tobytes(decoded, 'RGB')
                expected = pygame.image.tobytes(baseline, 'RGB')
                assert decoded.get_size() == baseline.get_size() == engine.screen.get_size()
                assert rgb == expected
                assert scene.runtime.export_state() == authority
                (options.output / 'pygame-v7.png').write_bytes(data)
                record = dict(passed=True, visual_version=VISUAL_VERSION,
                    baseline_visual_version='starbench-ui-v6', baseline=str(baseline_path.relative_to(root)),
                    size=decoded.get_size(), png_signature=True, frame_format=result['frame_format'],
                    capture_sha256=digest(data), rgb_sha256=digest(rgb),
                    baseline_rgb_sha256=digest(expected), pixel_equal=True,
                    authority_unchanged_by_capture=True,
                    prior_capture_encoding='TGA', current_capture_encoding='PNG')
                (options.output / 'capture-validation.json').write_text(json.dumps(record, indent=2) + '\n')
                print('PNG capture and v6 desktop pixel parity: PASS')
    finally:
        engine.quit()


if __name__ == '__main__':
    main()
