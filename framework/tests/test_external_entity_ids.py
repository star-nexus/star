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
