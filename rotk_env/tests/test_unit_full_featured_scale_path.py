from __future__ import annotations

from types import SimpleNamespace

from rotk_env.components import HexPosition, Unit, UnitCount
from rotk_env.prefabs.config import Faction, UnitType
from rotk_env.systems import optimized_render_systems_base as optimized


class _Query:
    def __init__(self, entities):
        self._entities = entities

    def with_all(self, *component_types):
        return self

    def entities(self):
        return list(self._entities)


class _World:
    def __init__(self):
        self.positions = {
            1: SimpleNamespace(col=2, row=3),
            2: SimpleNamespace(col=2, row=3),
            3: SimpleNamespace(col=5, row=7),
        }
        self.units = {
            1: SimpleNamespace(faction=Faction.WEI),
            2: SimpleNamespace(faction=Faction.WEI),
            3: SimpleNamespace(faction=Faction.SHU),
        }
        self.counts = {entity: object() for entity in self.positions}

    def query(self):
        return _Query(self.positions)

    @staticmethod
    def get_singleton_component(component_type):
        return None

    def get_component(self, entity, component_type):
        if component_type is HexPosition:
            return self.positions.get(entity)
        if component_type is Unit:
            return self.units.get(entity)
        if component_type is UnitCount:
            return self.counts.get(entity)
        return None


class _Rect:
    def __init__(self, center):
        self.center = center


class _Surface:
    def __init__(self, token):
        self.token = token

    def get_rect(self, *, center):
        return _Rect(center)


class _Font:
    def __init__(self):
        self.render_calls = []

    def render(self, text, antialias, color):
        self.render_calls.append((text, antialias, color))
        return _Surface((text, color))


def test_full_featured_occupancy_snapshot_replaces_per_unit_world_scan():
    renderer = optimized.UnitRenderSystem.__new__(optimized.UnitRenderSystem)
    renderer.world = _World()
    renderer._full_featured_occupancy_index = None

    snapshot = renderer._build_full_featured_occupancy_snapshot()
    renderer._full_featured_occupancy_index = snapshot

    assert snapshot[(2, 3)] == [1, 2]
    assert snapshot[(5, 7)] == [3]
    assert renderer._get_units_in_same_hex(1) == [1, 2]
    assert renderer._get_units_in_same_hex(3) == [3]


def test_unit_labels_use_prewarmed_quantized_surfaces_without_runtime_render(monkeypatch):
    renderer = optimized.UnitRenderSystem.__new__(optimized.UnitRenderSystem)
    renderer._unit_label_surface_cache = {}

    font = _Font()
    renderer._get_font = lambda size: font
    renderer._prewarm_unit_label_surfaces()

    expected_variants = (
        len(renderer.UNIT_LABEL_FONT_SIZES)
        * len(list(Faction))
        * len(renderer.UNIT_LABELS)
    )
    assert len(renderer._unit_label_surface_cache) == expected_variants
    assert len(font.render_calls) == expected_variants
    assert renderer._quantize_unit_label_font_size(33) == 34
    assert renderer._quantize_unit_label_font_size(29) == 28

    render_calls_before = len(font.render_calls)
    draws = []
    monkeypatch.setattr(
        optimized.RMS,
        "draw",
        lambda surface, rect: draws.append((surface, rect)),
    )

    unit = SimpleNamespace(unit_type=UnitType.INFANTRY, faction=Faction.WEI)
    renderer._render_unit_icon(100.0, 200.0, unit, zoom=3.0, scale=0.8)

    # 14 * 3.0 * 0.8 = 33.6 -> int 33 -> prewarmed bucket 34.
    assert len(font.render_calls) == render_calls_before
    assert draws and draws[0][1].center == (100, 200)
