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
    return scene


def test_start_scene_none_matches_cli_without_mock_or_hub():
    scene = _scene(CONTROLLER_NONE)
    scene._start_game()

    _, kwargs = scene.engine.scene_manager.calls[-1]
    assert kwargs["enable_mock_ai"] is False
    assert kwargs["hub_url"] is None


def test_start_scene_local_bot_is_explicit_and_offline():
    scene = _scene(CONTROLLER_MOCK_AI)
    scene._start_game()

    _, kwargs = scene.engine.scene_manager.calls[-1]
    assert kwargs["enable_mock_ai"] is True
    assert kwargs["hub_url"] is None


def test_start_scene_hub_backend_does_not_enable_local_bot():
    scene = _scene(CONTROLLER_HUB)
    scene._start_game()

    _, kwargs = scene.engine.scene_manager.calls[-1]
    assert kwargs["enable_mock_ai"] is False
    assert kwargs["hub_url"] == DEFAULT_HUB_URL
