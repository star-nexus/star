from types import SimpleNamespace

from framework import World
from rotk_env.components import Unit, UnitCount, HexPosition
from rotk_env.prefabs.config import Faction, UnitType
from rotk_env.systems.ui_render_system import UIRenderSystem


def add(world,faction):
    e=world.create_entity()
    world.add_component(e,Unit(faction=faction,unit_type=UnitType.INFANTRY))
    return e


def reference(world):
    counts={}
    for e in world.query().with_component(Unit).entities():
        unit=world.get_component(e,Unit)
        if unit: counts[unit.faction]=counts.get(unit.faction,0)+1
    return list(counts.items())


def test_roster_matches_order_and_all_unit_semantics_through_lifecycle():
    world=World()
    renderer=UIRenderSystem.__new__(UIRenderSystem)
    renderer.initialize(world)
    a=add(world,Faction.WEI)
    b=add(world,Faction.SHU)
    c=add(world,Faction.WEI)
    # A Unit without position/count still belongs to this UI's original roster.
    world.add_component(c,UnitCount(current_count=0,max_count=10))
    def check():
        assert list(renderer._current_faction_counts().items())==reference(world)
    check(); check()
    # In-place faction updates must be visible with unchanged query membership.
    world.get_component(a,Unit).faction=Faction.WU
    check()
    # Replacing a component under the same entity ID must replace the reference.
    world.add_component(b,Unit(faction=Faction.WU,unit_type=UnitType.ARCHER))
    check()
    world.remove_component(c,Unit)
    check()
    world.destroy_entity(a)
    check()
    add(world,Faction.SHU)
    check()
    world.clear_cache()
    check()
    for entity in list(world.entities): world.destroy_entity(entity)
    check()
    assert renderer._faction_roster_units==()
    assert renderer._faction_roster_values==()


def test_unchanged_roster_reuses_components_but_observes_current_factions():
    world=World()
    for i in range(30): add(world,Faction.WEI if i%2 else Faction.SHU)
    renderer=UIRenderSystem.__new__(UIRenderSystem)
    renderer.initialize(world)
    renderer._current_faction_counts()
    renderer._current_faction_counts()  # first query result is copied into cache
    old=world.get_component
    world.get_component=lambda *args: (_ for _ in ()).throw(AssertionError('redundant entity lookup'))
    try:
        assert renderer._current_faction_counts()=={Faction.SHU:15,Faction.WEI:15}
    finally: world.get_component=old
    world.get_component(0,Unit).faction=Faction.WU
    assert renderer._current_faction_counts()[Faction.WU]==1


def test_world_reinitialization_drops_old_roster():
    world=World(); add(world,Faction.WEI)
    renderer=UIRenderSystem.__new__(UIRenderSystem)
    renderer.initialize(world); renderer._current_faction_counts()
    renderer.initialize(World())
    assert renderer._faction_roster_units==()
    assert renderer._current_faction_counts()=={}
