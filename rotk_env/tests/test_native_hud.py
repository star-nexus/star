"""HUD history transport and UI-only scrolling over native authoritative statistics."""

from copy import deepcopy
import json
import pytest

pytest.importorskip("star_native")
from rotk_env import components as c
from rotk_env.prefabs.config import GameMode
from rotk_env.runtime.bootstrap import export_initial_state, encode
from rotk_env.runtime.native import RustRuntime
from rotk_env.runtime.world_presentation import WorldPresentation
from rotk_env.systems.statistics_system import StatisticsSystem
from rotk_env.systems.window_statistics_system import StatisticsSystem as WindowStatistics
from rotk_env.tests.test_native_combat_presentation import make
from rotk_env.tests.test_native_lifecycle import snapshot
from rotk_env.tests.test_native_request_batch import frozen
from rotk_env.tests.test_native_world_presentation import detached_world


@pytest.fixture
def creation_times(frozen, monkeypatch):
    for cls, field in ((c.UnitStatistics, "creation_time"), (c.UnitObservation, "last_seen_time")):
        original = cls.__init__
        def initialize(self, *args, _init=original, _field=field, **kwargs):
            _init(self, *args, **kwargs)
            setattr(self, _field, frozen[0])
        monkeypatch.setattr(cls, "__init__", initialize)


@pytest.mark.parametrize("display_mode", ["none", "dummy", "window"])
@pytest.mark.parametrize("mode", [GameMode.REAL_TIME, GameMode.TURN_BASED])
@pytest.mark.parametrize("capacity", [0, 3, 100])
def test_hud_counters_and_battle_log_match_after_commands_ticks_and_reset(display_mode, mode, capacity, frozen, creation_times):
    source, (a, b, enemy), llm = make(display_mode, mode, "ranged", critical=True)
    llm.enabled = False
    source.add_system(WindowStatistics(batch_size=1) if display_mode == "window" else StatisticsSystem())
    log = c.BattleLog(max_entries=capacity, visible_lines=2)
    for n in range(5): log.add_entry(f"initial-{n}")
    source.add_singleton_component(log)
    display = detached_world(source)
    presentation = WorldPresentation(display)
    initial = export_initial_state(source, display=display_mode)
    combat = next(s for s in source.systems if type(s).__name__ == "CombatSystem")
    try:
        with RustRuntime(initial) as native:
            presentation.apply(native.take_presentation_delta())
            for i in range(3):
                assert native.execute_control("attack", unit_id=a, target_id=enemy) == combat.attack(a, enemy)
                snapshot(source, native, display_mode)
                delta = native.take_presentation_delta()
                assert not delta["hud"]["battle_log"]["full"]
                assert delta["hud"]["battle_log"]["entries"]
                presentation.apply(delta)
                assert encode(display.get_singleton_component(c.BattleLog)) == encode(log)
                assert display.get_singleton_component(c.GameStats).faction_stats == source.get_singleton_component(c.GameStats).faction_stats
                for dt in (.01, .15, 2.):
                    frozen[0] += .25
                    source.update(dt); native.step(dt)
                    snapshot(source, native, display_mode)
                    presentation.apply(native.take_presentation_delta())
                    assert encode(display.get_singleton_component(c.BattleLog)) == encode(log)
                    expected = source.get_singleton_component(c.GameStats)
                    actual = display.get_singleton_component(c.GameStats)
                    assert actual.faction_stats == expected.faction_stats
                    assert actual.total_game_time == expected.total_game_time
            # Scroll position is display-only until the next appended message
            # applies the original automatic scroll-to-bottom behavior.
            before = native.export_state()
            shown = display.get_singleton_component(c.BattleLog)
            shown.scroll_up(); shown.show_log = False
            offset = shown.scroll_offset
            idle = native.take_presentation_delta()
            assert idle["hud"]["battle_log"]["entries"] == []
            presentation.apply(idle)
            assert shown.scroll_offset == offset and not shown.show_log
            assert native.export_state() == before
            native.reset(before)
            fresh = native.take_presentation_delta()
            assert fresh["hud"]["battle_log"]["full"]
            assert fresh["hud"]["battle_log"]["baseline"] == before["singletons"]["BattleLog"]
    finally:
        source.reset(); display.reset()


def test_multiple_commands_before_first_display_do_not_duplicate_initial_log(frozen):
    source, (a, b, enemy), llm = make("none", GameMode.REAL_TIME, "melee")
    source.add_singleton_component(c.BattleLog())
    source.add_system(StatisticsSystem())
    display = detached_world(source)
    try:
        with RustRuntime(export_initial_state(source)) as native:
            for _ in range(3): native.execute_control("attack", unit_id=a, target_id=enemy)
            delta = native.take_presentation_delta()
            assert delta["hud"]["battle_log"]["entries"] == []
            WorldPresentation(display).apply(delta)
            assert encode(display.get_singleton_component(c.BattleLog)) == native.export_state()["singletons"]["BattleLog"]
    finally:
        source.reset(); display.reset()


def test_hud_omits_full_histories_and_preserves_detached_outputs(frozen):
    source, ids, llm = make("none", GameMode.REAL_TIME, "melee")
    stats = source.get_singleton_component(c.GameStats)
    stats.battle_history = [{"large_history_marker": i} for i in range(10000)]
    stats.unit_observation_history = deepcopy(stats.battle_history)
    source.add_singleton_component(c.BattleLog())
    initial = export_initial_state(source)
    try:
        with RustRuntime(initial) as native:
            first = native.take_presentation_delta()
            assert "large_history_marker" not in json.dumps(first)
            assert len(json.dumps(first["hud"])) < 1000
            assert len(native.export_state()["singletons"]["GameStats"]["battle_history"]) == 10000
            saved = deepcopy(first)
            native.step(.1); native.take_presentation_delta()
            assert first == saved
    finally:
        source.reset()
