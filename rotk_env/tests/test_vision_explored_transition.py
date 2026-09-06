from framework.ecs.world import World

from rotk_env.components import FogOfWar, HexPosition, Unit, Vision
from rotk_env.prefabs.config import Faction, UnitType
from rotk_env.systems.vision_system import VisionSystem, mark_vision_dirty


class _CountingSet(set):
    def __init__(self, values=()):
        super().__init__(values)
        self.add_calls = 0
        self.update_calls = 0

    def add(self, value):
        self.add_calls += 1
        return super().add(value)

    def update(self, *others):
        self.update_calls += 1
        return super().update(*others)


def _spawn(world, *, faction=Faction.WEI, col=0, row=0, vision_range=1):
    entity = world.create_entity()
    world.add_component(
        entity,
        Unit(unit_type=UnitType.INFANTRY, faction=faction, name=str(entity)),
    )
    world.add_component(entity, HexPosition(col, row))
    world.add_component(entity, Vision(range=vision_range))
    return entity


def _system(world):
    fog = FogOfWar(enabled=True)
    world.add_singleton_component(fog)
    system = VisionSystem()
    system.initialize(world)
    return system, fog


def test_explored_is_not_touched_for_shared_refcount_increment():
    world = World()
    system, fog = _system(world)
    faction = Faction.WEI
    shared = (0, 0)
    newly_visible = (1, 0)

    system._faction_tile_counts[faction] = {shared: 1}
    fog.faction_vision[faction] = {shared}
    explored = _CountingSet({shared})
    fog.explored_tiles[faction] = explored

    added, union_added = system._add_tiles(fog, faction, {shared})

    assert (added, union_added) == (1, 0)
    assert system._faction_tile_counts[faction][shared] == 2
    assert explored.add_calls == 0
    assert explored.update_calls == 0

    added, union_added = system._add_tiles(fog, faction, {newly_visible})

    assert (added, union_added) == (1, 1)
    assert newly_visible in fog.faction_vision[faction]
    assert newly_visible in explored
    assert explored.add_calls == 1
    assert explored.update_calls == 0


def test_bootstrap_exploration_matches_initial_faction_visibility():
    world = World()
    _spawn(world, col=0, row=0, vision_range=1)
    _spawn(world, col=0, row=0, vision_range=1)
    system, fog = _system(world)

    system.update(0.0)

    assert fog.faction_vision[Faction.WEI]
    assert fog.explored_tiles[Faction.WEI] == fog.faction_vision[Faction.WEI]


def test_explored_history_survives_leave_and_reentry():
    world = World()
    mover = _spawn(world, col=0, row=0, vision_range=1)
    system, fog = _system(world)

    system.update(0.0)
    first_visibility = set(fog.faction_vision[Faction.WEI])

    pos = world.get_component(mover, HexPosition)
    pos.col, pos.row = 5, 0
    mark_vision_dirty(world, mover)
    system.update(0.0)
    second_visibility = set(fog.faction_vision[Faction.WEI])

    assert first_visibility <= fog.explored_tiles[Faction.WEI]
    assert second_visibility <= fog.explored_tiles[Faction.WEI]

    pos.col, pos.row = 0, 0
    mark_vision_dirty(world, mover)
    system.update(0.0)

    assert fog.faction_vision[Faction.WEI] == first_visibility
    assert first_visibility | second_visibility <= fog.explored_tiles[Faction.WEI]
