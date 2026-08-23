"""Turn-based mode: the agent may only act during its own turn.

The turn gate is the whole mechanism. It starts open, closes when the ENV
confirms `end_turn`, and reopens when a `turn_start` for this faction arrives.
While it is closed the agent makes no model calls at all, so a waiting agent
costs nothing.

A per-turn call budget backs that up: a model that never chooses to end its
turn gets ended for it, instead of spinning until the game clock runs out.
"""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from ..core.bridge import EnvBridge, RemoteContext
from ..core.console import console
from ..core.delays import no_delay
from ..core.types import Message, ToolDefinition
from ..core.tools import end_turn_tool
from ..profiles import DEFAULT_LANGUAGE, faction_info
from .base import ModeStrategy

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ..core.agent import RoTKChatAgent

DEFAULT_MAX_API_CALLS_PER_TURN = 25
GATE_POLL_SECONDS = 0.5

LENGTH_NUDGE = (
    "Note: The game is turn-based, you should think carefully and give the "
    "critical information of your strategy."
)

STOP_NUDGE = (
    "Note: You are the commander. You decide the strategy and the action. Do not "
    "ask for confirmation. Once you know where the enemy is, move your units into "
    "range and attack. When you are done for this turn, call end_turn."
)

END_TURN_MISUSE_MESSAGE = (
    "❌ 工具使用错误！'end_turn' 是一个独立的工具，不能通过 'perform_action' 调用。\n"
    "正确的调用方式是：\n"
    '{"name": "end_turn", "arguments": {}}\n\n'
    "请直接使用 end_turn 工具来结束回合。"
)

END_TURN_MISUSE_CORRECTION = (
    "请注意：你刚才试图通过 perform_action 调用 end_turn，这是错误的。\n"
    "end_turn 是一个独立的工具。正确的调用方式是：\n"
    '{"name": "end_turn", "arguments": {}}\n\n'
    "请直接使用 end_turn 工具来结束当前回合。"
)

OPENING_PROMPT_CN = (
    "**当前配置**:\n"
    "- **我方势力**: {own_name} ({faction})\n"
    "- **主要敌人**: {enemy_name} ({enemy})\n"
    "- 你在使用工具的时候，建议附加简短的决策说明，以增加决策分指标。\n"
    "- 了解当前敌我态势，思考对战策略，调动你的所有unit消灭所有敌人。\n"
    "- 本回合行动完毕后，调用 end_turn 结束回合。"
)

OPENING_PROMPT_EN = (
    "**Current setup**:\n"
    "- **Our faction**: {own_name} ({faction})\n"
    "- **Main enemy**: {enemy_name} ({enemy})\n"
    "- When using tools, add a short rationale so the strategy score can register.\n"
    "- Read the board, pick a plan, and use every unit to eliminate all enemies.\n"
    "- When you are done for this turn, call end_turn."
)

TURN_START_HINT_CN = "你的回合开始（第{turn}回合）。所有资源已恢复。请开始行动。"
TURN_START_HINT_EN = (
    "Your turn has started (turn {turn}). All resources have been restored. Begin acting."
)


def is_not_our_turn_rejection(response: Any) -> bool:
    """ENV said this faction does not own the turn."""
    if not isinstance(response, dict):
        return False
    message = str(response.get("details") or response.get("message") or "")
    return "current turn" in message.lower()


class TurnBasedMode(ModeStrategy):
    """Gate model calls on turn ownership."""

    name = "turn_based"
    prompt_kind = "turn"
    history_limit = 100
    delay_policy = staticmethod(no_delay)

    def __init__(
        self,
        bridge: EnvBridge,
        faction: str,
        max_api_calls_per_turn: int = DEFAULT_MAX_API_CALLS_PER_TURN,
        language: str = DEFAULT_LANGUAGE,
    ):
        self.bridge = bridge
        self.faction = faction
        self.max_api_calls_per_turn = max_api_calls_per_turn
        self.language = language

        self._gate = asyncio.Event()
        self.reset()

    def reset(self) -> None:
        """Start closed. A leftover open gate would burn tokens out of turn.

        The first `turn_start` is either already in `RemoteContext` or the ENV
        will resend it until we ACK, so waiting is safe for every faction.
        """
        self._gate.clear()
        self._last_turn_notified = -1
        self._api_calls_this_turn = 0
        self._log_gate("RESET (closed)")

    # ---- gate plumbing ----

    def _log_gate(self, action: str) -> None:
        state = "OPEN" if self._gate.is_set() else "CLOSED"
        console.print(f"🚪 Turn gate {action}: {state}", style="cyan")

    def open_gate(self, reason: str = "manual") -> None:
        self._gate.set()
        self._log_gate(f"OPENED ({reason})")

    def close_gate(self, reason: str = "manual") -> None:
        self._gate.clear()
        self._log_gate(f"CLOSED ({reason})")

    async def _consume_turn_start(
        self, agent: "RoTKChatAgent", context: str = ""
    ) -> bool:
        """Open the gate if a newer `turn_start` for our faction has arrived."""
        try:
            status = RemoteContext.get_status() or {}
            event = status.get("turn_start")
            if not isinstance(event, dict):
                return False

            event_faction = str(event.get("faction", "")).lower()
            turn_number = event.get("turn_number")

            if event_faction != str(self.faction).lower():
                if event_faction and context:
                    console.print(
                        f"⏳ Detected turn_start for other faction: {event_faction} [{context}]",
                        style="dim yellow",
                    )
                return False

            if not isinstance(turn_number, int):
                return False

            if turn_number <= self._last_turn_notified:
                if context:
                    console.print(
                        f"⏳ Detected turn_start but not newer "
                        f"(evt_turn={turn_number}, last={self._last_turn_notified}) [{context}]",
                        style="dim yellow",
                    )
                return False

            if self._gate.is_set():
                # We are not waiting, so this is a replay of an event we already
                # acted on. Acting again would inject a duplicate turn hint.
                console.print(
                    f"⚠️ Found turn_start but gate is already open - likely a stale "
                    f"event (evt_turn={turn_number}, last={self._last_turn_notified}) [{context}]",
                    style="yellow",
                )
                return False

            template = (
                TURN_START_HINT_EN if self.language == "en" else TURN_START_HINT_CN
            )
            hint = template.format(turn=turn_number)
            async with agent.history_lock:
                agent.conversation_history.append(Message(role="user", content=hint))

            self._last_turn_notified = turn_number
            self._api_calls_this_turn = 0
            console.print(
                f"📣 Injected turn_start hint for faction={self.faction}, "
                f"turn={turn_number} [{context}]",
                style="green",
            )
            self.open_gate(f"turn_start ({context})")

            # Acknowledge so the ENV stops resending this turn_start.
            try:
                await self.bridge.send_turn_start_ack(self.faction, turn_number)
            except Exception as e:
                console.print(f"⚠️ turn_start_ack send failed: {e}", style="yellow")

            return True

        except Exception as e:
            console.print(
                f"⚠️ Turn-start processing failed [{context}]: {e}", style="yellow"
            )
            return False

    async def _wait_for_gate(self, agent: "RoTKChatAgent") -> bool:
        """Block until it is our turn. False means stop waiting entirely."""
        if self._gate.is_set():
            return True

        console.print(
            "⏸️ Waiting for next turn_start to resume LLM calls...", style="yellow"
        )
        while not self._gate.is_set():
            try:
                if await self._consume_turn_start(agent, "wait_gate"):
                    break

                status = RemoteContext.get_status() or {}
                if status.get("game_ended", False):
                    # Never leave the loop parked on a game that is over.
                    self.open_gate("game_ended - emergency (wait)")
                    return False
            except Exception as e:
                console.print(
                    f"⚠️ Polling status while waiting failed: {e}", style="yellow"
                )

            try:
                await asyncio.wait_for(self._gate.wait(), timeout=GATE_POLL_SECONDS)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                console.print(
                    f"⚠️ Waiting for turn_start interrupted: {e}", style="yellow"
                )
                return False

        console.print("▶️ Turn started. Resuming LLM calls.", style="green")
        return True

    # ---- the end_turn tool ----

    async def _end_turn(self) -> Dict[str, Any]:
        """End our turn, closing the gate only once the ENV confirms."""
        response = await self.bridge.send_end_turn(self.faction)

        confirmed = isinstance(response, dict) and (
            response.get("success") is True or response.get("result") is True
        )

        if confirmed:
            self.close_gate("end_turn")
            # Drop the consumed turn_start so it cannot be replayed.
            try:
                status = RemoteContext.get_status() or {}
                if "turn_start" in status:
                    status.pop("turn_start", None)
                    RemoteContext.set_status(status)
                    console.print(
                        "🗑️ Cleared old turn_start event from RemoteContext",
                        style="dim cyan",
                    )
            except Exception as e:
                console.print(
                    f"⚠️ Failed to clear turn_start event: {e}", style="yellow"
                )
            console.print(
                "⏹️ Turn ended. Pausing LLM calls until next turn_start...",
                style="yellow",
            )
            return response

        # The ENV refused, most often because it is not our turn. Closing the
        # gate anyway is deliberate: leaving it open lets an exhausted budget
        # retry end_turn forever.
        if is_not_our_turn_rejection(response):
            message = str(response.get("details") or response.get("message") or "")
            console.print(
                f"⏹️ ENV says it is not our turn ({message}); closing gate to wait.",
                style="yellow",
            )
            self.close_gate("end_turn rejected - not our turn")

        return response

    def on_tool_result(
        self,
        agent: "RoTKChatAgent",
        name: str,
        arguments: Dict[str, Any],
        result: Any,
    ) -> None:
        """A move/attack rejected as 'not your turn' means we should stop calling."""
        if not isinstance(result, dict):
            return
        failed = result.get("success") is False or result.get("result") is False
        if failed and is_not_our_turn_rejection(result):
            self.close_gate("action rejected - not our turn")

    def tools(self, agent: "RoTKChatAgent") -> List[ToolDefinition]:
        return [end_turn_tool(self._end_turn)]

    # ---- loop hooks ----

    async def before_iteration(self, agent: "RoTKChatAgent") -> bool:
        if not await self._wait_for_gate(agent):
            return False

        if self._api_calls_this_turn >= self.max_api_calls_per_turn:
            console.print(
                f"🎫 Per-turn API call budget exhausted "
                f"({self.max_api_calls_per_turn}), triggering end_turn...",
                style="yellow",
            )
            try:
                await self._end_turn()
            except Exception as e:
                console.print(f"⚠️ end_turn (budget) failed: {e}", style="yellow")
            return False

        self._api_calls_this_turn += 1
        return True

    def on_game_ended(self, agent: "RoTKChatAgent") -> None:
        if not self._gate.is_set():
            self.open_gate("game_ended - emergency")

    async def intercept_tool_call(
        self,
        agent: "RoTKChatAgent",
        name: str,
        arguments: Dict[str, Any],
        tool_call_id: str,
    ) -> bool:
        """Correct the common mistake of calling end_turn via perform_action."""
        if name != "perform_action" or (arguments or {}).get("action") != "end_turn":
            return False

        error = {
            "success": False,
            "error": "Invalid tool usage",
            "message": END_TURN_MISUSE_MESSAGE,
        }
        async with agent.history_lock:
            agent.conversation_history.append(
                Message(
                    role="tool",
                    content=json.dumps(error, ensure_ascii=False),
                    tool_call_id=tool_call_id,
                )
            )
            agent.conversation_history.append(
                Message(role="user", content=END_TURN_MISUSE_CORRECTION)
            )
        return True

    def opening_prompt(self, faction: str) -> str:
        own = faction_info(faction)
        enemy = faction_info(own["enemy"])
        template = OPENING_PROMPT_EN if self.language == "en" else OPENING_PROMPT_CN
        return template.format(
            own_name=own["name"],
            faction=faction,
            enemy_name=enemy["name"],
            enemy=own["enemy"],
        )

    def nudge_on_length(self) -> str:
        return LENGTH_NUDGE

    def nudge_on_stop(self) -> Optional[str]:
        return STOP_NUDGE


__all__ = [
    "TurnBasedMode",
    "DEFAULT_MAX_API_CALLS_PER_TURN",
    "is_not_our_turn_rejection",
]
