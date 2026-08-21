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

    def test_faction_state_strips_noise_and_keeps_units(self):
        result = filters.filter_faction_state_result(
            {
                "success": True,
                "units": [
                    {
                        "unit_id": 7,
                        "unit_status": {"morale": "low", "current_count": 40},
                        "capabilities": {
                            "attack_points": 2,
                            "long_rest_resources": {},
                            "properties": {"attack_range": 1},
                        },
                        "available_skills": [],
                    }
                ],
            }
        )
        unit = result["units"][0]
        assert unit["unit_id"] == 7
        assert "morale" not in unit["unit_status"]
        assert unit["unit_status"]["current_count"] == 40
        assert "attack_points" not in unit["capabilities"]
        assert "long_rest_resources" not in unit["capabilities"]
        assert unit["capabilities"]["properties"] == {"attack_range": 1}
        assert "available_skills" not in unit
        assert "success" not in result


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
