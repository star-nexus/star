from __future__ import annotations

from contextlib import nullcontext

import rotk_env.scenes.game_scene as game_scene_module
from framework.engine.scenes import SceneState
from rotk_env.scenes.game_scene import GameScene


class _FakeProfiler:
    enabled = True

    def __init__(self):
        self.reset_calls = 0

    def reset(self):
        self.reset_calls += 1

    def time_system(self, *args, **kwargs):
        return nullcontext()


class _FakeWorld:
    def __init__(self):
        self.update_calls = 0

    def update(self, delta_time):
        self.update_calls += 1

    def get_singleton_component(self, component_type):
        return None


def test_first_gameplay_update_consumes_deferred_profiler_warmup(monkeypatch):
    scene = GameScene(engine=None)
    scene.state = SceneState.ACTIVE
    scene.world = _FakeWorld()
    scene._profile_warmup_pending = True

    fake_profiler = _FakeProfiler()
    monkeypatch.setattr(game_scene_module, "profiler", fake_profiler)
    monkeypatch.setattr(
        game_scene_module.GameConfig, "sync_from_display", staticmethod(lambda: None)
    )

    scene.update(1 / 60)
    assert fake_profiler.reset_calls == 1
    assert scene._profile_warmup_pending is False
    assert scene.world.update_calls == 1

    # The guard is one-shot; later gameplay frames are retained normally.
    scene.update(1 / 60)
    assert fake_profiler.reset_calls == 1
    assert scene.world.update_calls == 2
