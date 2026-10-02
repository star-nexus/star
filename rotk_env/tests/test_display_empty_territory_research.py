"""E7 live membership, fallback and scoped ownership contracts."""
import os
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
import pytest
from framework.ecs.world import World
from rotk_env.components import MapData, TerritoryControl
from rotk_env.systems.window_map_render_system import WindowMapRenderSystem


def fixture():
    renderer = object.__new__(WindowMapRenderSystem)
    renderer.world = World()
    data = MapData(width=2, height=2, tiles={(0, 0): 1})
    renderer.world.add_singleton_component(data)
    return renderer, data


def test_empty_scope_restores_and_invalid_mode_precedes_work():
    renderer, data = fixture()
    original = renderer._render_territory_boundaries_optimized
    with renderer._display_research_frame('empty_territory'):
        renderer._render_territory_boundaries_optimized({(0, 0)}, [0, 0], 1)
        assert renderer._e7_valid_coordinates == ((0, 0),)
        with pytest.raises(RuntimeError):
            with renderer._display_research_frame('baseline'): pass
    assert renderer._render_territory_boundaries_optimized == original
    assert '_render_territory_boundaries_optimized' not in renderer.__dict__
    with pytest.raises(ValueError):
        with renderer._display_research_frame('bad'): pass
    renderer.cleanup()
    assert '_e7_valid_coordinates' not in renderer.__dict__


def test_membership_changes_and_unknown_mapping_use_original(monkeypatch):
    renderer, data = fixture()
    calls=[]
    from rotk_env.systems.map_render_system import MapRenderSystem
    monkeypatch.setattr(MapRenderSystem, '_render_territory_boundaries_optimized',
                        lambda *args: calls.append(args))
    entity=renderer.world.create_entity()
    with renderer._display_research_frame('empty_territory'):
        renderer._render_territory_boundaries_optimized({(0, 0)}, [0, 0], 1)
        assert not calls
        renderer.world.add_component(entity, TerritoryControl())
        renderer._render_territory_boundaries_optimized({(0, 0)}, [0, 0], 1)
        assert len(calls)==1
        renderer.world.remove_component(entity, TerritoryControl)
        renderer._render_territory_boundaries_optimized({(0, 0)}, [0, 0], 1)
        assert len(calls)==1
        data.tiles[(0, 0)]='unknown'
        renderer._render_territory_boundaries_optimized({(0, 0)}, [0, 0], 1)
        assert len(calls)==2
        renderer._render_territory_boundaries_optimized({('bad', 0)}, [0, 0], 1)
        assert len(calls)==3


def test_custom_override_and_exception_restoration():
    renderer, _ = fixture()
    def failing(*args): raise LookupError('original failure')
    renderer._render_territory_boundaries_optimized=failing
    with pytest.raises(LookupError, match='original failure'):
        with renderer._display_research_frame('empty_territory'):
            renderer._render_territory_boundaries_optimized({(0, 0)}, [0, 0], 1)
    assert renderer._render_territory_boundaries_optimized is failing
    assert not renderer._e7_frame_active


def test_same_size_coordinate_mutation_and_bounded_cache():
    renderer, _=fixture()
    cells={(0, 0)}
    with renderer._display_research_frame('empty_territory'):
        renderer._render_territory_boundaries_optimized(cells, [0, 0], 1)
        cells.clear();cells.add((1, 1))
        renderer._render_territory_boundaries_optimized(cells, [0, 0], 1)
        assert renderer._e7_valid_coordinates == ((1, 1),)
    assert not renderer.world._component_to_entities.get(TerritoryControl)
