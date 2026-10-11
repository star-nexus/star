"""Renderer substitution preserves authority and closes presentation resources."""
import subprocess
import sys

import pytest
pytest.importorskip('star_native')
from rotk_env.rendering import register_renderer
from rotk_env.rendering.adapters import ProjectionRenderer
from rotk_env.runtime.session import NativeSession
from rotk_env.tests.test_native_request_batch import frozen


def test_framework_contracts_do_not_import_pygame():
    code = 'import sys, framework.presentation; assert "pygame" not in sys.modules'
    subprocess.run([sys.executable, '-c', code], check=True)


def test_web_uses_interactive_optimizations_and_animation_without_an_sdl_window():
    code = '''
import pygame
from rotk_env.runtime.session import NativeSession
with NativeSession(renderer='web', scenario='chibi-small', seed=42) as s:
    assert not pygame.display.get_init()
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
