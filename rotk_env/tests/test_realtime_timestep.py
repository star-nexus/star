"""Realtime recovery follows GameTime board seconds, not engine delta_time."""

import pytest

from framework.ecs.world import World
from rotk_env.components import ActionPoints, GameStats, GameTime, GameModeComponent
from rotk_env.prefabs.config import GameConfig, GameMode
from rotk_env.systems.game_time_system import GameTimeSystem
from rotk_env.systems.resource_recovery_system import ResourceRecoverySystem
from rotk_env.systems.statistics_system import StatisticsSystem


def _realtime_world():
    world = World()
    world.add_singleton_component(GameModeComponent(mode=GameMode.REAL_TIME))
    world.add_system(GameTimeSystem())
    world.add_system(ResourceRecoverySystem())
    entity = world.create_entity()
    world.add_component(entity, ActionPoints(current_ap=0, max_ap=2))
    return world, entity


def test_eval_fps_is_sixty():
    assert GameConfig.FPS == 60


def test_realtime_ap_recovers_one_per_sixty_frames():
    world, entity = _realtime_world()
    dt = 1.0 / GameConfig.FPS
    for _ in range(GameConfig.FPS - 1):
        world.update(dt)
    assert world.get_component(entity, ActionPoints).current_ap == 0

    world.update(dt)
    assert world.get_component(entity, ActionPoints).current_ap == 1
    assert world.get_singleton_component(GameTime).game_elapsed_time == pytest.approx(
        1.0, abs=1e-9
    )


def test_recovery_reads_game_time_ledger_not_the_update_argument():
    """Fault injection: omit GameTimeSystem so world.update(dt) never
    reaches the board clock. dt and 棋盘秒 are the same scale; this only
    proves recovery has no private copy of the increment."""
    world = World()
    game_time = GameTime()
    game_time.current_mode = GameMode.REAL_TIME
    world.add_singleton_component(game_time)
    world.add_system(ResourceRecoverySystem())

    entity = world.create_entity()
    world.add_component(entity, ActionPoints(current_ap=0, max_ap=2))

    world.update(10.0)
    assert world.get_component(entity, ActionPoints).current_ap == 0
    assert game_time.game_elapsed_time == 0.0

    game_time.game_elapsed_time = 1.0
    world.update(0.0)
    assert world.get_component(entity, ActionPoints).current_ap == 1


def test_paused_game_time_does_not_recover_ap():
    world, entity = _realtime_world()
    game_time = world.get_singleton_component(GameTime)
    dt = 1.0 / GameConfig.FPS

    game_time.pause()
    for _ in range(GameConfig.FPS):
        world.update(dt)
    assert world.get_component(entity, ActionPoints).current_ap == 0
    assert game_time.game_elapsed_time == 0.0

    game_time.resume()
    for _ in range(GameConfig.FPS):
        world.update(dt)
    assert world.get_component(entity, ActionPoints).current_ap == 1
    assert game_time.game_elapsed_time == pytest.approx(1.0, abs=1e-9)


def test_time_scale_speeds_ap_recovery_with_game_clock():
    world, entity = _realtime_world()
    game_time = world.get_singleton_component(GameTime)
    game_time.set_time_scale(2.0)
    dt = 1.0 / GameConfig.FPS

    # 20 frames at 2x ≈ 0.67 board seconds: still short of 1 AP.
    for _ in range(20):
        world.update(dt)
    assert world.get_component(entity, ActionPoints).current_ap == 0

    # 40 frames at 2x ≈ 1.33 board seconds: one AP, matching the HUD clock.
    for _ in range(20):
        world.update(dt)
    assert world.get_component(entity, ActionPoints).current_ap == 1
    assert game_time.game_elapsed_time == pytest.approx(40 * dt * 2.0, abs=1e-9)


def test_statistics_realtime_clock_mirrors_game_time():
    world, _entity = _realtime_world()
    world.add_system(StatisticsSystem())
    dt = 1.0 / GameConfig.FPS

    for _ in range(GameConfig.FPS):
        world.update(dt)

    game_time = world.get_singleton_component(GameTime)
    stats = world.get_singleton_component(GameStats)
    assert stats.total_game_time == pytest.approx(game_time.game_elapsed_time, abs=1e-9)

    game_time.pause()
    paused_at = stats.total_game_time
    for _ in range(GameConfig.FPS):
        world.update(dt)
    assert world.get_singleton_component(GameStats).total_game_time == pytest.approx(
        paused_at, abs=1e-9
    )
