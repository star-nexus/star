"""Fixed 60 FPS sim step: realtime AP recovers one point per 60 frames."""

from framework.ecs.world import World
from rotk_env.components import ActionPoints, GameTime
from rotk_env.prefabs.config import GameConfig, GameMode
from rotk_env.systems.resource_recovery_system import ResourceRecoverySystem


def test_eval_fps_is_sixty():
    assert GameConfig.FPS == 60


def test_realtime_ap_recovers_one_per_sixty_frames():
    world = World()
    game_time = GameTime()
    game_time.current_mode = GameMode.REAL_TIME
    world.add_singleton_component(game_time)
    world.add_system(ResourceRecoverySystem())

    entity = world.create_entity()
    world.add_component(entity, ActionPoints(current_ap=0, max_ap=2))

    dt = 1.0 / GameConfig.FPS
    for _ in range(GameConfig.FPS - 1):
        world.update(dt)
    assert world.get_component(entity, ActionPoints).current_ap == 0

    world.update(dt)
    assert world.get_component(entity, ActionPoints).current_ap == 1
