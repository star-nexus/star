"""The chat loop, driven by scripted replies instead of a model.

One loop now serves every model and both modes, so its control flow is the
single most valuable thing to pin down.
"""

import json

import pytest

from rotk_agent.adapters.fake import FakeAdapter
from rotk_agent.core.agent import TOOL_FORMAT_REMINDER, RoTKChatAgent
from rotk_agent.core.types import NormalizedReply, ToolCall
from rotk_agent.modes.realtime import RealTimeMode
from rotk_agent.tests.support import RecordingBridge


def build_agent(replies, bridge=None, mode=None, stats=None, **kwargs):
    """An agent whose model returns `replies` in order."""
    from rotk_agent.core.config import LLMConfig
    from rotk_agent.core.stats import ErrorStatsCollector

    stats = stats or ErrorStatsCollector()
    bridge = bridge if bridge is not None else RecordingBridge()
    config = LLMConfig(
        provider="fake", model_id="fake-model", api_key="EMPTY", base_url="fake://local"
    )
    return RoTKChatAgent(
        adapter=FakeAdapter(config, stats, script=replies),
        mode=mode or RealTimeMode(),
        bridge=bridge,
        stats=stats,
        faction="wei",
        system_prompt="you are a commander",
        **kwargs,
    )


def tool_call_reply(action="get_faction_state", params=None, call_id="call_1"):
    return NormalizedReply(
        text="首先包抄侧翼，然后集火。",
        tool_calls=[
            ToolCall(
                id=call_id,
                name="perform_action",
                arguments=json.dumps({"action": action, "params": params or {}}),
            )
        ],
        finish_reason="tool_calls",
    )


@pytest.fixture(autouse=True)
def _isolated_context(clean_remote_context):
    """Every test starts with an empty ENV status."""
    return clean_remote_context


class TestToolCallHandling:
    @pytest.mark.asyncio
    async def test_tool_result_is_appended_and_the_loop_continues(self):
        agent = build_agent([tool_call_reply()], max_iterations=2)
        await agent.chat("start")

        tool_messages = [m for m in agent.conversation_history if m.role == "tool"]
        assert len(tool_messages) == 1
        assert tool_messages[0].tool_call_id == "call_1"

    @pytest.mark.asyncio
    async def test_faction_state_history_is_compact_json(self):
        payload = {
            "success": True,
            "result": True,
            "state": "active",
            "fog": "active",
            "total_units": 1,
            "alive_units": 1,
            "actionable_units": 1,
            "units": [
                {
                    "unit_id": 227,
                    "unit_type": "infantry",
                    "position": {"col": 1, "row": 3},
                    "unit_status": {"current_count": 100, "max_count": 100},
                    "capabilities": {
                        "properties": {
                            "attack_range": 1,
                            "attack_power": 10,
                            "vision_range": 2,
                            "defense": 10,
                        },
                        "unit_resources": {
                            "remaining_action_points": 2,
                            "remaining_movement_points": 4,
                        },
                    },
                    "reachable": [
                        {"col": -3, "row": 2},
                        {"col": -3, "row": 3},
                        {"col": -3, "row": 4},
                    ],
                    "attackable": [],
                }
            ],
            "visible_enemy_units": [],
        }
        agent = build_agent(
            [tool_call_reply()],
            bridge=RecordingBridge(responses={"get_faction_state": payload}),
            max_iterations=2,
        )
        await agent.chat("start")

        tool_messages = [m for m in agent.conversation_history if m.role == "tool"]
        text = tool_messages[0].content
        assert "\n" not in text
        assert "[[-3,2],[-3,3],[-3,4]]" in text
        parsed = json.loads(text)
        assert parsed["units"][0][0] == 227
        assert parsed["units"][0][12] == {
            "reachable": [[-3, 2], [-3, 3], [-3, 4]],
            "attackable": [],
        }

    @pytest.mark.asyncio
    async def test_state_filter_a_omits_optional_channels(self):
        payload = {
            "success": True,
            "units": [
                {
                    "unit_id": 227,
                    "unit_type": "infantry",
                    "position": {"col": 1, "row": 3},
                    "unit_status": {"current_count": 100, "max_count": 100},
                    "capabilities": {
                        "properties": {
                            "attack_range": 1,
                            "attack_power": 10,
                            "vision_range": 2,
                            "defense": 10,
                        },
                        "unit_resources": {
                            "remaining_action_points": 2,
                            "remaining_movement_points": 4,
                        },
                    },
                    "reachable": [{"col": -3, "row": 2}],
                    "attackable": [9],
                }
            ],
            "visible_terrain": [{"col": 1, "row": 0, "type": "forest"}],
        }
        agent = build_agent(
            [tool_call_reply()],
            bridge=RecordingBridge(responses={"get_faction_state": payload}),
            max_iterations=2,
            state_filter="A",
        )
        await agent.chat("start")

        parsed = json.loads(
            [m for m in agent.conversation_history if m.role == "tool"][0].content
        )
        assert len(parsed["units"][0]) == 12
        assert "terrain" not in parsed

    def test_tool_schema_decoder_matches_the_state_filter(self):
        from rotk_agent.core.filters import FILTER_PROFILES

        agent = build_agent([], state_filter="A")
        tool = agent.tool_manager.tools["perform_action"]
        variant = next(
            v
            for v in tool.parameters["properties"]["params"]["oneOf"]
            if v.get("title") == "get_faction_state"
        )
        assert FILTER_PROFILES["A"].decoder in variant["description"]
        assert FILTER_PROFILES["F"].decoder not in variant["description"]
        assert "reachable" not in variant["description"]

    @pytest.mark.asyncio
    async def test_the_action_reaches_the_env(self):
        bridge = RecordingBridge()
        agent = build_agent(
            [tool_call_reply(action="move", params={"unit_id": 1})],
            bridge=bridge,
            max_iterations=2,
        )
        await agent.chat("start")

        assert "move" in bridge.actions

    @pytest.mark.asyncio
    async def test_move_off_reachable_is_recorded_but_still_sent(self):
        payload = {
            "success": True,
            "result": True,
            "units": [
                {
                    "unit_id": 231,
                    "unit_type": "infantry",
                    "position": {"col": -1, "row": -3},
                    "unit_status": {"current_count": 100, "max_count": 100},
                    "capabilities": {
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
                    "reachable": [{"col": -1, "row": -2}],
                    "attackable": [],
                }
            ],
        }
        bridge = RecordingBridge(
            responses={
                "get_faction_state": payload,
                "move": {"success": False, "result": False, "details": "No valid path"},
            }
        )
        agent = build_agent(
            [
                tool_call_reply(),
                tool_call_reply(
                    action="move",
                    params={
                        "unit_id": 231,
                        "target_position": {"col": 9, "row": 9},
                    },
                    call_id="call_2",
                ),
            ],
            bridge=bridge,
            max_iterations=3,
        )
        await agent.chat("start")

        assert agent.stats.reachable_mismatch == 1
        assert agent.stats.reachable_mismatch_enforced == 0
        assert agent.stats.spatial_awareness_error == 1
        assert "move" in bridge.actions
        event = agent.stats.reachable_mismatch_events[0]
        assert event["unit_id"] == 231
        assert event["target"] == {"col": 9, "row": 9}
        assert event["enforced"] is False

    @pytest.mark.asyncio
    async def test_enforce_reachable_blocks_the_env_and_returns_the_list(self):
        payload = {
            "success": True,
            "result": True,
            "units": [
                {
                    "unit_id": 231,
                    "unit_type": "infantry",
                    "position": {"col": -1, "row": -3},
                    "unit_status": {"current_count": 100, "max_count": 100},
                    "capabilities": {
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
                    "reachable": [{"col": -1, "row": -2}, {"col": 0, "row": -2}],
                    "attackable": [],
                }
            ],
        }
        bridge = RecordingBridge(responses={"get_faction_state": payload})
        agent = build_agent(
            [
                tool_call_reply(),
                tool_call_reply(
                    action="move",
                    params={
                        "unit_id": 231,
                        "target_position": {"col": 9, "row": 9},
                    },
                    call_id="call_2",
                ),
            ],
            bridge=bridge,
            max_iterations=3,
            enforce_reachable=True,
        )
        await agent.chat("start")

        assert "move" not in bridge.actions
        assert agent.stats.reachable_mismatch == 1
        assert agent.stats.reachable_mismatch_enforced == 1
        assert agent.stats.spatial_awareness_error == 0
        tool_messages = [m for m in agent.conversation_history if m.role == "tool"]
        rejection = json.loads(tool_messages[-1].content)
        assert rejection["reason"] == "not_in_reachable"
        assert rejection["details"] == "target not in latest reachable"
        assert "reachable" not in rejection
        assert "Legal hexes" not in rejection["details"]

    @pytest.mark.asyncio
    async def test_listed_reachable_hex_is_not_a_mismatch(self):
        payload = {
            "success": True,
            "result": True,
            "units": [
                {
                    "unit_id": 231,
                    "unit_type": "infantry",
                    "position": {"col": -1, "row": -3},
                    "unit_status": {"current_count": 100, "max_count": 100},
                    "capabilities": {
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
                    "reachable": [{"col": -1, "row": -2}],
                    "attackable": [],
                }
            ],
        }
        bridge = RecordingBridge(responses={"get_faction_state": payload})
        agent = build_agent(
            [
                tool_call_reply(),
                tool_call_reply(
                    action="move",
                    params={
                        "unit_id": 231,
                        "target_position": {"col": -1, "row": -2},
                    },
                    call_id="call_2",
                ),
            ],
            bridge=bridge,
            max_iterations=3,
            enforce_reachable=True,
        )
        await agent.chat("start")

        assert agent.stats.reachable_mismatch == 0
        assert "move" in bridge.actions

    @pytest.mark.asyncio
    async def test_pack_a_cannot_shadow_check_reachable(self):
        payload = {
            "success": True,
            "result": True,
            "units": [
                {
                    "unit_id": 231,
                    "unit_type": "infantry",
                    "position": {"col": -1, "row": -3},
                    "unit_status": {"current_count": 100, "max_count": 100},
                    "capabilities": {
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
                    "reachable": [{"col": -1, "row": -2}],
                    "attackable": [],
                }
            ],
        }
        bridge = RecordingBridge(responses={"get_faction_state": payload})
        agent = build_agent(
            [
                tool_call_reply(),
                tool_call_reply(
                    action="move",
                    params={
                        "unit_id": 231,
                        "target_position": {"col": 9, "row": 9},
                    },
                    call_id="call_2",
                ),
            ],
            bridge=bridge,
            max_iterations=3,
            state_filter="A",
            enforce_reachable=True,
        )
        await agent.chat("start")

        assert agent.stats.reachable_mismatch == 0
        assert "move" in bridge.actions

    @pytest.mark.asyncio
    async def test_malformed_arguments_are_counted_and_reported_back(self):
        reply = NormalizedReply(
            tool_calls=[ToolCall(id="c1", name="perform_action", arguments="{not json")],
            finish_reason="tool_calls",
        )
        agent = build_agent([reply], max_iterations=2)
        await agent.chat("start")

        assert agent.stats.tool_param_error == 1
        # The model must see the failure to be able to correct itself.
        tool_messages = [m for m in agent.conversation_history if m.role == "tool"]
        assert "error" in json.loads(tool_messages[0].content)

    @pytest.mark.asyncio
    async def test_double_encoded_params_are_decoded(self):
        bridge = RecordingBridge()
        reply = NormalizedReply(
            tool_calls=[
                ToolCall(
                    id="c1",
                    name="perform_action",
                    arguments=json.dumps(
                        {"action": "move", "params": json.dumps({"unit_id": 4})}
                    ),
                )
            ],
            finish_reason="tool_calls",
        )
        agent = build_agent([reply], bridge=bridge, max_iterations=2)
        await agent.chat("start")

        assert bridge.params_for("move") == [{"unit_id": 4}]

    @pytest.mark.asyncio
    async def test_env_rejection_is_classified_as_a_spatial_error(self):
        bridge = RecordingBridge(
            responses={
                "attack": {
                    "result": False,
                    "details": "Target out of attack range: distance 5, range 2",
                }
            }
        )
        agent = build_agent(
            [tool_call_reply(action="attack")], bridge=bridge, max_iterations=2
        )
        await agent.chat("start")

        assert agent.stats.spatial_awareness_error == 1
        assert agent.stats.tool_invalid_tool == 0

    @pytest.mark.asyncio
    async def test_shortest_path_mp_rejection_is_spatial_not_invalid_tool(self):
        bridge = RecordingBridge(
            responses={
                "move": {
                    "result": False,
                    "details": (
                        "Shortest path costs 5 MP; unit has 4 MP. "
                        "Farthest reachable hex along this path: (-1, -1)."
                    ),
                    "failure_reason": "insufficient_movement_points",
                    "reason": "insufficient_mp",
                    "suggested_action": {
                        "action": "move",
                        "params": {
                            "unit_id": 233,
                            "target_position": {"col": -1, "row": -1},
                        },
                    },
                }
            }
        )
        agent = build_agent(
            [tool_call_reply(action="move")], bridge=bridge, max_iterations=2
        )
        await agent.chat("start")

        assert agent.stats.spatial_awareness_error == 1
        assert agent.stats.tool_invalid_tool == 0

    @pytest.mark.asyncio
    async def test_other_rejections_are_classified_as_invalid_tool_use(self):
        bridge = RecordingBridge(
            responses={"move": {"result": False, "details": "Unit 42 not found"}}
        )
        agent = build_agent(
            [tool_call_reply(action="move")], bridge=bridge, max_iterations=2
        )
        await agent.chat("start")

        assert agent.stats.tool_invalid_tool == 1
        assert agent.stats.spatial_awareness_error == 0


class TestSpatialErrorClassification:
    """Pinned to MovementSystem reason codes and handler error text.

    Structured ``failure_reason`` / ``reason`` are checked independently so one
    non-spatial code cannot hide the other. Substrings cover attack/occupy
    wording that has no reason code. Resource exhaustion (AP / construction /
    skill / empty MP bar) stays in ``tool_invalid_tool``.
    """

    @staticmethod
    def classify(details):
        return RoTKChatAgent.is_spatial_awareness_error(
            {"success": False, "result": False, "details": details, "message": details}
        )

    @pytest.mark.parametrize(
        "details",
        [
            "No valid path to target position {'col': 3, 'row': 4}",
            "Insufficient movement points this turn: need 6, have 4.",
            "Shortest path costs 5 MP; unit has 4 MP. "
            "Farthest reachable hex along this path: (-1, -1).",
            "No nearby reachable positions this turn. Wait to recover movement points.",
            "Target out of attack range: distance 5, range 2",
            "Cannot occupy position (1, 2): too far from unit position (5, 5). "
            "Can only occupy current or adjacent positions.",
            "Target position became occupied during execution",
            "Position (3, 3) already controlled by faction wei",
        ],
    )
    def test_board_misreadings_count_as_spatial(self, details):
        assert self.classify(details)

    def test_both_unreachable_target_paths_agree(self):
        # The ENV rejects an unreachable target in two places depending on
        # whether terrain cost pushed it over the limit. It is the same mistake,
        # so it must not land in two different buckets.
        assert self.classify("No valid path to target position {'col': 0, 'row': 0}")
        assert self.classify("Insufficient movement points this turn: need 6, have 4.")
        assert self.classify(
            "Shortest path costs 5 MP; unit has 4 MP. "
            "Farthest reachable hex along this path: (-1, -1)."
        )

    def test_structured_insufficient_mp_counts_as_spatial_without_old_wording(self):
        assert RoTKChatAgent.is_spatial_awareness_error(
            {
                "result": False,
                "failure_reason": "insufficient_movement_points",
                "reason": "insufficient_mp",
                "details": "Shortest path costs 5 MP; unit has 4 MP.",
            }
        )

    def test_reason_is_checked_even_when_failure_reason_is_unrelated(self):
        assert RoTKChatAgent.is_spatial_awareness_error(
            {"result": False, "failure_reason": "other", "reason": "no_path"}
        )

    def test_ap_exhaustion_is_not_spatial_even_with_a_reason_field(self):
        assert not RoTKChatAgent.is_spatial_awareness_error(
            {
                "result": False,
                "reason": "insufficient_ap",
                "details": "Insufficient action points for attack: need 2, have 1",
            }
        )

    def test_handler_shaped_insufficient_mp_payload_is_spatial(self):
        # Exact keys LLMActionHandler._translate_move_result copies through.
        assert RoTKChatAgent.is_spatial_awareness_error(
            {
                "success": False,
                "result": False,
                "details": (
                    "Shortest path costs 5 MP; unit has 4 MP. "
                    "Farthest reachable hex along this path: (-1, -1)."
                ),
                "message": (
                    "Shortest path costs 5 MP; unit has 4 MP. "
                    "Farthest reachable hex along this path: (-1, -1)."
                ),
                "reason": "insufficient_mp",
                "failure_reason": "insufficient_movement_points",
            }
        )

    def test_empty_mp_bar_is_resource_not_spatial(self):
        assert not RoTKChatAgent.is_spatial_awareness_error(
            {
                "result": False,
                "reason": "no_mp",
                "details": "Unit has no movement points left: 0",
                "message": "Unit has no movement points left: 0",
            }
        )

    @pytest.mark.parametrize(
        "details",
        [
            "Insufficient action points for attack: need 2, have 1",
            "Insufficient construction points for fortify: need 1, have 0",
            "Insufficient skill points: need 1, have 0",
        ],
    )
    def test_resource_exhaustion_is_not_spatial(self, details):
        # Spending the turn's budget is an economy mistake, not a misread board.
        assert not self.classify(details)

    @pytest.mark.parametrize(
        "details",
        [
            "Unit 42 not found",
            "unit_id must be integer",
            "Missing action field",
            "Not shu's turn. Current turn: wei",
            "Cannot attack units of same faction",
        ],
    )
    def test_malformed_or_rule_errors_are_not_spatial(self, details):
        assert not self.classify(details)

    def test_a_non_dict_result_is_not_classified(self):
        assert not RoTKChatAgent.is_spatial_awareness_error("boom")


class TestToolCallsHiddenInContent:
    @pytest.mark.asyncio
    async def test_detected_counted_and_the_model_is_told_to_retry(self):
        reply = NormalizedReply(
            text='{"name": "perform_action", "arguments": {"action": "move"}}\n</tool_call>',
            finish_reason="stop",
        )
        agent = build_agent([reply], max_iterations=2)
        await agent.chat("start")

        assert agent.stats.tool_in_content == 1
        assert any(
            m.role == "user" and m.content == TOOL_FORMAT_REMINDER
            for m in agent.conversation_history
        )

    @pytest.mark.asyncio
    async def test_ordinary_prose_is_not_mistaken_for_a_tool_call(self):
        agent = build_agent(
            [NormalizedReply(text="我正在观察战场。", finish_reason="stop")],
            max_iterations=2,
        )
        await agent.chat("start")

        assert agent.stats.tool_in_content == 0

    def test_detector_reports_malformed_attempts(self):
        assert RoTKChatAgent.content_looks_like_tool_call('{"name": "x", broken}')

    def test_detector_ignores_plain_text(self):
        assert not RoTKChatAgent.content_looks_like_tool_call("no tools here")
        assert not RoTKChatAgent.content_looks_like_tool_call("")


class TestFinishReasons:
    @pytest.mark.asyncio
    async def test_length_gets_the_mode_specific_nudge(self):
        mode = RealTimeMode()
        agent = build_agent(
            [NormalizedReply(text="truncated", finish_reason="length")],
            mode=mode,
            max_iterations=2,
        )
        await agent.chat("start")

        assert any(
            m.role == "user" and m.content == mode.nudge_on_length()
            for m in agent.conversation_history
        )

    @pytest.mark.asyncio
    async def test_a_reply_with_no_action_gets_nudged_rather_than_resent_unchanged(self):
        # Without this the next iteration would resend identical history and get
        # the same non-answer back, spending budget for nothing.
        mode = RealTimeMode()
        agent = build_agent(
            [NormalizedReply(text="waiting", finish_reason="stop")],
            mode=mode,
            max_iterations=2,
        )
        await agent.chat("start")

        assert any(
            m.role == "user" and m.content == mode.nudge_on_stop()
            for m in agent.conversation_history
        )

    @pytest.mark.asyncio
    async def test_content_filter_ends_the_expedition_without_failing_it(self):
        agent = build_agent(
            [NormalizedReply(text="", finish_reason="content_filter")],
            max_iterations=5,
        )
        result = await agent.chat("start")

        assert result["success"] is True
        assert result["reason"] == "content_filter"

    @pytest.mark.asyncio
    async def test_an_unknown_finish_reason_fails_loudly(self):
        agent = build_agent(
            [NormalizedReply(text="", finish_reason="who_knows")], max_iterations=5
        )
        result = await agent.chat("start")

        assert result["success"] is False
        assert "who_knows" in result["error"]


class TestGameEnd:
    @pytest.mark.asyncio
    async def test_game_end_stops_the_run_and_reports_stats(
        self, clean_remote_context
    ):
        clean_remote_context.set_status({"game_ended": True})
        bridge = RecordingBridge()
        agent = build_agent([], bridge=bridge, max_iterations=5)

        result = await agent.chat("start")

        assert result["reason"] == "game_ended"
        assert result["success"] is True
        assert "report_llm_stats" in bridge.actions

    @pytest.mark.asyncio
    async def test_stats_are_reported_only_once(self):
        bridge = RecordingBridge()
        agent = build_agent([], bridge=bridge, max_iterations=1)

        await agent.report_llm_stats()
        await agent.report_llm_stats()

        assert bridge.actions.count("report_llm_stats") == 1

    @pytest.mark.asyncio
    async def test_reported_stats_include_every_error_family(self):
        bridge = RecordingBridge()
        agent = build_agent([], bridge=bridge)
        agent.stats.add_http_timeout()
        agent.stats.add_tool_param_error()
        agent.stats.add_spatial_awareness_error()

        await agent.report_llm_stats()

        payload = bridge.params_for("report_llm_stats")[0]
        assert payload["http_error_total"] == 1
        assert payload["toolcall_error_total"] == 1
        assert payload["spatial_awareness_error"] == 1
        assert payload["reachable_mismatch"] == 0
        assert payload["reachable_mismatch_enforced"] == 0
        assert payload["reachable_mismatch_events"] == []
        assert payload["error_breakdown"]["http"]["timeout"] == 1
        assert payload["api_stats"]["prompt_cache_hit_tokens"] == 0
        assert payload["api_stats"]["cache_hit_rate"] == 0.0


class TestTerminalErrors:
    @pytest.mark.asyncio
    async def test_account_balance_failure_stops_the_run(self):
        class BrokeAdapter(FakeAdapter):
            async def complete(self, messages, tools=None, instructions=""):
                raise RuntimeError("Insufficient balance for this account")

        from rotk_agent.core.config import LLMConfig
        from rotk_agent.core.stats import ErrorStatsCollector

        stats = ErrorStatsCollector()
        config = LLMConfig(provider="fake", model_id="m", api_key="k")
        agent = RoTKChatAgent(
            adapter=BrokeAdapter(config, stats),
            mode=RealTimeMode(),
            bridge=RecordingBridge(),
            stats=stats,
            faction="wei",
            max_iterations=5,
        )

        result = await agent.chat("start")

        assert result["reason"] == "account_balance_insufficient"
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_unreachable_endpoint_stops_instead_of_retrying_forever(self):
        import httpx

        class OfflineAdapter(FakeAdapter):
            async def complete(self, messages, tools=None, instructions=""):
                raise httpx.ConnectError("Cannot connect")

        from rotk_agent.core.config import LLMConfig
        from rotk_agent.core.stats import ErrorStatsCollector

        stats = ErrorStatsCollector()
        config = LLMConfig(provider="fake", model_id="m", api_key="k")
        agent = RoTKChatAgent(
            adapter=OfflineAdapter(config, stats),
            mode=RealTimeMode(),
            bridge=RecordingBridge(),
            stats=stats,
            faction="wei",
            max_iterations=50,
        )

        result = await agent.chat("start")

        # Previously this called sys.exit(1), killing the process mid-run.
        assert result["reason"] == "llm_unreachable"
        assert result["iterations"] == 1


class TestReasoningInHistory:
    @pytest.mark.asyncio
    async def test_reasoning_rides_on_the_assistant_message(self):
        # Not as a second assistant turn: consecutive assistant messages are
        # malformed for most chat APIs, and providers that require the reasoning
        # back (DeepSeek) want it as a field on the message that produced it.
        agent = build_agent(
            [
                NormalizedReply(
                    text="advancing", reasoning="首先包抄侧翼", finish_reason="stop"
                )
            ],
            max_iterations=1,
        )
        await agent.chat("start")

        assistant = [m for m in agent.conversation_history if m.role == "assistant"]
        assert len(assistant) == 1
        assert assistant[0].content == "advancing"
        assert assistant[0].reasoning == "首先包抄侧翼"

    @pytest.mark.asyncio
    async def test_a_reply_without_reasoning_leaves_the_field_empty(self):
        agent = build_agent(
            [NormalizedReply(text="advancing", finish_reason="stop")], max_iterations=1
        )
        await agent.chat("start")

        assistant = [m for m in agent.conversation_history if m.role == "assistant"]
        assert assistant[0].reasoning == ""


class TestHistoryManagement:
    @pytest.mark.asyncio
    async def test_trimming_keeps_the_framing_and_the_last_exchange(self):
        from rotk_agent.core.types import Message

        agent = build_agent([])
        agent.conversation_history = [
            Message(role="system", content="system"),
            Message(role="user", content="first user"),
            *[Message(role="user", content=f"filler {i}") for i in range(10)],
            Message(role="assistant", content="latest plan"),
            Message(role="tool", content="{}", tool_call_id="c1"),
        ]

        await agent.shrink_history(window=3)

        roles = [m.role for m in agent.conversation_history]
        assert roles[0] == "system"
        assert agent.conversation_history[1].content == "first user"
        # An assistant turn is never separated from the tool results answering it.
        assert agent.conversation_history[-2].content == "latest plan"
        assert agent.conversation_history[-1].role == "tool"

    @pytest.mark.asyncio
    async def test_history_is_trimmed_once_it_exceeds_the_mode_limit(self):
        mode = RealTimeMode()
        replies = [
            NormalizedReply(text="waiting", finish_reason="stop")
            for _ in range(mode.history_limit + 5)
        ]
        agent = build_agent(replies, mode=mode, max_iterations=mode.history_limit + 4)

        await agent.chat("start")

        assert len(agent.conversation_history) <= mode.history_limit + 2


class TestStrategyReporting:
    @pytest.mark.asyncio
    async def test_tactical_reasoning_is_pinged_to_the_env(self):
        bridge = RecordingBridge()
        agent = build_agent([], bridge=bridge)

        await agent.report_strategy("首先移动到侧翼，然后集火攻击敌方弓兵。")

        assert "strategy_ping" in bridge.actions
        assert bridge.params_for("strategy_ping")[0]["score"] == 1.0

    @pytest.mark.asyncio
    async def test_non_tactical_text_is_not_pinged(self):
        bridge = RecordingBridge()
        agent = build_agent([], bridge=bridge)

        await agent.report_strategy("你好。")

        assert "strategy_ping" not in bridge.actions

    @pytest.mark.asyncio
    async def test_pings_are_throttled(self):
        bridge = RecordingBridge()
        agent = build_agent([], bridge=bridge)
        text = "首先移动到侧翼，然后集火攻击。"

        await agent.report_strategy(text)
        await agent.report_strategy(text)

        assert bridge.actions.count("strategy_ping") == 1

    @pytest.mark.asyncio
    async def test_reasoning_counts_toward_the_score(self):
        # Nemotron and the Responses API return reasoning separately from the
        # answer; scoring only the answer would penalise them.
        bridge = RecordingBridge()
        agent = build_agent(
            [
                NormalizedReply(
                    text="ok",
                    reasoning="首先移动到侧翼，然后集火攻击。",
                    finish_reason="stop",
                )
            ],
            bridge=bridge,
            max_iterations=1,
        )
        await agent.chat("start")
        # The ping is fired as a background task; drain it.
        import asyncio

        await asyncio.sleep(0.05)

        assert "strategy_ping" in bridge.actions


class TestRegistration:
    @pytest.mark.asyncio
    async def test_the_agent_registers_its_model_once(self):
        bridge = RecordingBridge()
        agent = build_agent(
            [NormalizedReply(text="x", finish_reason="stop")],
            bridge=bridge,
            max_iterations=1,
        )

        await agent.chat("start")
        await agent.chat("start")

        assert bridge.actions.count("register_agent_info") == 1
        payload = bridge.params_for("register_agent_info")[0]
        assert payload["faction"] == "wei"
        assert payload["model_id"] == "fake-model"

    @pytest.mark.asyncio
    async def test_map_briefing_from_register_is_in_the_opening_prompt(self):
        bridge = RecordingBridge(
            responses={
                "register_agent_info": {
                    "success": True,
                    "map": {
                        "width": 15,
                        "height": 15,
                        "col_min": -7,
                        "col_max": 7,
                        "row_min": -7,
                        "row_max": 7,
                        "home_bases": {
                            "wei": {"col": 2, "row": 3, "kind": "home_base"},
                            "shu": {"col": -2, "row": -4, "kind": "home_base"},
                        },
                        "home_bases_meaning": "各阵营基地坐标",
                    },
                    "game_actions": {
                        "names": ["move", "attack", "get_faction_state", "occupy"],
                        "docs": {
                            "move": {
                                "description": "Move a unit",
                                "parameters": {
                                    "unit_id": {
                                        "type": "int",
                                        "required": True,
                                        "description": "Unit ID",
                                    },
                                    "target_position": {
                                        "type": "object",
                                        "required": True,
                                        "description": "Target position (col/row)",
                                        "properties": {
                                            "col": {"type": "int", "description": "column"},
                                            "row": {"type": "int", "description": "row"},
                                        },
                                    },
                                },
                            },
                            "occupy": {
                                "description": "Occupy a tile",
                                "parameters": {
                                    "unit_id": {
                                        "type": "int",
                                        "required": True,
                                        "description": "Unit ID",
                                    },
                                    "position": {
                                        "type": "object",
                                        "required": True,
                                        "description": "Tile to occupy",
                                        "properties": {
                                            "col": {"type": "int", "description": "column"},
                                            "row": {"type": "int", "description": "row"},
                                        },
                                    },
                                },
                            },
                        },
                    },
                }
            }
        )
        agent = build_agent(
            [NormalizedReply(text="x", finish_reason="stop")],
            bridge=bridge,
            max_iterations=1,
        )
        await agent.chat("start")
        assert agent.conversation_history[0].role == "system"
        system = agent.conversation_history[0].content
        assert system == agent.system_prompt
        assert "**魏 (wei) 基地 / home base**: `(2, 3)`" in system
        assert "**蜀 (shu) 基地 / home base**: `(-2, -4)`" in system
        assert "`move`" in system
        assert "Move a unit" not in system
        assert "Board (even-q offset): col -7..7, row -7..7." in system
        assert "start" == agent.conversation_history[1].content
        schema = agent.tool_manager.tools["perform_action"].parameters
        assert "occupy" in schema["properties"]["action"]["enum"]
        occupy = next(
            v for v in schema["properties"]["params"]["oneOf"] if v.get("title") == "occupy"
        )
        col = occupy["properties"]["position"]["properties"]["col"]
        assert col["minimum"] == -7
        assert col["maximum"] == 7
