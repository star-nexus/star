"""Renderer substitution preserves authority and closes presentation resources."""
import subprocess
import sys
import datetime
import time

import pytest
pytest.importorskip('star_rust_runtime')
from rotk_env.rendering import register_renderer
from rotk_env.rendering.adapters import ProjectionRenderer
from rotk_env.runtime.session import NativeSession


@pytest.fixture
def frozen(monkeypatch):
    # Keep this gate runnable without importing desktop oracle test fixtures.
    monkeypatch.setattr(time, 'time', lambda: 1720000000.0)
    class Frozen(datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 9, 12, 12)
    monkeypatch.setattr(datetime, 'datetime', Frozen)


def test_framework_contracts_do_not_import_pygame():
    code = 'import sys, framework.presentation; assert "pygame" not in sys.modules'
    subprocess.run([sys.executable, '-c', code], check=True)


def test_web_uses_interactive_optimizations_and_animation_without_pygame():
    code = '''
import importlib.abc, sys
class BlockPygame(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, *args):
        if fullname == 'pygame' or fullname.startswith('pygame.'):
            raise AssertionError('Web must not import ' + fullname)
sys.meta_path.insert(0, BlockPygame())
from rotk_env.runtime.session import NativeSession
with NativeSession(renderer='web', scenario='chibi-small', seed=42) as s:
    assert 'pygame' not in sys.modules
    assert not s.world.systems
    state = s.runtime.export_state()
    assert state['display'] == 'window'  # API18's legacy simulation profile label.
    for name in ('VisionSystem', 'StatisticsSystem'):
        assert state['systems'][name]['window'] and state['systems'][name]['indexed']
    assert 'AnimationSystem' in state['systems']
    uid = s.renderer.model.snapshot('wei')['units'][0]['id']
    result = s.controls.execute('move', unit_id=int(uid), position=(0, 3))
    assert result['success']
    assert s.renderer.model.units[uid]['movement']['is_moving']
    s.step(1)
    assert s.renderer.model.units[uid]['position'] == {'col': 0, 'row': 3}
assert 'pygame' not in sys.modules
'''
    subprocess.run([sys.executable, '-c', code], check=True)


@pytest.mark.parametrize('threaded', [False, True])
def test_custom_adapter_receives_publications_and_cannot_advance_rules(threaded, frozen, monkeypatch):
    import rotk_env.rendering as registry
    monkeypatch.setattr(registry, '_FACTORIES', dict(registry._FACTORIES))
    class Recorder(ProjectionRenderer):
        renderer_id = 'test'; visual_version = 'test-v1'
        def __init__(self, **context):
            super().__init__(**context); self.revisions = []; self.cleaned = False
        def apply(self, delta):
            self.revisions.append(delta['revision']); return super().apply(delta)
        def close(self): self.cleaned = True
    register_renderer('test', Recorder)
    with NativeSession(renderer='test', authority_scheduling=threaded, scenario='chibi-small', seed=42) as scene:
        adapter = scene.renderer
        assert len(adapter.revisions) >= 1
        scene.step(.1)
        before = scene.runtime.export_state()
        scene.update_display(10)
        assert scene.runtime.export_state() == before
        assert adapter.revisions == sorted(adapter.revisions)
        assert scene.frame_provider.renderer_id == 'test'
    assert adapter.cleaned and not scene.world.entities


def test_failed_renderer_cleanup_still_releases_native_world(frozen):
    scene = NativeSession(scenario='chibi-small', seed=42)
    def fail(): raise RuntimeError('injected renderer cleanup')
    scene.renderer.close = fail
    with pytest.raises(RuntimeError, match='injected'): scene.close()
    assert not scene.world.entities
    with pytest.raises(RuntimeError, match='closed'): scene.runtime.export_state()


def test_default_adapter_and_web_do_not_change_rules_or_native_schema(frozen):
    states = []
    for renderer in ('none', 'web'):
        with NativeSession(renderer=renderer, simulation_profile='interactive', scenario='chibi-small', seed=42) as s:
            for dt in (.1, .25, 0): s.step(dt)
            states.append(s.runtime.export_state())
    assert states[0] == states[1]
    assert states[0]['schema'] == 5


def test_window_authority_preparation_does_not_import_any_renderer():
    code = '''
import importlib.abc, sys
class RejectRenderer(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, *args):
        if fullname == 'pygame' or fullname.startswith(('pygame.', 'rotk_env.ui.',
            'rotk_env.rendering.pygame', 'rotk_env.rendering.web', 'framework.engine.renders')):
            raise AssertionError('Authority preparation imported ' + fullname)
sys.meta_path.insert(0, RejectRenderer())
from rotk_env.runtime.bootstrap import prepare_display_world
from rotk_env.components import UIButton, Camera
world, initial = prepare_display_world(display='window', scenario='chibi-small', seed=42)
try:
    assert initial['display'] == 'window'
    assert world.systems == []
    assert world.get_singleton_component(Camera) is None
    assert not world.query().with_component(UIButton).entities()
    assert initial['entity_counter'] == 237
    assert 'pygame' not in sys.modules
finally:
    world.reset()
'''
    subprocess.run([sys.executable, '-c', code], check=True)


def test_authority_export_rejects_rule_components_on_local_entities(frozen):
    from rotk_env.components import UIButton, HexPosition
    from rotk_env.runtime.bootstrap import export_initial_state, prepare_display_world
    world, _ = prepare_display_world(scenario='chibi-small', seed=42)
    try:
        uid = world.create_local_entity()
        world.add_component(uid, UIButton(x=0, y=0, width=10, height=10, text='Test'))
        assert all(row['id'] >= 0 for row in export_initial_state(world)['entities'])
        world.add_component(uid, HexPosition(0, 0))
        with pytest.raises(ValueError, match='authoritative components'):
            export_initial_state(world)
    finally:
        world.reset()
