from types import SimpleNamespace

from framework.ecs.world import World

from rotk_env.components import FogOfWar, GameState, HexPosition, UIState, Unit, UnitCount
from rotk_env.prefabs.config import Faction, UnitType
import rotk_env.systems.scale_unit_render_system as scale_unit_render_system
from rotk_env.systems.scale_unit_render_system import UnitRenderSystem
from rotk_env.utils.unit_spatial_index import (
    UnitSpatialRecord,
    rebuild_unit_spatial_index,
    update_unit_spatial_index,
)


def _add_unit(world, faction, col, row):
    entity = world.create_entity()
    world.add_component(
        entity,
        Unit(unit_type=UnitType.INFANTRY, faction=faction, name=str(entity)),
    )
    world.add_component(entity, HexPosition(col, row))
    world.add_component(entity, UnitCount(current_count=100, max_count=100))
    return entity


def test_spatial_record_caches_world_center_and_refreshes_on_hex_change():
    world = World()
    entity = _add_unit(world, Faction.WEI, 0, 0)
    index = rebuild_unit_spatial_index(world)

    expected = index.hex_converter.hex_to_pixel(0, 0)
    record = index.by_entity[entity]
    assert (record.world_x, record.world_y) == tuple(float(value) for value in expected)

    position = world.get_component(entity, HexPosition)
    position.col = 4
    position.row = -2
    assert update_unit_spatial_index(world, entity) is True

    expected = index.hex_converter.hex_to_pixel(4, -2)
    record = index.by_entity[entity]
    assert (record.col, record.row) == (4, -2)
    assert (record.world_x, record.world_y) == tuple(float(value) for value in expected)


class _FakeIndex:
    def __init__(self):
        self.revision = 9
        self.by_entity = {
            1: UnitSpatialRecord(0, 0, Faction.WEI, 0.0, 0.0, (0, 0)),
            # Coarse-bucket false positive outside the exact expanded viewport.
            2: UnitSpatialRecord(20, 0, Faction.WEI, 1400.0, 0.0, (0, 0)),
            # In bounds but hidden by Fog for the viewing faction.
            3: UnitSpatialRecord(1, 1, Faction.SHU, 100.0, 100.0, (0, 0)),
            # In bounds and explicitly visible through Fog.
            4: UnitSpatialRecord(2, 2, Faction.SHU, 200.0, 100.0, (0, 0)),
        }

    def nonempty_buckets_in_world_rect(self, left, right, top, bottom):
        yield (0, 0), set(self.by_entity)


class _FakeWorld:
    def __init__(self):
        self._unit_spatial_index = _FakeIndex()
        self._game_state = SimpleNamespace(current_player=Faction.WEI)
        self._fog = SimpleNamespace(
            enabled=True,
            faction_vision={Faction.WEI: {(2, 2)}},
        )
        self._ui = SimpleNamespace(view_faction=None)

    def get_singleton_component(self, component_type):
        if component_type is GameState:
            return self._game_state
        if component_type is FogOfWar:
            return self._fog
        if component_type is UIState:
            return self._ui
        return None


def _bare_renderer(world):
    """Create only the object state needed by the cull method.

    The production renderer constructor initializes pygame fonts/textures.  This
    test targets only spatial candidate filtering, so exercising SDL/font setup
    would add an unrelated environment dependency to a pure unit test.
    """
    renderer = UnitRenderSystem.__new__(UnitRenderSystem)
    renderer.world = world
    return renderer


def test_spatial_cull_filters_bounds_before_fog_and_publishes_breakdown(monkeypatch):
    metrics = {}
    monkeypatch.setattr(
        scale_unit_render_system.profiling.profiler,
        "set_frame_metric",
        lambda name, value: metrics.__setitem__(name, value),
    )

    renderer = _bare_renderer(_FakeWorld())

    visible = renderer._get_visible_units([0.0, 0.0], 1.0)

    assert sorted(visible) == [1, 4]
    assert metrics["unit_cull_buckets"] == 1
    assert metrics["unit_cull_candidates"] == 4
    assert metrics["unit_cull_bounds_rejected"] == 1
    assert metrics["unit_cull_fog_rejected"] == 1
    assert metrics["unit_cull_visible"] == 2
    assert metrics["unit_cull_population"] == 4
    assert metrics["unit_cull_spatial_revision"] == 9
    assert metrics["unit_cull_world_margin"] > 0
