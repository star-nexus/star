"""perform_action schema is built from the join payload, not from rotk_env."""

import ast
from pathlib import Path

from rotk_agent.core.tools import (
    FALLBACK_ACTION_NAMES,
    PERFORM_ACTION_SCHEMA,
    BoardBounds,
    board_bounds_from_map,
    perform_action_schema,
)


def _axis(schema, action_title, axis):
    for variant in schema["properties"]["params"]["oneOf"]:
        if variant.get("title") != action_title:
            continue
        for field in variant["properties"].values():
            nested = (field.get("properties") or {}) if isinstance(field, dict) else {}
            if axis in nested:
                return nested[axis]
    raise AssertionError(f"{axis} not found on {action_title}")


class TestNoEnvImport:
    def test_agent_package_does_not_import_rotk_env(self):
        root = Path("rotk_agent")
        offenders = []
        for path in root.rglob("*.py"):
            if "tests" in path.parts:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name == "rotk_env" or alias.name.startswith("rotk_env."):
                            offenders.append(f"{path}:{node.lineno} import {alias.name}")
                elif isinstance(node, ast.ImportFrom) and node.module:
                    if node.module == "rotk_env" or node.module.startswith("rotk_env."):
                        offenders.append(f"{path}:{node.lineno} from {node.module}")
        assert offenders == []


class TestFallbackSchema:
    def test_pre_join_enum_is_the_local_skirmish_three(self):
        assert FALLBACK_ACTION_NAMES == ("move", "attack", "get_faction_state")
        assert set(PERFORM_ACTION_SCHEMA["properties"]["action"]["enum"]) == set(
            FALLBACK_ACTION_NAMES
        )
        assert "end_turn" not in PERFORM_ACTION_SCHEMA["properties"]["action"]["enum"]

    def test_pre_join_coordinates_are_unclamped(self):
        col = _axis(PERFORM_ACTION_SCHEMA, "move", "col")
        assert "minimum" not in col
        assert "maximum" not in col

    def test_end_turn_is_never_in_the_perform_action_enum(self):
        schema = perform_action_schema(["move", "end_turn"])
        assert schema["properties"]["action"]["enum"] == ["move"]

    def test_get_faction_state_description_includes_compact_decoder(self):
        from rotk_agent.core.filters import FACTION_STATE_COMPACT_DECODER
        from rotk_agent.core.tools import FACTION_STATE_CALL_RULES

        variant = next(
            v
            for v in PERFORM_ACTION_SCHEMA["properties"]["params"]["oneOf"]
            if v.get("title") == "get_faction_state"
        )
        assert variant["description"] == (
            f"{FACTION_STATE_CALL_RULES} {FACTION_STATE_COMPACT_DECODER}"
        )


class TestJoinPayload:
    def test_docs_supply_param_shapes_for_new_verbs(self):
        schema = perform_action_schema(
            ["move", "occupy"],
            docs={
                "occupy": {
                    "description": "Occupy a territory tile",
                    "parameters": {
                        "unit_id": {
                            "type": "int",
                            "required": True,
                            "description": "Unit ID",
                        },
                        "position": {
                            "type": "object",
                            "required": True,
                            "description": "Tile to occupy (col/row)",
                            "properties": {
                                "col": {"type": "int", "description": "column"},
                                "row": {"type": "int", "description": "row"},
                            },
                        },
                    },
                }
            },
        )
        assert "occupy" in schema["properties"]["action"]["enum"]
        variants = schema["properties"]["params"]["oneOf"]
        assert len(variants) == 2
        occupy = next(v for v in variants if v.get("title") == "occupy")
        assert occupy["properties"]["position"]["properties"]["col"]["type"] == "integer"
        assert occupy["required"] == ["unit_id", "position"]

    def test_unknown_verbs_keep_typed_oneOf_variants(self):
        schema = perform_action_schema(
            ["move", "attack", "get_faction_state", "occupy"]
        )
        assert "occupy" in schema["properties"]["action"]["enum"]
        variants = schema["properties"]["params"]["oneOf"]
        assert len(variants) == 4
        occupy = next(v for v in variants if v.get("title") == "occupy")
        assert occupy == {
            "type": "object",
            "title": "occupy",
            "additionalProperties": True,
        }

    def test_empty_docs_parameters_fall_back_to_local_move_shape(self):
        schema = perform_action_schema(
            ["move"],
            docs={"move": {"description": "Move", "parameters": {}}},
        )
        move = next(
            v for v in schema["properties"]["params"]["oneOf"] if v.get("title") == "move"
        )
        assert "target_position" in move["properties"]
        assert move["description"].startswith("Move a unit")

    def test_docs_enum_and_bounds_are_kept(self):
        schema = perform_action_schema(
            ["get_faction_state"],
            docs={
                "get_faction_state": {
                    "parameters": {
                        "faction": {
                            "type": "string",
                            "required": True,
                            "description": "Your faction",
                            "enum": ["wei", "shu", "wu"],
                        }
                    }
                }
            },
        )
        faction = schema["properties"]["params"]["oneOf"][0]["properties"]["faction"]
        assert faction["enum"] == ["wei", "shu", "wu"]

    def test_env_payload_description_is_replaced_by_decoder(self):
        from rotk_agent.core.filters import FACTION_STATE_COMPACT_DECODER
        from rotk_agent.core.tools import FACTION_STATE_CALL_RULES

        schema = perform_action_schema(
            ["get_faction_state"],
            docs={
                "get_faction_state": {
                    "description": (
                        "Your army (full detail, owner/commandable) plus "
                        "visible_enemy_units"
                    ),
                    "parameters": {
                        "faction": {
                            "type": "string",
                            "required": True,
                            "description": "Your faction",
                        }
                    },
                }
            },
        )
        description = schema["properties"]["params"]["oneOf"][0]["description"]
        assert description == (
            f"{FACTION_STATE_CALL_RULES} {FACTION_STATE_COMPACT_DECODER}"
        )
        assert "owner/commandable" not in description
        assert "visible_enemy_units" not in description

    def test_non_string_names_are_dropped(self):
        schema = perform_action_schema(["move", 123, None, ""])  # type: ignore[list-item]
        assert schema["properties"]["action"]["enum"] == ["move"]

    def test_board_bounds_clamp_col_and_row(self):
        board = BoardBounds(col_min=-3, col_max=4, row_min=-5, row_max=6)
        schema = perform_action_schema(["move"], board=board)
        col = _axis(schema, "move", "col")
        row = _axis(schema, "move", "row")
        assert col["minimum"] == -3
        assert col["maximum"] == 4
        assert row["minimum"] == -5
        assert row["maximum"] == 6
        assert "range -3 to 4" in col["description"]


class TestBoardBoundsFromMap:
    def test_prefers_explicit_axis_fields(self):
        bounds = board_bounds_from_map(
            {
                "width": 99,
                "height": 99,
                "col_min": -2,
                "col_max": 8,
                "row_min": -4,
                "row_max": 1,
            }
        )
        assert bounds == BoardBounds(-2, 8, -4, 1)

    def test_centered_width_height_matches_map_files(self):
        bounds = board_bounds_from_map({"width": 15, "height": 15})
        assert bounds == BoardBounds(-7, 7, -7, 7)

    def test_missing_sheet_returns_none(self):
        assert board_bounds_from_map(None) is None
        assert board_bounds_from_map({}) is None

    def test_bool_is_not_an_axis_bound(self):
        # isinstance(True, int) is True; a malformed sheet must not clamp to 0/1.
        assert board_bounds_from_map(
            {"col_min": True, "col_max": True, "row_min": True, "row_max": True}
        ) is None
