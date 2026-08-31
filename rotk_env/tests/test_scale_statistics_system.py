"""Regression coverage for window-only amortized statistics sampling."""

from framework.ecs.world import World

from rotk_env.components import GameStats, HexPosition, Unit, UnitCount
from rotk_env.prefabs.config import Faction, UnitType
from rotk_env.systems.scale_statistics_system import StatisticsSystem


def _world_with_units(count: int, batch_size: int = 2):
    world = World()
    system = StatisticsSystem(batch_size=batch_size)
    system.observation_interval = 0.0
    world.add_system(system)

    for index in range(count):
        entity = world.create_entity()
        world.add_component(
            entity,
            Unit(unit_type=UnitType.INFANTRY, faction=Faction.WEI),
        )
        world.add_component(entity, UnitCount(current_count=100, max_count=100))
        world.add_component(entity, HexPosition(index, 0))

    return world, system


def test_observation_sampling_is_limited_to_one_batch_per_frame():
    world, _system = _world_with_units(5, batch_size=2)
    stats = world.get_singleton_component(GameStats)

    world.update(0.0)
    assert len(stats.unit_observation_history) == 2

    world.update(0.0)
    assert len(stats.unit_observation_history) == 4

    world.update(0.0)
    assert len(stats.unit_observation_history) == 5


def test_cycle_advances_without_restarting_while_work_is_pending():
    world, system = _world_with_units(5, batch_size=2)

    world.update(0.0)
    first_cycle = system._cycle
    assert first_cycle is not None
    assert first_cycle["phase"] == "observations"

    world.update(0.0)
    assert system._cycle is first_cycle

    world.update(0.0)
    assert system._cycle is first_cycle
    assert system._cycle["phase"] == "visibility"
