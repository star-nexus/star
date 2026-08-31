from framework.ecs.world import World

from rotk_env.components import FogOfWar, HexPosition, MapData, Unit, Vision
from rotk_env.prefabs.config import Faction, UnitType
from rotk_env.systems.scale_vision_system import VisionSystem


def _unit(world, faction, pos):
    entity = world.create_entity()
    world.add_component(
        entity,
        Unit(unit_type=UnitType.INFANTRY, faction=faction, name=str(entity)),
    )
    world.add_component(entity, HexPosition(*pos))
    world.add_component(entity, Vision(range=2))
    return entity


def test_incremental_aggregate_preserves_overlap_and_updates_only_moved_unit(monkeypatch):
    world = World()
    world.add_singleton_component(FogOfWar())
    map_data = MapData(width=5, height=5)
    for tile in {(0, 0), (1, 0), (2, 0), (3, 0)}:
        map_data.tiles[tile] = world.create_entity()
    world.add_singleton_component(map_data)

    first = _unit(world, Faction.WEI, (1, 0))
    second = _unit(world, Faction.WEI, (2, 0))

    system = VisionSystem()
    calls = []

    def fake_vision(center, _range, _entity):
        calls.append(center)
        return {(0, 0), center}

    monkeypatch.setattr(system, "_calculate_vision", fake_vision)
    world.add_system(system)

    world.update(0.0)
    fog = world.get_singleton_component(FogOfWar)
    assert fog.faction_vision[Faction.WEI] == {(0, 0), (1, 0), (2, 0)}
    assert calls == [(1, 0), (2, 0)]

    calls.clear()
    world.update(0.0)
    assert calls == []
    assert fog.faction_vision[Faction.WEI] == {(0, 0), (1, 0), (2, 0)}

    position = world.get_component(first, HexPosition)
    position.col = 3
    calls.clear()
    world.update(0.0)
    assert calls == [(3, 0)]
    # The shared (0,0) tile remains visible through the second unit while the
    # first unit's old unique tile disappears.
    assert fog.faction_vision[Faction.WEI] == {(0, 0), (2, 0), (3, 0)}


def test_fog_disabled_publishes_whole_map_once_and_rebuilds_on_enable(monkeypatch):
    world = World()
    fog = FogOfWar()
    world.add_singleton_component(fog)
    map_data = MapData(width=3, height=1)
    for tile in {(0, 0), (1, 0), (2, 0)}:
        map_data.tiles[tile] = world.create_entity()
    world.add_singleton_component(map_data)

    entity = _unit(world, Faction.WEI, (0, 0))
    system = VisionSystem()
    calls = []

    def fake_vision(center, _range, _entity):
        calls.append(center)
        return {center}

    monkeypatch.setattr(system, "_calculate_vision", fake_vision)
    world.add_system(system)
    world.update(0.0)
    assert fog.faction_vision[Faction.WEI] == {(0, 0)}

    fog.enabled = False
    world.update(0.0)
    assert fog.faction_vision[Faction.WEI] == {(0, 0), (1, 0), (2, 0)}

    world.get_component(entity, HexPosition).col = 2
    calls.clear()
    world.update(0.0)
    assert calls == []
    assert fog.faction_vision[Faction.WEI] == {(0, 0), (1, 0), (2, 0)}

    fog.enabled = True
    world.update(0.0)
    assert calls == [(2, 0)]
    assert fog.faction_vision[Faction.WEI] == {(2, 0)}
