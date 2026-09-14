"""Human input uses the original low-level contracts, not Agent action handlers."""

import pytest

pytest.importorskip("star_native")
from rotk_env.components import (
    ActionPoints, ConstructionPoints, FogOfWar, GameState, MapData, Player,
    TerritoryControl, TurnManager, UnitStatus,
)
from rotk_env.prefabs.config import GameMode, Faction, UnitState
from rotk_env.runtime.bootstrap import export_initial_state, encode
from rotk_env.runtime.native import RustRuntime
from rotk_env.systems.ui_button_system import UIButtonSystem
from rotk_env.systems.unit_action_button_system import UnitActionButtonSystem
from rotk_env.tests.test_native_combat_presentation import make
from rotk_env.tests.test_native_lifecycle import snapshot, capture_events
from rotk_env.tests.test_native_request_batch import frozen
from rotk_env.tests.test_native_unit_actions import setup


def panel(cls, world):
    # These command methods require no rendering/font initialization.
    instance = cls.__new__(cls)
    instance.world = world
    return instance


@pytest.mark.parametrize("display", ["none", "dummy", "window"])
@pytest.mark.parametrize("mode", [GameMode.REAL_TIME, GameMode.TURN_BASED])
@pytest.mark.parametrize("kind", ["melee", "ranged"])
@pytest.mark.parametrize("dead,critical", [(False, False), (False, True), (True, True)])
def test_human_attack_result_state_events_and_visuals(display, mode, kind, dead, critical, frozen, monkeypatch):
    world, (a, b, c), llm = make(display, mode, kind, dead, critical)
    # Local commands have no Protocol ingress. Post-game Agent report collection
    # is a separate host integration gate and is not part of this fixture.
    llm.enabled = False
    combat = next(s for s in world.systems if type(s).__name__ == "CombatSystem")
    events = capture_events(monkeypatch)
    try:
        with RustRuntime(export_initial_state(world, display=display)) as native:
            native.take_presentation_delta()
            # Valid hit followed by friendly, missing and (when dead) destroyed targets.
            for target in (c, b, 999999, c):
                expected = combat.attack(a, target)
                assert native.execute_control("attack", unit_id=a, target_id=target) == expected
                snapshot(world, native, display)
                assert native.take_presentation_delta()["events"] == events
                events.clear()
            for dt in (.01, .1, .25, 1., 2.):
                world.update(dt)
                native.step(dt)
                snapshot(world, native, display)
                assert native.take_presentation_delta()["events"] == events
                events.clear()
    finally:
        world.reset()


@pytest.mark.parametrize("display", ["none", "dummy", "window"])
@pytest.mark.parametrize("mode", [GameMode.REAL_TIME, GameMode.TURN_BASED])
def test_human_move_keeps_occupancy_and_animation_boundary(display, mode, frozen):
    world, (a, b, c), _, _ = setup(display, mode)
    mover = next(s for s in world.systems if type(s).__name__ == "MovementSystem")
    try:
        with RustRuntime(export_initial_state(world, display=display)) as native:
            for goal in ((0, 0), (-1, 0), (1, 1), (100, 100), (-2, 0), (-2, 1)):
                expected = encode(mover.move_unit(a, goal))
                assert native.execute_control("move", unit_id=a, position=goal) == expected
                snapshot(world, native, display)
            for dt in (.01, .2, 1.):
                world.update(dt)
                native.step(dt)
                snapshot(world, native, display)
    finally:
        world.reset()


@pytest.mark.parametrize("mode", [GameMode.REAL_TIME, GameMode.TURN_BASED])
@pytest.mark.parametrize("kind", ["wait", "garrison"])
@pytest.mark.parametrize("ap", [None, 0, 1, 6])
def test_human_wait_and_garrison_spend_ap_without_agent_rest(kind, mode, ap, frozen):
    world, (a, b, c), _, _ = setup(mode=mode)
    status = world.get_component(a, UnitStatus)
    status.current_status = UnitState.CONFUSION
    status.status_duration = 5
    if ap is None:
        world.remove_component(a, ActionPoints)
    else:
        world.get_component(a, ActionPoints).current_ap = ap
    buttons = panel(UnitActionButtonSystem, world)
    try:
        with RustRuntime(export_initial_state(world)) as native:
            for uid in (a, a, 999999):
                expected = getattr(buttons, f"_execute_{kind}_action")(uid)
                assert native.execute_control(kind, unit_id=uid) == expected
                snapshot(world, native, "none")
            assert status.current_status == UnitState.CONFUSION
            assert status.status_duration == 5 and status.wait_turns == 0
    finally:
        world.reset()


@pytest.mark.parametrize("mode", [GameMode.REAL_TIME, GameMode.TURN_BASED])
@pytest.mark.parametrize("case", ["normal", "enemy", "fortified", "empty_ap", "empty_cp", "no_ap", "no_cp"])
def test_human_fortify_preserves_realtime_resource_exception(mode, case, frozen):
    world, (a, b, c), territory, _ = setup(mode=mode)
    cell = (-1, 0)
    tile = world.get_singleton_component(MapData).tiles[cell]
    control = world.get_component(tile, TerritoryControl)
    control.controlling_faction = Faction.SHU if case == "enemy" else Faction.WEI
    control.fortified = case == "fortified"
    if case == "empty_ap": world.get_component(a, ActionPoints).current_ap = 0
    if case == "empty_cp": world.get_component(a, ConstructionPoints).current_cp = 0
    if case == "no_ap": world.remove_component(a, ActionPoints)
    if case == "no_cp": world.remove_component(a, ConstructionPoints)
    try:
        with RustRuntime(export_initial_state(world)) as native:
            for target in (cell, cell, (100, 100)):
                expected = territory.build_fortification(a, target)
                assert native.execute_control("fortify", unit_id=a, position=target) == expected
                snapshot(world, native, "none")
    finally:
        world.reset()


@pytest.mark.parametrize("mode", [GameMode.REAL_TIME, GameMode.TURN_BASED])
@pytest.mark.parametrize("case", ["normal", "reverse", "empty", "unknown", "zero", "negative_index", "no_manager", "game_over"])
def test_toolbar_end_turn_uses_manager_order_without_keyboard_reset(mode, case, frozen, monkeypatch):
    world, (a, b, c), _, _ = setup(mode=mode)
    players = list(world.query().with_component(Player).ordered_entities())
    if case == "reverse": players.reverse()
    if case == "empty": players.clear()
    if case == "unknown": players = [999999]
    if case == "zero": players = [0]
    world.add_singleton_component(TurnManager(players, -2 if case == "negative_index" else 0))
    if case == "no_manager": world.remove_singleton_component(TurnManager)
    if case == "game_over": world.get_singleton_component(GameState).game_over = True
    world.get_component(a, ActionPoints).current_ap = 0
    buttons = panel(UIButtonSystem, world)
    events = capture_events(monkeypatch)
    try:
        with RustRuntime(export_initial_state(world)) as native:
            native.take_presentation_delta()
            for _ in range(4):
                assert native.execute_control("toolbar_end_turn") == buttons._end_turn()
                snapshot(world, native, "none")
                assert native.take_presentation_delta()["events"] == events == []
            assert world.get_component(a, ActionPoints).current_ap == 0
    finally:
        world.reset()


@pytest.mark.parametrize("present", [False, True])
def test_fog_control_invalidates_queries_without_advancing_simulation(present, frozen):
    from rotk_env.systems.input_system import InputHandlingSystem
    world, ids, _, _ = setup()
    if present: world.add_singleton_component(FogOfWar())
    else: world.remove_singleton_component(FogOfWar)
    inputs = panel(InputHandlingSystem, world)
    try:
        with RustRuntime(export_initial_state(world)) as native:
            native.take_presentation_delta()
            for enabled in (False, True, False):
                before = native.diagnostics()
                assert native.execute_control("set_fog", enabled=enabled) == inputs._set_fog_enabled(None, enabled)
                snapshot(world, native, "none")
                after = native.diagnostics()
                assert after["revision"] > before["revision"]
                assert after["clock"] == before["clock"]
                assert native.take_presentation_delta()["fog"]["enabled"] == enabled
    finally:
        world.reset()


@pytest.mark.parametrize("kind,parameters", [
    ("unknown", {}), ("wait", {"unit_id": -1}), ("wait", {"unit_id": True}),
    ("wait", {"unit_id": 1, "agent_id": "spoof"}), ("move", {"unit_id": 1, "position": [1]}),
    ("move", {"unit_id": 1, "position": [1.5, 1]}), ("set_fog", {"enabled": 1}),
])
def test_malformed_controls_reject_before_mutation_and_close(kind, parameters, frozen):
    world, ids, _, _ = setup()
    try:
        with RustRuntime(export_initial_state(world)) as native:
            before = native.export_state()
            with pytest.raises(RuntimeError): native.execute_control(kind, **parameters)
            assert native.export_state() == before
            native.close()
            with pytest.raises(RuntimeError, match="closed"):
                native.execute_control("wait", unit_id=ids[0])
    finally:
        world.reset()
