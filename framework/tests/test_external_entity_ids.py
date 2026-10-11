"""Stable external IDs for derived presentation worlds."""

import pytest
from framework import World
from dataclasses import dataclass
from framework import Component


@dataclass
class Point(Component):
    col: int
    row: int


def test_adopt_external_ids_keeps_query_indexes_and_allocator_correct():
    world = World()
    try:
        assert world.query().entities() == set()
        world.ensure_entity(500)
        assert world.query().entities() == {500}
        point = Point(1, 2)
        world.add_component(500, point)
        assert world.query().with_all(Point).ordered_entities() == (500,)
        world.ensure_entity(3)
        world.ensure_entity(500)
        assert world.get_component(500, Point) is point
        assert world.create_entity() == 501
        world.destroy_entity(500)
        assert world.query().with_all(Point).entities() == set()
        world.ensure_entity(500)
        assert world.query().entities() == {3, 500, 501}
        assert world.create_entity() == 502
        for invalid in (-1, True, "9", 1.5):
            with pytest.raises(ValueError):
                world.ensure_entity(invalid)
    finally:
        world.reset()


def test_local_entities_cannot_consume_or_collide_with_external_ids():
    world = World()
    try:
        world.ensure_entity(236)
        assert world.query().entities() == {236}
        first = world.create_local_entity()
        assert first == -1 and world.entity_counter == 237
        assert world.query().entities() == {-1, 236}
        point = Point(1, 2)
        world.add_component(first, point)
        # A future native entity or visual may use the very next authority ID.
        assert world.ensure_entity(237) == 237
        assert world.get_component(first, Point) is point
        assert world.create_local_entity() == -2
        assert world.create_entity() == 238
        assert world.query().with_component(Point).ordered_entities() == (-1,)
        world.destroy_entity(first)
        assert world.query().with_component(Point).entities() == set()
        assert world.create_local_entity() == -3
        world.reset()
        assert world.create_entity() == 0 and world.create_local_entity() == -1
    finally:
        world.reset()
