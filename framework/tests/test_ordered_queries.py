"""The migration oracle orders effects without changing the set query API."""

from dataclasses import dataclass

from framework import Component, World
from framework.engine.events import EventBus, Event


@dataclass
class Position(Component):
    x: int = 0


@dataclass
class Health(Component):
    hp: int = 10


def test_ordered_query_reuses_immutable_membership_until_invalidation():
    world = World()
    entities = [world.create_entity() for _ in range(8)]
    for entity in reversed(entities):
        world.add_component(entity, Position())
    query = world.query().with_component(Position)
    ordered = query.ordered_entities()
    assert isinstance(query.entities(), set)
    assert ordered == tuple(entities)
    assert world.query().with_component(Position).ordered_entities() is ordered
    world.get_component(entities[0], Position).x = 9
    world.add_component(entities[0], Health())
    assert query.ordered_entities() is ordered
    world.remove_component(entities[3], Position)
    assert query.ordered_entities() == tuple(e for e in entities if e != entities[3])
    world.destroy_entity(entities[4])
    assert entities[4] not in query.ordered_entities()
    world.clear_cache()
    assert not world._ordered_query_cache
    assert query.ordered_entities() == tuple(e for e in entities if e not in entities[3:5])
    world.reset()
    assert query.ordered_entities() == ()


def test_ordered_empty_exclusions_first_and_callback_order():
    world = World()
    query = world.query().with_component(Position).without_component(Health)
    assert query.ordered_entities() == ()
    ids = [world.create_entity() for _ in range(4)]
    for entity in reversed(ids):
        world.add_component(entity, Position())
    world.add_component(ids[0], Health())
    assert query.first() == ids[1]
    seen = []
    query.for_each(seen.append)
    assert seen == ids[1:]
    key = query._generate_cache_key()
    world._drop_cache_entry(key)
    assert key not in world._ordered_query_cache


def test_ordered_population_queries_track_empty_entity_lifecycles():
    world = World()
    all_query = world.query()
    excluded = world.query().without_component(Position)
    assert all_query.ordered_entities() == excluded.ordered_entities() == ()
    entity = world.create_entity()
    assert all_query.ordered_entities() == excluded.ordered_entities() == (entity,)
    world.add_component(entity, Position())
    assert excluded.ordered_entities() == ()
    assert all_query.ordered_entities() == (entity,)
    world.destroy_entity(entity)
    assert all_query.ordered_entities() == ()


def test_synchronous_events_keep_subscription_and_nested_publish_order():
    class Outer(Event):
        pass

    class Inner(Event):
        pass

    bus = EventBus()
    previous = bus._listeners
    bus._listeners = {}
    seen = []
    try:
        def first(event):
            seen.append('outer:first')
            bus.publish(Inner())
        bus.subscribe(Outer, first)
        bus.subscribe(Outer, lambda event: seen.append('outer:second'))
        bus.subscribe(Inner, lambda event: seen.append('inner'))
        bus.publish(Outer())
        assert seen == ['outer:first', 'inner', 'outer:second']
    finally:
        bus._listeners = previous
