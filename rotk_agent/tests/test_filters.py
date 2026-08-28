"""Filters must trim context without dropping anything actionable."""

from rotk_agent.core import filters


class TestUnitStateKeys:
    """The ENV uses two different keys for unit state, depending on the action.

    `observation` nests it under `status`; `get_unit_info` and
    `get_faction_state` use `unit_status`. Each old per-file filter hardcoded
    one of the two, so half of them silently filtered nothing.
    """

    def test_strips_noise_under_status_key(self):
        result = filters.filter_observation_result(
            {"unit_info": {"status": {"morale": "high", "fatigue": "none", "hp": 90}}}
        )
        status = result["unit_info"]["status"]
        assert "morale" not in status
        assert "fatigue" not in status
        assert status["hp"] == 90

    def test_strips_noise_under_unit_status_key(self):
        result = filters.filter_observation_result(
            {"unit_info": {"unit_status": {"morale": "high", "fatigue": "none", "hp": 90}}}
        )
        unit_status = result["unit_info"]["unit_status"]
        assert "morale" not in unit_status
        assert "fatigue" not in unit_status
        assert unit_status["hp"] == 90

    def test_faction_state_compacts_to_fixed_rows(self):
        original = {
            "success": True,
            "result": True,
            "state": "active",
            "faction": "wei",
            "fog": "active",
            "total_units": 1,
            "alive_units": 1,
            "actionable_units": 1,
            "units": [
                {
                    "unit_id": 7,
                    "unit_type": "infantry",
                    "faction": "wei",
                    "position": {"col": 1, "row": 3},
                    "unit_status": {
                        "morale": "low",
                        "fatigue": "none",
                        "current_count": 40,
                        "max_count": 100,
                        "health_percentage": 40.0,
                    },
                    "capabilities": {
                        "attack_points": 2,
                        "properties": {
                            "attack_range": 1,
                            "attack_power": 10,
                            "vision_range": 2,
                            "defense": 10,
                        },
                        "unit_resources": {
                            "remaining_action_points": 1,
                            "remaining_movement_points": 4,
                        },
                    },
                    "available_skills": [],
                    "owner": "wei_vanguard",
                    "commandable": False,
                    "reachable": [
                        {"col": -3, "row": 2},
                        {"col": -3, "row": 3},
                    ],
                    "attackable": [236, 239],
                }
            ],
        }
        result = filters.filter_faction_state_result(original)
        assert result == {
            "state": "active",
            "fog": "active",
            "counts": [1, 1, 1],
            "units": [
                [
                    7,
                    "infantry",
                    1,
                    3,
                    40,
                    100,
                    1,
                    4,
                    1,
                    10,
                    2,
                    10,
                    [[-3, 2], [-3, 3]],
                    [236, 239],
                ]
            ],
        }
        assert original["units"][0]["reachable"][0] == {"col": -3, "row": 2}
        assert original["units"][0]["attackable"] == [236, 239]

    def test_faction_state_compacts_enemies_and_non_plain_terrain(self):
        original = {
            "success": True,
            "visible_enemy_units": [
                {
                    "unit_id": 9,
                    "unit_type": "cavalry",
                    "faction": "shu",
                    "position": {"col": 1, "row": 0},
                    "unit_status": {"morale": "high", "current_count": 80},
                    "reachable": [{"col": 0, "row": 0}],
                }
            ],
            "visible_terrain": [
                {
                    "col": 0,
                    "row": 0,
                    "type": "plain",
                    "movement_cost": 1,
                    "passable": True,
                },
                {
                    "col": 1,
                    "row": 0,
                    "type": "forest",
                    "movement_cost": 2,
                    "passable": True,
                    "defense_bonus": 1,
                },
                {
                    "col": 2,
                    "row": 0,
                    "type": "water",
                    "movement_cost": 999,
                    "passable": False,
                },
                {
                    "position": {"col": 3, "row": 4},
                    "type": "mountain",
                    "movement_cost": 3,
                },
            ],
        }
        result = filters.filter_faction_state_result(original)
        assert result["enemies"] == [[9, "cavalry", "shu", 1, 0, 80]]
        assert result["terrain"] == {
            "forest": [[1, 0]],
            "water": [[2, 0]],
            "mountain": [[3, 4]],
        }
        assert "plain" not in result["terrain"]
        assert "success" not in result
        assert "visible_enemy_units" not in result
        assert "visible_terrain" not in result

    def test_faction_state_failure_is_left_intact(self):
        payload = {
            "success": False,
            "error_code": 2005,
            "error": "wrong faction",
            "units": [{"unit_id": 1}],
        }
        assert filters.filter_faction_state_result(payload) is payload

    def test_faction_state_result_false_is_left_intact(self):
        payload = {"result": False, "details": "query failed"}
        assert filters.filter_faction_state_result(payload) is payload


class TestObservationTrimming:
    def test_keeps_position_terrain_units_and_flags(self):
        result = filters.filter_observation_result(
            {
                "visible_environment": [
                    {
                        "position": {"col": 1, "row": 2},
                        "terrain": "hill",
                        "units": [{"unit_id": 3}],
                        "movement_accessibility": {"reachable": True, "cost": 9},
                        "attack_range_info": {"in_attack_range": False, "noise": 1},
                        "extra_noise": "dropped",
                    }
                ]
            }
        )
        tile = result["visible_environment"][0]
        assert tile == {
            "position": {"col": 1, "row": 2},
            "terrain": "hill",
            "units": [{"unit_id": 3}],
            "reachable": True,
            "attackable": False,
        }

    def test_handles_boolean_attack_range_info(self):
        result = filters.filter_observation_result(
            {"visible_environment": [{"position": {}, "attack_range_info": True}]}
        )
        assert result["visible_environment"][0]["attackable"] is True

    def test_does_not_mutate_the_input(self):
        original = {"unit_info": {"status": {"morale": "high"}}}
        filters.filter_observation_result(original)
        assert original["unit_info"]["status"] == {"morale": "high"}


class TestMoveFilter:
    def test_failure_with_suggestion_keeps_diagnosis(self):
        result = filters.filter_move_result(
            {
                "result": False,
                "details": "out of movement range",
                "current_movement_points": 1,
                "required_movement_points": 4,
                "suggested_action": "move closer",
                "verbose_noise": "x" * 100,
            }
        )
        assert result["details"] == "out of movement range"
        assert result["required_movement_points"] == 4
        assert "verbose_noise" not in result

    def test_success_drops_narration_but_keeps_outcome(self):
        result = filters.filter_move_result(
            {
                "result": True,
                "success": True,
                "message": "ok",
                "movement_descriptions": ["step 1", "step 2"],
                "action_status": {},
                "new_position": {"col": 1, "row": 1},
            }
        )
        assert result == {"result": True, "new_position": {"col": 1, "row": 1}}

    def test_failure_without_suggestion_is_left_intact(self):
        payload = {"result": False, "details": "something else"}
        assert filters.filter_move_result(payload) == payload


class TestAttackFilter:
    def test_success_keeps_combat_outcome(self):
        result = filters.filter_attack_result(
            {
                "result": True,
                "remaining_resources": {"ap": 1},
                "battle_summary": {
                    "attacker_info": {"unit_id": 1, "faction": "wei", "noise": "x"},
                    "target_info": {"unit_id": 2, "faction": "shu"},
                    "battle_result": {"damage_dealt": 30, "target_destroyed": False},
                },
                "tactical_info": {
                    "attack_was_effective": True,
                    "target_strength_percentage": 70,
                },
                "verbose": "dropped",
            }
        )
        assert result["remaining_resources"] == {"ap": 1}
        assert result["battle_summary"]["attacker_info"] == {
            "unit_id": 1,
            "faction": "wei",
        }
        assert result["battle_summary"]["battle_result"]["damage_dealt"] == 30
        assert result["attack_was_effective"] is True
        assert result["target_remaining_manpower"] == "70%"
        assert "verbose" not in result

    def test_failure_is_returned_whole_so_the_model_can_correct(self):
        payload = {"result": False, "details": "out of attack range", "hint": "move"}
        assert filters.filter_attack_result(payload) == payload


class TestToolResultRouting:
    def test_routes_by_action_name(self):
        result = filters.filter_tool_result(
            "perform_action",
            {"result": True, "success": True, "message": "ok"},
            {"action": "move"},
        )
        assert "success" not in result

    def test_action_name_is_case_insensitive(self):
        result = filters.filter_tool_result(
            "perform_action",
            {"result": True, "success": True},
            {"action": "  MOVE  "},
        )
        assert "success" not in result

    def test_unknown_action_passes_through(self):
        payload = {"anything": 1}
        assert filters.filter_tool_result(
            "perform_action", payload, {"action": "mystery"}
        ) == payload

    def test_non_dict_result_passes_through(self):
        assert filters.filter_tool_result("perform_action", "plain", {}) == "plain"

    def test_other_tools_are_not_filtered(self):
        payload = {"result": True, "success": True}
        assert filters.filter_tool_result("end_turn", payload, {}) == payload


class TestBooleanStringification:
    def test_converts_nested_booleans(self):
        assert filters.replace_booleans_with_strings(
            {"a": True, "b": [False, {"c": True}], "d": 1, "e": "x"}
        ) == {"a": "true", "b": ["false", {"c": "true"}], "d": 1, "e": "x"}

    def test_applied_only_when_requested(self):
        payload = {"result": True, "success": True}
        plain = filters.filter_tool_result(
            "perform_action", payload, {"action": "move"}, booleans_as_strings=False
        )
        stringified = filters.filter_tool_result(
            "perform_action", payload, {"action": "move"}, booleans_as_strings=True
        )
        assert plain["result"] is True
        assert stringified["result"] == "true"

    def test_unfiltered_actions_are_still_stringified(self):
        # GPT-OSS copies bare JSON booleans back as tool arguments.
        payload = {"result": True, "ok": False}
        result = filters.filter_tool_result(
            "perform_action",
            payload,
            {"action": "occupy"},
            booleans_as_strings=True,
        )
        assert result == {"result": "true", "ok": "false"}

    def test_non_perform_action_tools_are_stringified_when_requested(self):
        result = filters.filter_tool_result(
            "end_turn",
            {"success": True},
            {},
            booleans_as_strings=True,
        )
        assert result == {"success": "true"}


class TestDumpsForAgent:
    def test_keeps_nested_hexes_on_one_line(self):
        compact = {
            "state": "active",
            "fog": "active",
            "counts": [5, 5, 5],
            "units": [
                [
                    227,
                    "infantry",
                    1,
                    3,
                    100,
                    100,
                    2,
                    4,
                    1,
                    10,
                    2,
                    10,
                    [[-3, 2], [-3, 3], [-3, 4]],
                    [],
                ]
            ],
            "enemies": [],
        }
        text = filters.dumps_for_agent(compact)
        assert "\n" not in text
        assert "[[-3,2],[-3,3],[-3,4]]" in text
        assert ": " not in text
        assert ", " not in text

    def test_passes_through_already_serialized_strings(self):
        assert filters.dumps_for_agent("already") == "already"


class TestCompactDecoder:
    def test_decoder_lists_every_own_unit_column(self):
        decoder = filters.FACTION_STATE_COMPACT_DECODER
        assert "reachable" in decoder
        assert "attackable" in decoder
        assert "enemies" in decoder
        assert "terrain" in decoder
        assert "currently visible non-plain hexes only" in decoder
        assert "visible plain or currently unknown" in decoder
        assert "unlisted hexes are plain" not in decoder
        assert "not the raw ENV object" in decoder
        assert "state; fog" in decoder
