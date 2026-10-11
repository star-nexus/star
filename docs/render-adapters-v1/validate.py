"""Run the renderer adoption regression and record exact local evidence."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
env = {**os.environ, 'SDL_VIDEODRIVER': 'dummy', 'SDL_AUDIODRIVER': 'dummy', 'PYTHONPATH': str(ROOT)}
tests = ['framework/tests', 'protocol/tests'] + [f'rotk_env/tests/{name}.py' for name in (
    'test_ui_context', 'test_ui_toolbar_clicks', 'test_native_controls', 'test_native_input',
    'test_native_session', 'test_native_hub', 'test_native_turn', 'test_turn',
    'test_terrain_presentation_cache', 'test_starbench_launcher', 'test_render_projection',
    'test_web_commands', 'test_web_server', 'test_renderer_adapters')]
commands = [[sys.executable, '-m', 'pytest', '-q', *tests],
            ['npm', 'test', '--prefix', 'rotk_env/rendering/web/client'],
            [sys.executable, 'docs/render-adapters-v1/check_desktop.py'],
            ['git', 'diff', '--check']]
records = []
for command in commands:
    started = time.monotonic()
    result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
    output = result.stdout + result.stderr
    summary = re.findall(r'\d+ passed[^\n]*|ℹ (?:tests|pass|fail)[^\n]*', output)
    records.append(dict(command=command, exit_code=result.returncode,
        elapsed_seconds=round(time.monotonic()-started, 3), summary=summary))
    print('PASS' if result.returncode == 0 else 'FAIL', ' '.join(command), *summary, sep='\n', flush=True)
    if result.returncode:
        print(output, flush=True)
        break

import star_native
import star_native._native
native_sha = hashlib.sha256(Path(star_native._native.__file__).read_bytes()).hexdigest()
previous = json.loads((ROOT / 'docs/ui-polish-v6/validation.json').read_text())['native_extension_sha256']
files = []
for folder in ('framework/presentation', 'rotk_env/rendering'):
    files += [p for p in (ROOT / folder).rglob('*') if p.is_file()
              and 'node_modules' not in p.parts and '__pycache__' not in p.parts]
files += [ROOT / f'rotk_env/runtime/{name}.py' for name in
          ('session', 'local_controls', 'authority', 'native', 'bootstrap')]
files += [ROOT / 'rotk_env/prefabs/world_builder.py', ROOT / 'starbench.py']
record = dict(date='2026-10-11', branch='codex/render-adapters', integration_base='2598697',
    passed=len(records) == len(commands) and all(r['exit_code'] == 0 for r in records) and native_sha == previous,
    pygame_visual_version='starbench-ui-v6', web_visual_version='starbench-web-v1',
    render_schema=1, native_api=star_native.API_VERSION, native_schema=5,
    native_extension_sha256=native_sha, native_binary_unchanged=native_sha == previous,
    checks=records,
    source_sha256={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)},
    artifact_sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(OUT.iterdir())
        if p.suffix in ('.jpg', '.png') or p.name in ('desktop-parity.json', 'browser-validation.json')})
(OUT / 'validation.json').write_text(json.dumps(record, indent=2, ensure_ascii=False) + '\n')
raise SystemExit(0 if record['passed'] else 1)
