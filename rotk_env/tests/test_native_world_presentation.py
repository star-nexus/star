"""Existing renderers can use a detached derived World without gameplay updates."""

from copy import deepcopy
import pytest

pytest.importorskip("star_native")
from framework import World
from rotk_env import components as c
from rotk_env.prefabs.config import GameMode
from rotk_env.runtime.bootstrap import export_initial_state, encode
from rotk_env.runtime.native import RustRuntime
from rotk_env.runtime.world_presentation import WorldPresentation, _UNIT_COLUMNS
from rotk_env.tests.test_native_combat_presentation import make, request
from rotk_env.tests.test_native_unit_actions import register
from rotk_env.tests.test_native_request_batch import frozen
from rotk_env.utils.unit_spatial_index import get_unit_spatial_index


def detached_world(source):
    result = World()
    for uid, components in source.entities.items():
        result.ensure_entity(uid)
        for component in components.values():
            result.add_component(uid, deepcopy(component))
    for component in source._singleton_components.values():
        result.add_singleton_component(deepcopy(component))
    return result


@pytest.mark.parametrize("kind", ["melee", "ranged"])
@pytest.mark.parametrize("dead", [False, True])
def test_presentation_world_tracks_native_facts_and_legacy_visuals_without_simulation(
    kind, dead, frozen
):
    source, (a, b, target), llm = make(
        "window", GameMode.REAL_TIME, kind, dead=dead, critical=True
    )
    display = detached_world(source)
    presentation = WorldPresentation(display)
    visual_types = (
        c.AttackAnimation,
        c.DamageNumber,
        c.EffectAnimation,
        c.ProjectileAnimation,
    )
    try:
        with RustRuntime(export_initial_state(source, display="window")) as native:
            initial = native.take_presentation_delta()
            presentation.apply(initial)
            register(source, native, llm, "window")
            request(
                source,
                native,
                llm,
                "attack",
                {"unit_id": a, "target_id": target},
                "window",
            )
            for index in range(80):
                zoom = 0.5 if index < 5 else 1.25
                source.get_singleton_component(c.Camera).zoom = zoom
                display.get_singleton_component(c.Camera).zoom = zoom
                source.update(0.04)
                native.step(0.04)
                before = native.export_state()
                presentation.apply(native.take_presentation_delta())
                assert native.export_state() == before
                assert display.systems == []
                for uid in source.query().with_all(c.Unit).entities():
                    for cls in _UNIT_COLUMNS.values():
                        assert encode(display.get_component(uid, cls)) == encode(
                            source.get_component(uid, cls)
                        )
                assert (
                    display.query().with_all(c.Unit).entities()
                    == source.query().with_all(c.Unit).entities()
                )
                for cls in visual_types:
                    ids = source.query().with_all(cls).entities()
                    assert display.query().with_all(cls).entities() == ids
                    for uid in ids:
                        actual = display.get_component(uid, cls)
                        expected = source.get_component(uid, cls)
                        if cls is c.DamageNumber:
                            assert actual.position == pytest.approx(expected.position)
                        elif cls is c.AttackAnimation:
                            assert actual.current_render_pos == pytest.approx(
                                expected.current_render_pos
                            )
                        elif cls is c.ProjectileAnimation:
                            assert actual.current_pos == pytest.approx(
                                expected.current_pos
                            )
                        else:
                            assert actual.progress == expected.progress
            index = get_unit_spatial_index(display)
            assert (target not in index.by_entity) == dead
            # UI writes affect only the derived world and cannot alter authority.
            before = native.export_state()
            display.get_component(a, c.UnitCount).current_count = -100
            assert native.export_state() == before
            with pytest.raises(ValueError, match="Stale"):
                presentation.apply(initial)
            native.reset(native.export_state())
            with pytest.raises(ValueError, match="epoch"):
                presentation.apply(native.take_presentation_delta())
    finally:
        source.reset()
        display.reset()
