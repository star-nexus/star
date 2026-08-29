"""Move targets are checked against the latest compact reachable list."""

from rotk_agent.core.reachable_guard import (
    ReachableGuard,
    as_hex,
    index_reachable,
    parse_move,
)


COMPACT = {
    "units": [
        [
            231,
            "infantry",
            -1,
            -3,
            100,
            100,
            1,
            4,
            1,
            10,
            2,
            10,
            {"reachable": [[-1, -2], [0, -2]], "attackable": [236]},
        ]
    ]
}


class TestHexParsing:
    def test_dict_and_pair(self):
        assert as_hex({"col": -1, "row": 2}) == (-1, 2)
        assert as_hex([-1, 2]) == (-1, 2)
        assert as_hex({"target_position": {"col": 3, "row": 4}}) == (3, 4)

    def test_rejects_junk(self):
        assert as_hex(None) is None
        assert as_hex({"col": "x", "row": 1}) is None


class TestIndexAndParse:
    def test_indexes_only_rows_with_reachable(self):
        index = index_reachable(COMPACT)
        assert index[231] == [(-1, -2), (0, -2)]

    def test_pack_without_affordance_is_empty(self):
        assert index_reachable({"units": [[231, "infantry", 0, 0]]}) == {}

    def test_pack_c_attackable_only_is_skipped(self):
        row = [231, "infantry", 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, {"attackable": [9]}]
        assert index_reachable({"units": [row]}) == {}

    def test_parse_move_reads_params(self):
        assert parse_move(
            {
                "action": "move",
                "params": {"unit_id": 231, "target_position": {"col": 0, "row": -2}},
            }
        ) == (231, (0, -2))

    def test_parse_move_ignores_other_actions(self):
        assert parse_move({"action": "attack", "params": {"unit_id": 1}}) is None


class TestReachableGuard:
    def test_listed_hex_is_legal(self):
        guard = ReachableGuard()
        guard.observe_faction_state(COMPACT)
        assert (
            guard.check_move(
                {
                    "action": "move",
                    "params": {
                        "unit_id": 231,
                        "target_position": {"col": 0, "row": -2},
                    },
                }
            )
            is None
        )

    def test_unlisted_hex_is_a_mismatch(self):
        guard = ReachableGuard()
        guard.observe_faction_state(COMPACT)
        mismatch = guard.check_move(
            {
                "action": "move",
                "params": {
                    "unit_id": 231,
                    "target_position": {"col": 9, "row": 9},
                },
            }
        )
        assert mismatch is not None
        assert mismatch.unit_id == 231
        assert mismatch.target == (9, 9)
        assert mismatch.reachable == [(-1, -2), (0, -2)]

    def test_empty_reachable_rejects_any_move(self):
        guard = ReachableGuard()
        row = list(COMPACT["units"][0])
        row[12] = {"reachable": []}
        guard.observe_faction_state({"units": [row]})
        assert guard.check_move(
            {
                "action": "move",
                "params": {"unit_id": 231, "target_position": {"col": 0, "row": 0}},
            }
        )

    def test_unknown_unit_is_not_flagged(self):
        guard = ReachableGuard()
        guard.observe_faction_state(COMPACT)
        assert (
            guard.check_move(
                {
                    "action": "move",
                    "params": {
                        "unit_id": 999,
                        "target_position": {"col": 0, "row": 0},
                    },
                }
            )
            is None
        )

    def test_no_snapshot_is_not_flagged(self):
        guard = ReachableGuard()
        assert (
            guard.check_move(
                {
                    "action": "move",
                    "params": {
                        "unit_id": 231,
                        "target_position": {"col": 0, "row": 0},
                    },
                }
            )
            is None
        )

    def test_latest_snapshot_replaces_the_previous(self):
        guard = ReachableGuard()
        guard.observe_faction_state(COMPACT)
        row = list(COMPACT["units"][0])
        row[12] = {"reachable": [[4, 4]]}
        guard.observe_faction_state({"units": [row]})
        assert (
            guard.check_move(
                {
                    "action": "move",
                    "params": {
                        "unit_id": 231,
                        "target_position": {"col": 0, "row": -2},
                    },
                }
            )
            is not None
        )
        assert (
            guard.check_move(
                {
                    "action": "move",
                    "params": {
                        "unit_id": 231,
                        "target_position": {"col": 4, "row": 4},
                    },
                }
            )
            is None
        )


class TestObserveSkipsFailures:
    def test_rejected_payload_does_not_replace_snapshot(self):
        from rotk_agent.core.types import ToolCall
        from rotk_agent.tests.test_agent_loop import build_agent

        agent = build_agent([])
        agent.reachable_guard.observe_faction_state(COMPACT)
        call = ToolCall(id="c", name="perform_action", arguments="{}")
        agent._maybe_observe_faction_state(
            call,
            {"action": "get_faction_state"},
            {
                "success": False,
                "result": False,
                "units": [],
                "details": "wrong faction",
            },
        )
        assert agent.reachable_guard.check_move(
            {
                "action": "move",
                "params": {
                    "unit_id": 231,
                    "target_position": {"col": 9, "row": 9},
                },
            }
        )

    def test_stringified_false_is_treated_as_rejection(self):
        from rotk_agent.core.agent import RoTKChatAgent

        assert RoTKChatAgent._env_rejected({"result": "false"})
        assert RoTKChatAgent._env_rejected({"success": False})
        assert not RoTKChatAgent._env_rejected({"units": [[231]]})
