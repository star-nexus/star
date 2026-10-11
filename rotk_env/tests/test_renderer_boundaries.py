"""Architecture gates for pure rules/data, including imports inside functions."""
import ast
from importlib.util import resolve_name
from pathlib import Path
import subprocess
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[2]
# Existing desktop compatibility leaves may stay at their historical paths.
# New renderer implementation belongs under rendering/ or ui/, not these roots.
DESKTOP_SYSTEMS = frozenset('''animation_system window_animation_system
input_system window_input_system unit_action_button_system ui_button_system
fast_render_systems optimized_render_systems window_render_systems_base
fog_surface_presenter terrain_presentation_cache minimap_system window_minimap_system
map_render_system window_map_render_system unit_render_system window_unit_render_system
effect_render_system window_effect_render_system game_over_render_system
panel_render_system start_scene_render_system settlement_report_render_system ui_render_system'''.split())
FORBIDDEN = ('pygame', 'pyglet', 'moderngl', 'OpenGL', 'sdl2', 'wgpu',
    'framework.RMS', 'framework.IPS', 'framework.GameEngine',
    'framework.engine.renders', 'framework.engine.inputs', 'framework.engine.game_engine',
    'framework.engine.frame_capture', 'framework.engine.RMS', 'framework.engine.IPS',
    'framework.engine.GameEngine', 'rotk_env.ui', 'rotk_env.rendering.pygame',
    'rotk_env.rendering.web', 'rotk_env.rendering.pygame_adapter',
    'rotk_env.runtime.native_input', 'rotk_env.runtime.window_presentation')


def module_name(path):
    parts = path.relative_to(ROOT).with_suffix('').parts
    return '.'.join(parts[:-1] if parts[-1] == '__init__' else parts)


def imports(path):
    module = module_name(path)
    package = module if path.name == '__init__.py' else module.rpartition('.')[0]
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            yield from (alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = resolve_name('.' * node.level + (node.module or ''), package) if node.level else node.module
            yield base
            for alias in node.names:
                yield base + '.' + alias.name
        elif (isinstance(node, ast.Call) and node.args and isinstance(node.args[0], ast.Constant)
              and isinstance(node.args[0].value, str)):
            name = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, 'attr', '')
            if name in ('__import__', 'import_module'):
                target = node.args[0].value
                yield resolve_name(target, package) if target.startswith('.') else target


def test_core_cannot_reach_renderer_implementation_through_imports():
    files = [p for base in ('framework', 'rotk_env', 'protocol')
             for p in (ROOT / base).rglob('*.py') if 'tests' not in p.parts]
    graph = {module_name(p): set(imports(p)) for p in files}
    protected = {module_name(p) for p in files if (
        p.is_relative_to(ROOT / 'framework/ecs') or
        p.is_relative_to(ROOT / 'framework/presentation') or
        p.is_relative_to(ROOT / 'protocol') or
        p.is_relative_to(ROOT / 'rotk_env/components') or
        p.is_relative_to(ROOT / 'rotk_env/utils') or
        (p.parent == ROOT / 'rotk_env/runtime' and p.stem not in ('session', 'native_input', 'window_presentation')) or
        (p.parent == ROOT / 'rotk_env/systems' and p.stem not in DESKTOP_SYSTEMS) or
        p == ROOT / 'rotk_env/prefabs/config.py' or p == ROOT / 'rotk_env/prefabs/action_catalog.py' or
        p in {ROOT / 'rotk_env/rendering' / name for name in ('projection.py', 'tactics.py', 'commands.py')})}
    violations = []
    for source in sorted(protected):
        queue, seen = [(source, [source])], set()
        while queue:
            module, route = queue.pop()
            if module in seen:
                continue
            seen.add(module)
            for target in graph.get(module, ()):
                # Bootstrap reaches the display-selection composition gateway.
                # Its none/Web branches are independently checked with imports
                # blocked at runtime; selected desktop branches may load leaves.
                if module == 'rotk_env.runtime.bootstrap' and target.startswith('rotk_env.prefabs.world_builder'):
                    continue
                if any(target == prefix or target.startswith(prefix + '.') for prefix in FORBIDDEN):
                    violations.append(' -> '.join(route + [target]))
                elif target in graph:
                    queue.append((target, route + [target]))
    assert not violations, '\n'.join(violations)


def test_rust_dependency_lock_has_no_graphics_engine():
    packages = tomllib.loads((ROOT / 'Cargo.lock').read_text())['package']
    engines = {'bevy', 'bevy_render', 'bevy_winit', 'wgpu', 'sdl2', 'glow', 'glium'}
    assert not engines.intersection(row['name'] for row in packages)


def test_successful_vlm_without_renderer_never_imports_an_engine():
    code = '''
import importlib.abc, sys
class Reject(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, *args):
        if fullname == 'pygame' or fullname.startswith(('pygame.', 'rotk_env.ui.', 'rotk_env.rendering.pygame', 'rotk_env.rendering.web', 'framework.engine.renders', 'framework.engine.frame_capture')):
            raise AssertionError('core imported ' + fullname)
sys.meta_path.insert(0, Reject())
from framework.presentation.capture import capture_observation_frame
from rotk_env.components import MatchRules
from rotk_env.runtime.bootstrap import prepare_display_world, export_initial_state
from rotk_env.runtime.native import RustRuntime
from rotk_env.runtime.authority import AuthorityRuntime
from rotk_env.runtime.session import NativeSession
from rotk_env.runtime.identity import runtime_identity
from rotk_env.systems.llm_action_handler import LLMActionHandler
world, _ = prepare_display_world(display='none', scenario='chibi-small', seed=42)
world.add_singleton_component(MatchRules(game_actions=('get_faction_state', 'get_faction_state_vlm')))
initial = export_initial_state(world)
expected = capture_observation_frame()[1]
for threaded in (False, True):
    raw = RustRuntime(initial)
    runtime = AuthorityRuntime(raw, on_publication=lambda delta: []) if threaded else raw
    try:
        assert runtime.execute_action('register_agent_info', dict(faction='wei', provider='synthetic', model_id='fixture', base_url='https://host'), agent_id='a')['success']
        result = runtime.execute_action('get_faction_state_vlm', {'faction':'wei'}, agent_id='a')
        assert result['success'] and result['frame_base64'] is None and result['frame_error'] == expected
    finally:
        runtime.close()
result = LLMActionHandler(world).handle_faction_state_vlm({'faction':'wei'})
assert result['success'] and result['frame_error'] == expected
with NativeSession(scenario='chibi-small', seed=42) as session:
    assert session.frame_provider.capture() == (None, expected)
identity = runtime_identity('rust', env_id='fixture', mode='turn_based', scenario='chibi-small', seed=42, scheduling='threaded', threads=1)
assert identity['visual_version'] == 'none'
world.reset()
assert 'pygame' not in sys.modules
'''
    subprocess.run([sys.executable, '-c', code], check=True, timeout=20)
