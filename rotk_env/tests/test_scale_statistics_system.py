"""Regression coverage for window-only amortized statistics sampling."""

from framework.ecs.world import World

from rotk_env.components import (
    FogOfWar,
    GameStats,
    HexPosition,
    Unit,
    UnitCount,
    UnitObservation,
    VisibilityTracker,
)
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


def _run_one_unit_statistics_cycle(world: World) -> None:
    """One unit with batch>=1 takes observation, visibility, faction frames."""
    world.update(0.0)
    world.update(0.0)
    world.update(0.0)


def _only_unit(world: World) -> int:
    """Return the single unit entity from this test fixture.

    ECS query ``entities()`` intentionally returns a set, so make the iterator
    conversion explicit instead of assuming iterator semantics.
    """
    return next(iter(world.query().with_all(Unit, HexPosition).entities()))


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


def test_visibility_history_records_baseline_then_only_real_changes():
    world, system = _world_with_units(1, batch_size=2)
    entity = _only_unit(world)
    fog = FogOfWar(
        faction_vision={Faction.WEI: {(0, 0)}, Faction.SHU: set()},
        explored_tiles={Faction.WEI: {(0, 0)}, Faction.SHU: set()},
        enabled=True,
    )
    world.add_singleton_component(fog)

    _run_one_unit_statistics_cycle(world)
    tracker = world.get_singleton_component(VisibilityTracker)
    observation = world.get_component(entity, UnitObservation)
    history = tracker.visibility_history[entity]

    assert observation.is_visible_to == {Faction.WEI}
    assert len(history) == 1
    assert history[0]["newly_spotted"] is False
    assert history[0]["lost_sight"] is False

    # An unchanged one-second sample updates live state without allocating a
    # duplicate visibility-history record.
    _run_one_unit_statistics_cycle(world)
    assert tracker.visibility_history[entity] is history
    assert len(history) == 1

    fog.faction_vision[Faction.SHU].add((0, 0))
    _run_one_unit_statistics_cycle(world)
    assert observation.is_visible_to == {Faction.WEI, Faction.SHU}
    assert len(history) == 2
    assert history[-1]["newly_spotted"] is True
    assert history[-1]["lost_sight"] is False


def test_visibility_history_is_bounded_in_place_on_changes():
    world, system = _world_with_units(1, batch_size=2)
    system.VISIBILITY_HISTORY_LIMIT = 2
    entity = _only_unit(world)
    fog = FogOfWar(
        faction_vision={Faction.WEI: {(0, 0)}, Faction.SHU: set()},
        explored_tiles={Faction.WEI: {(0, 0)}, Faction.SHU: set()},
        enabled=True,
    )
    world.add_singleton_component(fog)

    _run_one_unit_statistics_cycle(world)
    tracker = world.get_singleton_component(VisibilityTracker)
    history = tracker.visibility_history[entity]

    fog.faction_vision[Faction.SHU].add((0, 0))
    _run_one_unit_statistics_cycle(world)
    fog.faction_vision[Faction.SHU].clear()
    _run_one_unit_statistics_cycle(world)

    assert tracker.visibility_history[entity] is history
    assert len(history) == 2
    assert history[-1]["newly_spotted"] is False
    assert history[-1]["lost_sight"] is True


def test_fog_disabled_reuses_all_visible_relation_without_duplicate_history():
    world, _system = _world_with_units(1, batch_size=2)
    entity = _only_unit(world)
    fog = FogOfWar(
        faction_vision={
            Faction.WEI: set(),
            Faction.SHU: set(),
            Faction.WU: set(),
        },
        explored_tiles={},
        enabled=False,
    )
    world.add_singleton_component(fog)

    _run_one_unit_statistics_cycle(world)
    tracker = world.get_singleton_component(VisibilityTracker)
    observation = world.get_component(entity, UnitObservation)
    history = tracker.visibility_history[entity]

    assert observation.is_visible_to == {Faction.WEI, Faction.SHU, Faction.WU}
    for faction in (Faction.WEI, Faction.SHU, Faction.WU):
        assert entity in tracker.faction_visible_units[faction]
    assert len(history) == 1

    _run_one_unit_statistics_cycle(world)
    assert tracker.visibility_history[entity] is history
    assert len(history) == 1
