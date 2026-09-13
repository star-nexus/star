"""Presentation lifetimes preserve the legacy ID stream without native rendering."""

import pytest

pytest.importorskip("star_native")
from rotk_env.components import Combat, Unit, UnitCount, Camera, MatchRules, RngService
from rotk_env.prefabs.config import GameMode, UnitType
from rotk_env.runtime.bootstrap import export_initial_state, encode
from rotk_env.runtime.native import RustRuntime
from rotk_env.tests.test_native_request_batch import frozen
from rotk_env.tests.test_native_unit_actions import setup, register
from rotk_env.tests.test_native_lifecycle import capture_events, snapshot


def make(display, mode, kind, dead=False, critical=False):
    w, (a, b, c), _, llm = setup(display, mode)
    if display == "window":
        from rotk_env.systems.window_animation_system import AnimationSystem

        index = next(
            i for i, s in enumerate(w.systems) if type(s).__name__ == "AnimationSystem"
        )
        animation = AnimationSystem()
        animation.world = w
        w.systems[index] = animation
        from rotk_env.systems.window_combat_system import CombatSystem

        index = next(
            i for i, s in enumerate(w.systems) if type(s).__name__ == "CombatSystem"
        )
        combat = CombatSystem()
        combat.world = w
        w.systems[index] = combat
        w.add_singleton_component(Camera(zoom=0.5))
    w.get_component(a, Unit).unit_type = (
        UnitType.ARCHER if kind == "ranged" else UnitType.INFANTRY
    )
    w.get_component(a, Combat).attack_range = 5
    w.get_component(c, UnitCount).current_count = 1 if dead else 10000
    w.get_component(c, UnitCount).max_count = 10000
    if critical:
        import random

        w.get_singleton_component(RngService)._rngs["combat"] = random.Random(1)
    return w, (a, b, c), llm


def request(w, native, llm, verb, params, display):
    expected = llm._process_action_request(
        agent_id="alpha",
        action_id=0,
        action=verb,
        params=dict(params),
        send_response=False,
    )
    actual = native.execute_action(verb, params, agent_id="alpha")
    assert encode(actual) == encode(expected)
    snapshot(w, native, display)
    return actual


@pytest.mark.parametrize("display", ["none", "dummy", "window"])
@pytest.mark.parametrize("mode", [GameMode.REAL_TIME, GameMode.TURN_BASED])
@pytest.mark.parametrize("kind", ["melee", "ranged"])
@pytest.mark.parametrize("dead", [False, True])
@pytest.mark.parametrize("critical", [False, True])
def test_combat_visual_lifecycle_ids_events_reset_and_cleanup(
    display, mode, kind, dead, critical, frozen, monkeypatch
):
    w, (a, b, c), llm = make(display, mode, kind, dead, critical)
    events = capture_events(monkeypatch)
    try:
        with RustRuntime(export_initial_state(w, display=display)) as native:
            register(w, native, llm, display)
            native.take_presentation_delta()
            events.clear()
            result = request(
                w, native, llm, "attack", {"unit_id": a, "target_id": c}, display
            )
            assert result["success"]
            if critical:
                assert result["battle_summary"]["battle_result"]["is_critical"]
            delta = native.take_presentation_delta()
            assert delta["events"] == events
            events.clear()
            if display != "none":
                assert delta["visuals"]["rows"]
            # Small dt crosses the ranged projectile creation phase; later large
            # dt expires every temporary entity. Reset also tests the spawn flag.
            for index, dt in enumerate([0.01] * 25 + [0.5, 1.0, 2.0]):
                frozen[0] += 0.1
                w.update(dt)
                native.step(dt, wall_time=frozen[0])
                snapshot(w, native, display)
                delta = native.take_presentation_delta()
                assert delta["events"] == events
                events.clear()
                if index in (8, 20):
                    native.reset(native.export_state())
                    snapshot(w, native, display)
                    native.take_presentation_delta()
            assert all(
                not rows
                for rows in native.export_state()["systems"]["VisualLifecycle"].values()
            )
            # Immutable, detached output survives subsequent cleanup.
            assert result["battle_summary"]["battle_result"]["target_destroyed"] == dead
    finally:
        w.reset()


@pytest.mark.parametrize("disabled", [False, True])
def test_repeated_attacks_restart_projectile_flag_and_visual_timers(disabled, frozen):
    w, (a, b, c), llm = make("dummy", GameMode.REAL_TIME, "ranged")
    animation = next(s for s in w.systems if type(s).__name__ == "AnimationSystem")
    animation.enabled = not disabled
    try:
        with RustRuntime(export_initial_state(w, display="dummy")) as native:
            register(w, native, llm, "dummy")
            for i in range(4):
                request(
                    w, native, llm, "attack", {"unit_id": a, "target_id": c}, "dummy"
                )
                for _ in range(10):
                    w.update(0.01)
                    native.step(0.01)
                    snapshot(w, native, "dummy")
            assert bool(native.export_state()["systems"]["VisualLifecycle"]["attack"])
    finally:
        w.reset()


def test_python_visual_projection_matches_window_math_and_never_creates_world_entities(
    frozen,
):
    from rotk_env.runtime.visual_projection import VisualProjection
    from rotk_env.components import (
        AttackAnimation,
        DamageNumber,
        ProjectileAnimation,
        EffectAnimation,
    )

    w, (a, b, c), llm = make("window", GameMode.REAL_TIME, "ranged", critical=True)
    projection = VisualProjection()
    types = (AttackAnimation, DamageNumber, ProjectileAnimation, EffectAnimation)
    try:
        with RustRuntime(export_initial_state(w, display="window")) as native:
            register(w, native, llm, "window")
            request(w, native, llm, "attack", {"unit_id": a, "target_id": c}, "window")
            for index in range(80):
                zoom = 0.5 if index < 5 else 1.25
                w.get_singleton_component(Camera).zoom = zoom
                w.update(0.04)
                native.step(0.04)
                snapshot(w, native, "window")
                delta = native.take_presentation_delta()
                before = native.export_state()
                projection.apply(delta["visuals"], zoom=zoom)
                assert native.export_state() == before
                expected_ids = {
                    uid
                    for uid, comps in w.entities.items()
                    if any(t in comps for t in types)
                }
                assert set(projection.entities) == expected_ids
                for uid, components in projection.entities.items():
                    for cls, obj in components.items():
                        expected = w.get_component(uid, cls)
                        assert expected is not None
                        if cls is DamageNumber:
                            assert obj.position == pytest.approx(expected.position)
                            assert (
                                obj.text == expected.text
                                and obj.color == expected.color
                            )
                            assert obj.elapsed_time == expected.elapsed_time
                        elif cls is AttackAnimation:
                            assert obj.current_render_pos == pytest.approx(
                                expected.current_render_pos
                            )
                            assert (
                                obj.phase == expected.phase
                                and obj.show_aim_line == expected.show_aim_line
                            )
                        elif cls is ProjectileAnimation:
                            assert obj.current_pos == pytest.approx(
                                expected.current_pos
                            )
                            assert obj.rotation == pytest.approx(expected.rotation)
                        else:
                            assert obj.progress == expected.progress
            assert not projection.entities
            projection.reset()
            assert not projection.entities
    finally:
        w.reset()
