"""Protect the explicit scale-only MiniMap unit-layer ablation."""

from __future__ import annotations

from rotk_env.components import MiniMap
from rotk_env.systems.window_minimap_system import (
    MiniMapSystem,
    _parse_minimap_units_override,
)


class _World:
    def __init__(self):
        self._singletons = {}

    def get_singleton_component(self, component_type):
        return self._singletons.get(component_type)

    def add_singleton_component(self, component):
        self._singletons[type(component)] = component


def test_minimap_units_override_parser_is_explicit():
    assert _parse_minimap_units_override(None) is None
    assert _parse_minimap_units_override("on") is True
    assert _parse_minimap_units_override("1") is True
    assert _parse_minimap_units_override("off") is False
    assert _parse_minimap_units_override("0") is False


def test_scale_ablation_disables_only_dynamic_unit_layer(monkeypatch):
    monkeypatch.setenv("STAR_SCALE_MINIMAP_UNITS", "off")
    world = _World()
    system = MiniMapSystem()

    system.initialize(world)

    minimap = world.get_singleton_component(MiniMap)
    assert minimap is not None
    assert minimap.visible is True
    assert minimap.show_units is False
    assert minimap.show_terrain is True
    assert minimap.show_camera_viewport is True
    assert minimap.clickable is True
