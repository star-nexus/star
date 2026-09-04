import pytest

from framework.ecs.world import World

from rotk_env.components import HexPosition, MovementAnimation
from rotk_env.systems.animation_system import AnimationSystem


def _movement_fixture(path):
    world = World()
    entity = world.create_entity()
    world.add_component(entity, HexPosition(col=path[0][0], row=path[0][1]))

    system = AnimationSystem()
    system.world = world
    system.start_unit_movement(entity, path)

    position = world.get_component(entity, HexPosition)
    animation = world.get_component(entity, MovementAnimation)
    assert position is not None
    assert animation is not None
    return system, entity, position, animation


def test_movement_crosses_exact_60hz_segment_on_tick_30():
    system, entity, position, animation = _movement_fixture(
        [(0, 0), (1, 0), (2, 0)]
    )

    for _ in range(30):
        system._update_movement_animations(1.0 / 60.0)

    assert (position.col, position.row) == (1, 0)
    assert animation.current_target_index == 1
    assert animation.progress == pytest.approx(0.0, abs=1e-12)

    boundary = system.hex_converter.hex_to_pixel(1, 0)
    assert system.get_unit_render_position(entity) == pytest.approx(boundary)

    system._update_movement_animations(1.0 / 60.0)
    assert animation.progress == pytest.approx(1.0 / 30.0)
    assert system.get_unit_render_position(entity) != pytest.approx(boundary)


def test_movement_preserves_segment_overshoot():
    system, entity, position, animation = _movement_fixture(
        [(0, 0), (1, 0), (2, 0)]
    )
    animation.progress = 0.98

    system._update_movement_animations(0.02)

    assert (position.col, position.row) == (1, 0)
    assert animation.current_target_index == 1
    assert animation.progress == pytest.approx(0.02)

    start_x, start_y = system.hex_converter.hex_to_pixel(1, 0)
    target_x, target_y = system.hex_converter.hex_to_pixel(2, 0)
    expected = (
        start_x + (target_x - start_x) * 0.02,
        start_y + (target_y - start_y) * 0.02,
    )
    assert system.get_unit_render_position(entity) == pytest.approx(expected)


def test_movement_consumes_large_delta_across_multiple_segments():
    system, _entity, position, animation = _movement_fixture(
        [(0, 0), (1, 0), (2, 0), (3, 0)]
    )

    system._update_movement_animations(1.2)

    assert (position.col, position.row) == (2, 0)
    assert animation.current_target_index == 2
    assert animation.progress == pytest.approx(0.4)
    assert animation.is_moving is True
