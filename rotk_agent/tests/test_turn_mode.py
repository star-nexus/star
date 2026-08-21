"""The turn gate.

While the gate is closed the agent makes no model calls, so gate bugs are
expensive in both directions: a stuck-closed gate forfeits the game silently,
a stuck-open gate burns tokens playing out of turn.
"""

import asyncio
import json

import pytest

from rotk_agent.core.bridge import RemoteContext
from rotk_agent.modes.turn import (
    END_TURN_MISUSE_CORRECTION,
    TurnBasedMode,
)
from rotk_agent.tests.support import RecordingBridge
from rotk_agent.tests.test_agent_loop import build_agent, tool_call_reply
from rotk_agent.core.types import NormalizedReply, ToolCall


@pytest.fixture(autouse=True)
def _isolated_context(clean_remote_context):
    return clean_remote_context


def turn_start(faction="wei", turn_number=1):
    RemoteContext.set_status(
        {"turn_start": {"faction": faction, "turn_number": turn_number}}
    )


class TestGateLifecycle:
    def test_the_gate_starts_open(self):
        # The first turn may already belong to us, and a closed gate would wait
        # for a turn_start that already happened.
        mode = TurnBasedMode(RecordingBridge(), "wei")
        assert mode._gate.is_set()

    @pytest.mark.asyncio
    async def test_a_confirmed_end_turn_closes_the_gate(self):
        bridge = RecordingBridge(responses={"end_turn": {"success": True}})
        mode = TurnBasedMode(bridge, "wei")

        await mode._end_turn()

        assert not mode._gate.is_set()

    @pytest.mark.asyncio
    async def test_an_unconfirmed_end_turn_leaves_the_gate_open(self):
        # The ENV may have dropped the request; staying open lets us retry.
        bridge = RecordingBridge(responses={"end_turn": {"success": False}})
        mode = TurnBasedMode(bridge, "wei")

        await mode._end_turn()

        assert mode._gate.is_set()

    @pytest.mark.asyncio
    async def test_a_wrong_turn_rejection_closes_the_gate(self):
        # Otherwise an exhausted budget retries end_turn forever.
        bridge = RecordingBridge(
            responses={
                "end_turn": {"success": False, "details": "Not the current turn faction"}
            }
        )
        mode = TurnBasedMode(bridge, "wei")

        await mode._end_turn()

        assert not mode._gate.is_set()

    @pytest.mark.asyncio
    async def test_end_turn_clears_the_event_it_consumed(self):
        turn_start(turn_number=3)
        bridge = RecordingBridge(responses={"end_turn": {"success": True}})
        mode = TurnBasedMode(bridge, "wei")

        await mode._end_turn()

        assert "turn_start" not in (RemoteContext.get_status() or {})


class TestTurnStartConsumption:
    @pytest.mark.asyncio
    async def test_a_new_turn_reopens_the_gate_and_injects_a_hint(self):
        bridge = RecordingBridge()
        mode = TurnBasedMode(bridge, "wei")
        agent = build_agent([], bridge=bridge, mode=mode)
        mode.close_gate("test")
        turn_start(turn_number=4)

        assert await mode._consume_turn_start(agent)
        assert mode._gate.is_set()
        assert "第4回合" in agent.conversation_history[-1].content
        assert "turn_start_ack" in bridge.actions

    @pytest.mark.asyncio
    async def test_another_faction_turn_is_ignored(self):
        bridge = RecordingBridge()
        mode = TurnBasedMode(bridge, "wei")
        agent = build_agent([], bridge=bridge, mode=mode)
        mode.close_gate("test")
        turn_start(faction="shu", turn_number=1)

        assert not await mode._consume_turn_start(agent)
        assert not mode._gate.is_set()

    @pytest.mark.asyncio
    async def test_an_already_seen_turn_is_ignored(self):
        bridge = RecordingBridge()
        mode = TurnBasedMode(bridge, "wei")
        agent = build_agent([], bridge=bridge, mode=mode)
        mode.close_gate("test")
        turn_start(turn_number=2)
        await mode._consume_turn_start(agent)

        mode.close_gate("test again")
        # The same event replayed must not start a second turn.
        assert not await mode._consume_turn_start(agent)

    @pytest.mark.asyncio
    async def test_a_replay_while_playing_does_not_double_inject(self):
        bridge = RecordingBridge()
        mode = TurnBasedMode(bridge, "wei")
        agent = build_agent([], bridge=bridge, mode=mode)
        turn_start(turn_number=1)

        # The gate is open, so we are mid-turn already.
        assert not await mode._consume_turn_start(agent)
        assert agent.conversation_history == []

    @pytest.mark.asyncio
    async def test_a_new_turn_resets_the_call_budget(self):
        bridge = RecordingBridge()
        mode = TurnBasedMode(bridge, "wei", max_api_calls_per_turn=3)
        agent = build_agent([], bridge=bridge, mode=mode)
        mode._api_calls_this_turn = 3
        mode.close_gate("test")
        turn_start(turn_number=7)

        await mode._consume_turn_start(agent)

        assert mode._api_calls_this_turn == 0

    @pytest.mark.asyncio
    async def test_a_malformed_turn_number_is_ignored(self):
        bridge = RecordingBridge()
        mode = TurnBasedMode(bridge, "wei")
        agent = build_agent([], bridge=bridge, mode=mode)
        mode.close_gate("test")
        RemoteContext.set_status({"turn_start": {"faction": "wei", "turn_number": None}})

        assert not await mode._consume_turn_start(agent)


class TestWaiting:
    @pytest.mark.asyncio
    async def test_waiting_resumes_when_the_turn_arrives(self):
        bridge = RecordingBridge()
        mode = TurnBasedMode(bridge, "wei")
        agent = build_agent([], bridge=bridge, mode=mode)
        mode.close_gate("test")

        async def deliver():
            await asyncio.sleep(0.05)
            turn_start(turn_number=1)

        asyncio.create_task(deliver())
        assert await asyncio.wait_for(mode._wait_for_gate(agent), timeout=3)

    @pytest.mark.asyncio
    async def test_a_finished_game_stops_the_wait(self):
        # Never leave the loop parked on a game that is already over.
        bridge = RecordingBridge()
        mode = TurnBasedMode(bridge, "wei")
        agent = build_agent([], bridge=bridge, mode=mode)
        mode.close_gate("test")
        RemoteContext.set_status({"game_ended": True})

        assert not await asyncio.wait_for(mode._wait_for_gate(agent), timeout=3)

    @pytest.mark.asyncio
    async def test_game_end_force_opens_a_closed_gate(self):
        bridge = RecordingBridge()
        mode = TurnBasedMode(bridge, "wei")
        agent = build_agent([], bridge=bridge, mode=mode)
        mode.close_gate("test")

        mode.on_game_ended(agent)

        assert mode._gate.is_set()


class TestCallBudget:
    @pytest.mark.asyncio
    async def test_each_iteration_spends_one_call(self):
        bridge = RecordingBridge()
        mode = TurnBasedMode(bridge, "wei", max_api_calls_per_turn=5)
        agent = build_agent([], bridge=bridge, mode=mode)

        assert await mode.before_iteration(agent)
        assert mode._api_calls_this_turn == 1

    @pytest.mark.asyncio
    async def test_exhausting_the_budget_ends_the_turn_instead_of_calling(self):
        bridge = RecordingBridge(responses={"end_turn": {"success": True}})
        mode = TurnBasedMode(bridge, "wei", max_api_calls_per_turn=2)
        agent = build_agent([], bridge=bridge, mode=mode)

        assert await mode.before_iteration(agent)
        assert await mode.before_iteration(agent)
        # Third attempt is over budget.
        assert not await mode.before_iteration(agent)
        assert "end_turn" in bridge.actions
        assert not mode._gate.is_set()


class TestEndTurnMisuse:
    """Models routinely try `perform_action(action="end_turn")`."""

    @pytest.mark.asyncio
    async def test_it_is_intercepted_and_corrected(self):
        bridge = RecordingBridge()
        mode = TurnBasedMode(bridge, "wei")
        reply = NormalizedReply(
            tool_calls=[
                ToolCall(
                    id="c1",
                    name="perform_action",
                    arguments=json.dumps({"action": "end_turn", "params": {}}),
                )
            ],
            finish_reason="tool_calls",
        )
        agent = build_agent([reply], bridge=bridge, mode=mode, max_iterations=1)

        await agent.chat("start")

        # The turn did not actually end...
        assert "end_turn" not in bridge.actions
        assert mode._gate.is_set()
        # ...and the model was told how to do it properly.
        assert agent.conversation_history[-1].content == END_TURN_MISUSE_CORRECTION
        tool_reply = json.loads(agent.conversation_history[-2].content)
        assert tool_reply["success"] is False

    @pytest.mark.asyncio
    async def test_a_normal_action_is_not_intercepted(self):
        bridge = RecordingBridge()
        mode = TurnBasedMode(bridge, "wei")
        agent = build_agent(
            [tool_call_reply(action="move")],
            bridge=bridge,
            mode=mode,
            max_iterations=1,
        )

        await agent.chat("start")

        assert "move" in bridge.actions


class TestModeWiring:
    def test_turn_mode_registers_the_end_turn_tool(self):
        bridge = RecordingBridge()
        mode = TurnBasedMode(bridge, "wei")
        agent = build_agent([], bridge=bridge, mode=mode)

        names = {t.name for t in agent.tool_manager.get_tool_definitions()}
        assert names == {"perform_action", "end_turn"}

    def test_realtime_mode_has_no_end_turn_tool(self):
        agent = build_agent([])
        names = {t.name for t in agent.tool_manager.get_tool_definitions()}
        assert names == {"perform_action"}

    def test_turn_mode_selects_the_turn_prompt_family(self):
        from rotk_agent import profiles

        mode = TurnBasedMode(RecordingBridge(), "wei")
        assert profiles.load_prompt(mode.prompt_kind, "cn")

    def test_turn_mode_never_delays(self):
        # Delays exist for real-time animation races, which turn mode does not have.
        mode = TurnBasedMode(RecordingBridge(), "wei")
        assert mode.delay_policy("move", {}, {"result": True}) == 0.0
