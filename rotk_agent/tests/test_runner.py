"""The expedition loop, without a hub."""

from types import SimpleNamespace

import pytest

from rotk_agent.core.runner import AgentRunner
from rotk_agent.modes.turn import TurnBasedMode
from rotk_agent.tests.support import RecordingBridge


def _bare_runner(factory, mode):
    runner = AgentRunner.__new__(AgentRunner)
    runner.agent_factory = factory
    runner.mode = mode
    runner.faction = "wei"
    runner.current_agent = None
    return runner


class TestPlayStopsOnUnreachable:
    @pytest.mark.asyncio
    async def test_llm_unreachable_does_not_relaunch(self):
        launches = []

        class Agent:
            def __init__(self):
                self.mode = SimpleNamespace(
                    opening_prompt=lambda faction: "go",
                    reset=lambda: None,
                )

            async def chat(self, prompt):
                launches.append(prompt)
                return {"success": False, "reason": "llm_unreachable"}

        await _bare_runner(Agent, Agent().mode).play()

        assert len(launches) == 1

    @pytest.mark.asyncio
    async def test_a_non_terminal_reason_relaunches_once_then_stops(self):
        launches = []

        class Agent:
            def __init__(self):
                self.mode = SimpleNamespace(
                    opening_prompt=lambda faction: "go",
                    reset=lambda: None,
                )

            async def chat(self, prompt):
                launches.append(1)
                if len(launches) == 1:
                    return {"success": False, "error": "Max iterations reached"}
                return {"success": True, "reason": "game_ended"}

        await _bare_runner(Agent, Agent().mode).play()

        assert len(launches) == 2


class TestPlayResetsSharedMode:
    @pytest.mark.asyncio
    async def test_a_shared_mode_is_reset_before_each_expedition(self):
        # The factory reused one TurnBasedMode; without reset(), last=5 made
        # the parked turn_start look already consumed and the agent waited
        # forever.
        mode = TurnBasedMode(RecordingBridge(), "wei")
        mode._last_turn_notified = 5
        mode._api_calls_this_turn = 9
        mode.open_gate("leftover")

        class Agent:
            def __init__(self):
                self.mode = mode

            async def chat(self, prompt):
                assert not mode._gate.is_set()
                assert mode._last_turn_notified == -1
                assert mode._api_calls_this_turn == 0
                return {"success": True, "reason": "game_ended"}

        await _bare_runner(Agent, mode).play()
