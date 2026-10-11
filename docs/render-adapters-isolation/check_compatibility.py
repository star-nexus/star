"""Audit the dependency split against its parent and the accepted native binary.

Run from the repo root with PYTHONPATH=. and the native + pygame extras.
No checkout, branch or Rust binary is changed.
"""
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import time
import types

import star_native
from rotk_env.prefabs import world_builder
from rotk_env.runtime.session import NativeSession

BASELINE = '1fc91c4'
OUT = Path(__file__).resolve().parent


def old_source(path):
    return subprocess.check_output(['git', 'show', f'{BASELINE}:{path}'], text=True)


def methods(source):
    cls = next(n for n in ast.parse(source).body if isinstance(n, ast.ClassDef))
    return {n.name: ast.dump(n, include_attributes=False) for n in cls.body
            if isinstance(n, ast.FunctionDef)}


original = methods(old_source('rotk_env/systems/animation_system.py'))
pure = methods(Path('rotk_env/systems/animation_lifecycle.py').read_text())
kept = set(original) - {'__init__', 'initialize', 'render_damage_numbers'}
assert all(original[name] == pure[name] for name in kept)
interactive = methods(Path('rotk_env/systems/interactive_animation_lifecycle.py').read_text())
assert methods(old_source('rotk_env/systems/window_animation_system.py')) == interactive
pygame_methods = methods(Path('rotk_env/rendering/pygame/animation.py').read_text())
assert pygame_methods['render_damage_numbers'] == original['render_damage_numbers']

binary = next(Path(star_native.__file__).parent.glob('*.so'))
binary_sha = hashlib.sha256(binary.read_bytes()).hexdigest()
previous = json.loads(Path('docs/render-adapters-v2/validation.json').read_text())
assert binary_sha == previous['native_extension_sha256']
assert not subprocess.check_output(['git', 'diff', BASELINE, '--',
                                   'rotk_env/rendering/web/client'], text=True)
client_paths = subprocess.check_output(['git', 'ls-files',
    'rotk_env/rendering/web/client'], text=True).splitlines()

# Compare entire Web initial authority and authorized display snapshots. The
# baseline intentionally imports pygame; the current path is separately checked
# with a hard import blocker and an environment without the package installed.
baseline = types.ModuleType('rotk_env.prefabs.baseline_builder')
baseline.__package__ = 'rotk_env.prefabs'
exec(old_source('rotk_env/prefabs/world_builder.py'), baseline.__dict__)
current = world_builder.build_skirmish_world
clock = time.time
states, snapshots = [], []
try:
    time.time = lambda: 1700000000.0
    for build in (baseline.build_skirmish_world, current):
        world_builder.build_skirmish_world = build
        with NativeSession(renderer='web', scenario='chibi-small', seed=42) as session:
            states.append(session.runtime.export_state())
            snapshots.append(session.renderer.model.snapshot('wei'))
    assert states[0] == states[1]
    assert snapshots[0] == snapshots[1]
finally:
    world_builder.build_skirmish_world = current
    time.time = clock

record = dict(passed=True, baseline=BASELINE, native_api=star_native.API_VERSION,
    native_schema=5, native_extension_sha256=binary_sha, native_binary_unchanged=True,
    lifecycle_methods_unchanged=len(kept), interactive_methods_unchanged=len(interactive),
    pygame_damage_drawing_unchanged=True, web_client_unchanged=True,
    web_initial_authority_equal=True, web_initial_snapshot_equal=True,
    web_snapshot_sha256=hashlib.sha256(json.dumps(snapshots[1], sort_keys=True).encode()).hexdigest(),
    web_client_source_sha256={p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
                              for p in client_paths})
(OUT / 'compatibility.json').write_text(json.dumps(record, indent=2) + '\n')
print('Lifecycle, native binary, Web authority and snapshot parity passed')
