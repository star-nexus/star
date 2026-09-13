"""A consumer can reconstruct display facts from journals across skipped drains."""

import copy
import pytest

pytest.importorskip("star_native")
from rotk_env.components import Combat, UnitCount, Vision
from rotk_env.prefabs.config import GameMode
from rotk_env.runtime.bootstrap import export_initial_state
from rotk_env.runtime.native import RustRuntime
from rotk_env.systems.window_vision_system import VisionSystem
from rotk_env.tests.test_native_unit_actions import setup, register, command
from rotk_env.tests.test_native_lifecycle import snapshot
from rotk_env.tests.test_native_request_batch import frozen


UNIT_COLUMNS = dict(
    position="HexPosition",
    unit="Unit",
    count="UnitCount",
    movement="MovementAnimation",
    movement_points="MovementPoints",
    action_points="ActionPoints",
    status="UnitStatus",
    skill_points="SkillPoints",
    construction_points="ConstructionPoints",
)


class DisplayFacts:
    def __init__(self):
        self.units = {}
        self.tiles = {}
        self.fog = None

    def consume(self, delta, authoritative):
        for uid in delta["removed"]:
            self.units.pop(uid, None)
        for row in delta["units"]:
            self.units[row["id"]] = {
                column: row[key]
                for key, column in UNIT_COLUMNS.items()
                if row[key] is not None
            }
        for row in delta["tiles"]:
            self.tiles[row["id"]] = row["control"]
        fog = delta["fog"]
        if fog["enabled"] is not None:
            if fog["full"]:
                self.fog = dict(
                    enabled=fog["enabled"], faction_vision={}, explored_tiles={}
                )
            self.fog["enabled"] = fog["enabled"]
            for faction in fog["factions"]:
                for key, flag in [
                    ("faction_vision", "visible"),
                    ("explored_tiles", "explored"),
                ]:
                    cells = self.fog[key].setdefault(faction["faction"], set())
                    for cell in faction["cells"]:
                        pos = (cell["col"], cell["row"])
                        if cell[flag]:
                            cells.add(pos)
                        else:
                            cells.discard(pos)
        expected_units = {}
        expected_tiles = {}
        for row in authoritative["entities"]:
            cols = row["components"]
            if "Unit" in cols:
                expected_units[row["id"]] = {
                    key: cols[key] for key in UNIT_COLUMNS.values() if key in cols
                }
            if "TerritoryControl" in cols:
                expected_tiles[row["id"]] = cols["TerritoryControl"]
        assert self.units == expected_units
        assert self.tiles == expected_tiles
        expected_fog = authoritative["singletons"].get("FogOfWar")
        if expected_fog is not None:
            expected_fog = copy.deepcopy(expected_fog)
            for key in ("faction_vision", "explored_tiles"):
                expected_fog[key] = {
                    f: {tuple(p) for p in cells["$set"]}
                    for f, cells in expected_fog[key].items()
                }
            assert self.fog == expected_fog
        for name, state in delta["state"].items():
            assert state == authoritative["singletons"][name]


@pytest.mark.parametrize("mode", [GameMode.REAL_TIME, GameMode.TURN_BASED])
@pytest.mark.parametrize("drain_every", [1, 7])
def test_display_journals_cover_resource_recovery_capture_fog_death_and_reset(
    mode, drain_every, frozen
):
    world, (a, b, c), territory, llm = setup("window", mode)
    for uid in (a, b, c):
        world.add_component(uid, Vision(range=1))
    vision = VisionSystem()
    world.add_system(vision)
    vision.update(0.0)
    world.get_component(a, Combat).attack_range = 5
    world.get_component(c, UnitCount).current_count = 1
    try:
        with RustRuntime(export_initial_state(world, display="window")) as native:
            facts = DisplayFacts()

            def drain():
                delta = native.take_presentation_delta()
                facts.consume(delta, native.export_state())
                return delta

            first = drain()
            saved = copy.deepcopy(first)
            register(world, native, llm, "window")
            for verb, params in [
                ("rest", {"unit_id": a}),
                ("occupy", {"unit_id": a, "position": {"col": -1, "row": 0}}),
                ("fortify", {"unit_id": a, "position": {"col": -1, "row": 0}}),
                ("move", {"unit_id": b, "target_position": {"col": -1, "row": 1}}),
            ]:
                assert command(world, native, llm, verb, params, display="window")[
                    "success"
                ]
                drain()
            assert (
                territory.start_capture(c, (1, 1))
                == native.start_capture(c, (1, 1))
                == True
            )
            drain()
            for index in range(42):
                if index == 10:
                    assert command(
                        world,
                        native,
                        llm,
                        "attack",
                        {"unit_id": a, "target_id": c},
                        display="window",
                    )["success"]
                if index == 20 and mode == GameMode.TURN_BASED:
                    turn = next(
                        s for s in world.systems if type(s).__name__ == "TurnSystem"
                    )
                    turn.end_turn()
                    native.finish_human_turn(wall_time=frozen[0])
                frozen[0] += 0.25
                world.update(0.25)
                native.step(0.25, wall_time=frozen[0])
                snapshot(world, native, "window")
                if index % drain_every == 0:
                    drain()
                if index == 30:
                    initial = native.export_state()
                    native.reset(initial)
                    facts = DisplayFacts()
                    assert drain()["fog"]["full"]
            drain()
            assert first == saved
            empty = drain()
            assert empty["units"] == empty["tiles"] == empty["fog"]["factions"] == []
            assert empty["fog"]["full"] is False
    finally:
        world.reset()


def test_idle_ticks_emit_no_unit_or_tile_rows(frozen):
    world, ids, territory, llm = setup()
    # Start with full AP to isolate an inactive world from pending recovery.
    from rotk_env.components import ActionPoints

    for uid in ids:
        ap = world.get_component(uid, ActionPoints)
        ap.current_ap = ap.max_ap
    try:
        with RustRuntime(export_initial_state(world)) as native:
            native.take_presentation_delta()
            native.step(1 / 30, wall_time=frozen[0])
            delta = native.take_presentation_delta()
            assert delta["units"] == delta["tiles"] == []
            assert delta["state"]["GameTime"]["game_elapsed_time"] == 1 / 30
    finally:
        world.reset()
