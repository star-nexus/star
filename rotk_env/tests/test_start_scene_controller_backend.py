from types import SimpleNamespace

from rotk_env.components.start_menu import (
    CONTROLLER_HUB,
    CONTROLLER_MOCK_AI,
    CONTROLLER_NONE,
    StartMenuConfig,
)
from rotk_env.prefabs.config import Faction, PlayerType
from rotk_env.prefabs.world_builder import DEFAULT_HUB_URL
from rotk_env.scenes.start_scene import StartScene


class _World:
    def __init__(self, config):
        self.config = config

    def get_singleton_component(self, component_type):
        if component_type is StartMenuConfig:
            return self.config
        return None


class _SceneManager:
    def __init__(self):
        self.calls = []

    def switch_to(self, name, **kwargs):
        self.calls.append((name, kwargs))


def _scene(backend):
    config = StartMenuConfig()
    config.selected_players = {
        Faction.WEI: PlayerType.HUMAN,
        Faction.SHU: PlayerType.AI,
        Faction.WU: PlayerType.AI,
    }
    config.selected_controller_backend = backend

    scene = StartScene.__new__(StartScene)
    scene.world = _World(config)
    scene.engine = SimpleNamespace(scene_manager=_SceneManager())
    scene.game_config = None
    scene._pending_game_config = None
    return scene


def _queue_and_flush(backend):
    scene = _scene(backend)
    scene._start_game()

    # Menu clicks only queue. GameScene construction happens later from the
    # StartScene update phase, never from inside MouseButtonDown dispatch.
    assert scene.engine.scene_manager.calls == []
    assert scene._pending_game_config is not None
    assert scene._flush_pending_game_start() is True
    assert scene._pending_game_config is None
    assert scene._flush_pending_game_start() is False
    return scene.engine.scene_manager.calls[-1]


def test_start_scene_none_matches_cli_without_mock_or_hub():
    _, kwargs = _queue_and_flush(CONTROLLER_NONE)
    assert kwargs["enable_mock_ai"] is False
    assert kwargs["hub_url"] is None


def test_start_scene_local_bot_is_explicit_and_offline():
    _, kwargs = _queue_and_flush(CONTROLLER_MOCK_AI)
    assert kwargs["enable_mock_ai"] is True
    assert kwargs["hub_url"] is None


def test_start_scene_hub_backend_does_not_enable_local_bot():
    _, kwargs = _queue_and_flush(CONTROLLER_HUB)
    assert kwargs["enable_mock_ai"] is False
    assert kwargs["hub_url"] == DEFAULT_HUB_URL


def test_explicit_auto_start_config_uses_same_pending_handoff():
    scene = _scene(CONTROLLER_NONE)
    cli_config = {
        "mode": "real_time",
        "players": {
            Faction.WEI: PlayerType.HUMAN,
            Faction.SHU: PlayerType.AI,
            Faction.WU: PlayerType.AI,
        },
        "scenario": "TestMap-2K-scale-1000",
        "hub_url": None,
        "enable_mock_ai": False,
        "seed": 42,
        "seed_source": "cli",
    }

    scene._queue_game_start(cli_config)
    assert scene.engine.scene_manager.calls == []
    assert scene._flush_pending_game_start() is True

    name, kwargs = scene.engine.scene_manager.calls[-1]
    assert name == "game"
    assert kwargs == cli_config
