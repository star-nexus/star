from __future__ import annotations

from rotk_env.components import HexPosition
from rotk_env.systems.window_unit_render_system import UnitRenderSystem


class _FakeWorld:
    def __init__(self):
        self.positions = {
            1: HexPosition(0, 0),
            2: HexPosition(1, 0),
        }
        self.systems = []

    def get_component(self, entity, component_type):
        if component_type is HexPosition:
            return self.positions.get(entity)
        return None


class _FakeHexConverter:
    @staticmethod
    def hex_to_pixel(col, row):
        return (col * 100.0, row * 100.0)


class _FakeAnimationSystem:
    @staticmethod
    def get_unit_render_position(entity):
        if entity == 1:
            # Halfway between committed hex centres (0,0) and (1,0).
            return (50.0, 0.0)
        return (100.0, 0.0)


class _TinyAnimationSystem:
    @staticmethod
    def get_unit_render_position(entity):
        if entity == 1:
            # Deliberately below the old 1px/5px dead zones.
            return (0.5, 0.0)
        return (100.0, 0.0)


def _renderer():
    renderer = UnitRenderSystem.__new__(UnitRenderSystem)
    renderer.world = _FakeWorld()
    renderer.hex_converter = _FakeHexConverter()
    return renderer


def test_batch_renderer_peels_animated_units_out_of_static_hex_groups():
    renderer = _renderer()
    renderer._get_animation_system = lambda: _FakeAnimationSystem()

    static_groups = []
    animated_draws = []
    renderer._render_unit_group_optimized = (
        lambda pos_key, units, camera_offset, zoom: static_groups.append(
            (pos_key, list(units))
        )
    )
    renderer._render_single_unit_fast = (
        lambda entity, screen_x, screen_y, zoom: animated_draws.append(
            (entity, screen_x, screen_y, zoom)
        )
    )

    renderer._render_units_batch([1, 2], [10.0, 20.0], 2.0)

    # Entity 1 must use the interpolated render position:
    # (50 world px * 2 zoom) + camera offset = (110, 20).
    assert animated_draws == [(1, 110.0, 20.0, 2.0)]

    # Entity 2 is static and remains in the cheap grouped fast path. Most
    # importantly, entity 1 is not drawn a second time at its committed hex.
    assert static_groups == [((1, 0), [2])]


def test_animation_position_has_no_subpixel_dead_zone():
    renderer = _renderer()

    # A real 0.5-world-pixel displacement is still animation, not a static
    # committed-hex position. At zoom 2 with offset (10,20), it becomes (11,20).
    assert renderer._animation_screen_position(
        1,
        _TinyAnimationSystem(),
        [10.0, 20.0],
        2.0,
    ) == (11.0, 20.0)

    # A truly static entity still stays on the static grouped path.
    assert (
        renderer._animation_screen_position(
            2,
            _TinyAnimationSystem(),
            [10.0, 20.0],
            2.0,
        )
        is None
    )
