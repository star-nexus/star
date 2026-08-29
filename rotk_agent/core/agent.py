"""The chat loop.

One loop serves every model and both modes. Provider differences live behind
`ModelAdapter`, mode differences behind `ModeStrategy`; what remains here is the
game-agnostic cycle: ask the model, run whatever tools it asked for, feed the
results back, and stop when the ENV says the game is over.
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from .bridge import EnvBridge, RemoteContext
from .console import console
from .errors import (
    RecoverableProviderError,
    create_error_details,
    is_account_balance_error,
    is_context_overflow_error,
    is_network_unreachable_error,
    log_error_to_file,
)
from .filters import (
    DEFAULT_FACTION_STATE_FILTER,
    dumps_for_agent,
    filter_tool_result,
    replace_booleans_with_strings,
    resolve_faction_state_filter,
)
from .reachable_guard import ReachableGuard
from .scoring import detect_strategy
from .stats import ErrorStatsCollector
from .tools import ToolManager, board_bounds_from_map, perform_action_tool
from ..profiles import apply_join_briefing_to_prompt
from .types import Message, NormalizedReply, ToolCall, ToolDefinition

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ..adapters.base import ModelAdapter
    from ..modes.base import ModeStrategy

AGENT_VERSION = "2.0.0"
STRATEGY_PING_INTERVAL_SECONDS = 2.0
STRATEGY_EVIDENCE_CHARS = 120
TRIM_TO_WINDOW = 10
OVERFLOW_TRIM_WINDOW = 40

TOOL_FORMAT_REMINDER = (
    "Note: You should not put the tool call information in the `content` field. "
    "You must follow the tool call format. Please try again."
)

# ENV rejection messages that mean the model misjudged the board rather than
# malformed its request. Prefer structured ``failure_reason`` / ``reason`` from
# MovementSystem; the substrings are a fallback for older wording still in
# attack/occupy errors.
SPATIAL_ERROR_PATTERNS = (
    # Movement: the target cannot be reached from here this turn.
    "no valid path",
    "insufficient movement points",
    "shortest path costs",
    "out of movement range",
    "no nearby reachable positions",
    # Attack: the target sits outside weapon reach.
    "out of attack range",
    # Occupy: the tile is not adjacent to the unit.
    "too far from unit position",
    # The tile is not free to enter or claim.
    "blocked by obstacles",
    "occupied",
    "already controlled by faction",
)

SPATIAL_FAILURE_REASONS = frozenset(
    {
        "insufficient_movement_points",
        "no_path",
        "insufficient_mp",
    }
)

# Deliberately *not* spatial: running out of action, construction, or skill
# points is a resource-budget mistake, not a misread of the board.

# A JSON object, optionally wrapped in the `</tool_call>` marker some models emit.
TEXT_TOOL_CALL_PATTERN = re.compile(
    r"\{[^}]*(?:\{[^}]*\}[^}]*)*\}(?:\s*\n?</tool_call>)?"
)


class RoTKChatAgent:
    """Drives one faction through an LLM."""

    def __init__(
        self,
        adapter: "ModelAdapter",
        mode: "ModeStrategy",
        bridge: EnvBridge,
        stats: ErrorStatsCollector,
        faction: str = "wei",
        system_prompt: str = "",
        agent_id: str = "agent_1",
        max_iterations: int = 1000,
        state_filter: str = DEFAULT_FACTION_STATE_FILTER,
        enforce_reachable: bool = False,
    ):
        self.adapter = adapter
        self.mode = mode
        self.bridge = bridge
        self.stats = stats
        self.faction = faction
        self.system_prompt = system_prompt
        self.agent_id = agent_id
        self.max_iterations = max_iterations
        self.faction_state_spec = resolve_faction_state_filter(state_filter)
        self.reachable_guard = ReachableGuard(enforce=enforce_reachable)

        self.tool_manager = ToolManager()
        self.conversation_history: List[Message] = []
        self.history_lock = asyncio.Lock()

        self._agent_registered = False
        self._stats_reported = False
        self._strategy_last_ping = 0.0
        self._map_briefing: Optional[Dict[str, Any]] = None
        self._game_actions: Optional[Dict[str, Any]] = None
        self._map_briefing_applied = False

        self._register_default_tools()

    def _register_default_tools(self) -> None:
        self.tool_manager.register_tool(
            perform_action_tool(
                self.bridge.perform_action,
                faction_state_spec=self.faction_state_spec,
            )
        )
        for tool in self.mode.tools(self):
            self.tool_manager.register_tool(tool)

    def _apply_join_tools(self) -> None:
        """Rebuild perform_action from the join map sheet and match verb list."""
        names = None
        docs = None
        payload = self._game_actions
        if isinstance(payload, dict):
            raw_names = payload.get("names")
            if isinstance(raw_names, list) and raw_names:
                names = raw_names
            if isinstance(payload.get("docs"), dict):
                docs = payload["docs"]
        self.tool_manager.register_tool(
            perform_action_tool(
                self.bridge.perform_action,
                names=names,
                docs=docs,
                board=board_bounds_from_map(self._map_briefing),
                faction_state_spec=self.faction_state_spec,
            )
        )

    def register_tool(self, tool: ToolDefinition) -> None:
        self.tool_manager.register_tool(tool)

    # ---- tool calls ----

    @staticmethod
    def content_looks_like_tool_call(content: str) -> bool:
        """Whether the model put a tool call in `content` instead of `tool_calls`.

        The parsed call itself is not usable — a model that ignores the tool
        protocol gets told to retry rather than having its text guessed at — so
        this only reports whether such a call appears to be present.
        """
        if not content:
            return False

        try:
            for match in TEXT_TOOL_CALL_PATTERN.findall(content.strip()):
                json_str = re.sub(r"\s*\n?</tool_call>.*$", "", match.strip())
                try:
                    payload = json.loads(json_str)
                except json.JSONDecodeError:
                    # Malformed, but it was clearly an attempt at a tool call.
                    console.print(
                        f"⚠️ Found malformed tool call in content: {json_str}",
                        style="red",
                    )
                    return True
                if isinstance(payload, dict) and payload.get("name"):
                    console.print(
                        f"📝 Found tool call in content: {payload.get('name')}",
                        style="cyan",
                    )
                    return True
        except Exception as e:
            console.print(f"⚠️ Error scanning content for tool calls: {e}", style="red")

        return False

    @staticmethod
    def is_spatial_awareness_error(result: Dict[str, Any]) -> bool:
        """Did the ENV reject this because the model misread the board?"""
        if not isinstance(result, dict):
            return False

        for key in ("failure_reason", "reason"):
            value = result.get(key)
            if isinstance(value, str) and value in SPATIAL_FAILURE_REASONS:
                return True

        for key in ("details", "message"):
            if key in result:
                text = str(result[key]).lower()
                if text and any(p in text for p in SPATIAL_ERROR_PATTERNS):
                    return True
        return False

    @staticmethod
    def _env_rejected(result: Any) -> bool:
        if not isinstance(result, dict):
            return False
        for key in ("success", "result"):
            value = result.get(key)
            if value is False or value == "false":
                return True
        return False

    def _maybe_observe_faction_state(
        self, call: ToolCall, arguments: Dict[str, Any], filtered: Any
    ) -> None:
        if call.name != "perform_action":
            return
        action = arguments.get("action")
        if not (isinstance(action, str) and action.strip().lower() == "get_faction_state"):
            return
        if not isinstance(filtered, dict) or "units" not in filtered:
            return
        if self._env_rejected(filtered):
            return
        self.reachable_guard.observe_faction_state(filtered)

    def _record_env_rejection(self, result: Any) -> None:
        """Attribute an ENV rejection to the right error class."""
        if not isinstance(result, dict):
            return
        if not (result.get("success") is False or result.get("result") is False):
            return

        if self.is_spatial_awareness_error(result):
            self.stats.add_spatial_awareness_error()
            console.print(
                f"📊 Spatial awareness error detected "
                f"(total: {self.stats.spatial_awareness_error})",
                style="yellow",
            )
            console.print(
                f"   └─ Error details: "
                f"{result.get('details', result.get('message', 'unknown'))}",
                style="dim yellow",
            )
        else:
            self.stats.add_tool_invalid_tool()
            console.print(
                f"📊 Tool call error: tool_invalid_tool "
                f"(total: {self.stats.tool_invalid_tool})",
                style="yellow",
            )

    async def _intercept_unreachable_move(
        self, call: ToolCall, arguments: Dict[str, Any]
    ) -> bool:
        """Shadow-check a move; optionally reject it before ENV sees it."""
        if call.name != "perform_action":
            return False
        mismatch = self.reachable_guard.check_move(arguments)
        if mismatch is None:
            return False

        enforced = self.reachable_guard.enforce
        event = mismatch.as_event(enforced=enforced)
        self.stats.add_reachable_mismatch(event)
        console.print(
            f"📊 Reachable mismatch: unit {mismatch.unit_id} -> "
            f"({mismatch.target[0]}, {mismatch.target[1]}) not in latest "
            f"reachable ({len(mismatch.reachable)} hexes) "
            f"[{'enforced' if enforced else 'shadow'}] "
            f"(total: {self.stats.reachable_mismatch})",
            style="yellow",
        )
        if not enforced:
            return False

        await self._append_tool_message(mismatch.tool_error(), call.id)
        return True

    async def _append_tool_message(self, content: Any, tool_call_id: str) -> None:
        async with self.history_lock:
            self.conversation_history.append(
                Message(
                    role="tool",
                    content=dumps_for_agent(content),
                    tool_call_id=tool_call_id,
                )
            )

    async def _execute_tool_call(self, call: ToolCall) -> None:
        """Run one tool call and record its result in the conversation."""
        console.print(
            f"── Executing tool '{call.name}' with arguments ──", style="magenta"
        )
        console.print(call.arguments, style="magenta", highlight=False)

        try:
            try:
                arguments = json.loads(call.arguments) if call.arguments else {}
            except json.JSONDecodeError as e:
                self.stats.add_tool_param_error()
                console.print(
                    f"📊 Tool call error: tool_param_error (arguments JSON decode "
                    f"failed, total: {self.stats.tool_param_error})",
                    style="yellow",
                )
                raise ValueError(
                    f"Failed to parse tool call arguments as JSON: {call.arguments}. "
                    f"Error: {e}"
                )

            # Some models double-encode the nested params object.
            if isinstance(arguments.get("params"), str):
                console.print(
                    "⚠️ 'params' is a string, trying to decode again...", style="yellow"
                )
                try:
                    arguments["params"] = json.loads(arguments["params"])
                except json.JSONDecodeError as e:
                    self.stats.add_tool_param_error()
                    console.print(
                        f"📊 Tool call error: tool_param_error (params JSON decode "
                        f"failed, total: {self.stats.tool_param_error})",
                        style="yellow",
                    )
                    raise ValueError(
                        f"LLM generated invalid JSON string for 'params': "
                        f"{arguments['params']}. Error: {e}"
                    )

            if await self.mode.intercept_tool_call(
                self, call.name, arguments, call.id
            ):
                return

            if await self._intercept_unreachable_move(call, arguments):
                return

            result = await self.tool_manager.execute_tool(call.name, arguments)
            self._record_env_rejection(result)
            self.mode.on_tool_result(self, call.name, arguments, result)

            filtered = filter_tool_result(
                call.name,
                result,
                arguments,
                booleans_as_strings=False,
                faction_state_spec=self.faction_state_spec,
            )
            self._maybe_observe_faction_state(call, arguments, filtered)
            if self.booleans_as_strings:
                filtered = replace_booleans_with_strings(filtered)
            console.print(f"── Tool result (filtered): {call.name} ──", style="magenta")
            # Pretty-print is for the operator only. History uses dumps_for_agent.
            console.print(
                json.dumps(filtered, indent=2, ensure_ascii=False),
                style="magenta",
                highlight=False,
                markup=False,
            )

            await self._append_tool_message(filtered, call.id)

        except Exception as e:
            console.print(
                f"Tool execution error during tool call '{call.name}': {e}", style="red"
            )
            # The model needs to see the failure to correct itself, so the error
            # goes back as the tool result rather than ending the run.
            await self._append_tool_message({"error": str(e)}, call.id)

    async def _handle_tool_calls(self, calls: List[ToolCall]) -> None:
        console.print(f"🔧 Handling {len(calls)} tool calls", style="cyan")

        # Only `perform_action` batches are safe to run concurrently; anything
        # else may depend on ordering (notably end_turn).
        parallel = len(calls) > 1 and all(c.name == "perform_action" for c in calls)

        if parallel:
            console.print("⚡ Running perform_action calls in parallel", style="cyan")
            await asyncio.gather(*(self._execute_tool_call(c) for c in calls))
        else:
            console.print("🔄 Running tool calls sequentially", style="cyan")
            for call in calls:
                await self._execute_tool_call(call)

    @property
    def booleans_as_strings(self) -> bool:
        """Whether tool results should render booleans as strings."""
        return getattr(self.adapter, "booleans_as_strings", False)

    # ---- strategy reporting ----

    async def report_strategy(self, text: str) -> None:
        """Score the model's reasoning and ping the ENV when it qualifies."""
        now = time.time()
        if now - self._strategy_last_ping < STRATEGY_PING_INTERVAL_SECONDS:
            return

        hit = detect_strategy(text)
        if not hit:
            return

        self._strategy_last_ping = now

        evidence = text.strip()
        if len(evidence) > STRATEGY_EVIDENCE_CHARS:
            evidence = evidence[: STRATEGY_EVIDENCE_CHARS - 3] + "..."

        try:
            await self.bridge.perform_action(
                "strategy_ping",
                {"faction": self.faction, "score": hit.score, "evidence": evidence},
            )
        except Exception as e:
            console.print(f"⚠️ strategy_ping failed: {e}", style="yellow")

    # ---- history ----

    async def shrink_history(self, window: int = 5) -> None:
        """Keep the framing plus the most recent exchange.

        Trimming starts at the last assistant message so that an assistant turn
        never gets separated from the tool results answering it.
        """
        async with self.history_lock:
            system_msgs = [m for m in self.conversation_history if m.role == "system"][:1]
            user_msgs = [m for m in self.conversation_history if m.role == "user"][:1]
            rest = [m for m in self.conversation_history if m.role != "system"]

            last_assistant = None
            for i in range(len(rest) - 1, -1, -1):
                if rest[i].role == "assistant":
                    last_assistant = i
                    break

            tail = rest[last_assistant:] if last_assistant is not None else rest[-window:]
            self.conversation_history = system_msgs + user_msgs + tail

    # ---- ENV reporting ----

    async def _register_agent_info(self) -> None:
        """Tell the ENV which model is playing this faction."""
        try:
            config = self.adapter.config
            result = await self.bridge.perform_action(
                "register_agent_info",
                {
                    "faction": self.faction,
                    "provider": config.provider,
                    "model_id": config.model_id,
                    "base_url": config.base_url or "unknown",
                    "agent_id": self.agent_id,
                    "version": AGENT_VERSION,
                    "note": f"Agent using {config.provider} via {self.adapter.name}",
                    "enable_thinking": config.enable_thinking,
                },
            )
            if isinstance(result, dict) and result.get("success"):
                if isinstance(result.get("map"), dict):
                    self._map_briefing = result["map"]
                if isinstance(result.get("game_actions"), dict):
                    self._game_actions = result["game_actions"]
                self._apply_join_tools()
                console.print(
                    f"✅ Agent registered: {self.faction} - "
                    f"{config.provider}:{config.model_id} "
                    f"(thinking: {config.enable_thinking})",
                    style="cyan",
                )
            else:
                console.print(
                    f"⚠️ Agent registration failed: "
                    f"{(result or {}).get('message', 'unknown error')}",
                    style="red",
                )
        except Exception as e:
            console.print(f"❌ Agent registration error: {e}", style="red")

    async def report_llm_stats(self) -> None:
        """Report API and error totals. Safe to call more than once."""
        if self._stats_reported:
            console.print(
                "⚠️ LLM stats already reported, skipping duplicate", style="yellow"
            )
            return
        self._stats_reported = True

        try:
            api_stats = self.stats.get_api_stats()
            payload = {
                "faction": self.faction,
                "api_stats": api_stats,
                "toolcall_error_total": self.stats.get_tool_call_gen_errors_total(),
                "http_error_total": self.stats.get_http_errors_total(),
                "spatial_awareness_error": self.stats.get_llm_capability_errors_total(),
                "reachable_mismatch": self.stats.reachable_mismatch,
                "reachable_mismatch_enforced": self.stats.reachable_mismatch_enforced,
                "reachable_mismatch_events": list(
                    self.stats.reachable_mismatch_events
                ),
                "error_breakdown": self.stats.get_error_breakdown(),
                "provider": self.adapter.config.provider,
                "model_id": self.adapter.config.model_id,
            }

            console.print(f"📊 Reporting LLM stats: {api_stats}", style="cyan")
            result = await self.bridge.perform_action("report_llm_stats", payload)

            if isinstance(result, dict) and result.get("success"):
                console.print("✅ LLM statistics reported successfully", style="cyan")
            else:
                console.print(
                    f"⚠️ LLM statistics report failed: "
                    f"{(result or {}).get('message', 'unknown error')}",
                    style="red",
                )
        except Exception as e:
            console.print(f"❌ LLM statistics report failed: {e}", style="red")

    async def stop(self) -> None:
        await self.report_llm_stats()
        await self.adapter.close()

    # ---- the loop ----

    @staticmethod
    def _game_ended(iteration: int) -> bool:
        try:
            status = RemoteContext.get_status() or {}
            if "game_ended" in status:
                console.print(
                    f"🔍 Status check (iteration {iteration}): {status}",
                    style="dim cyan",
                )
            return bool(status.get("game_ended", False))
        except Exception as e:
            console.print(f"⚠️ Error checking game status: {e}", style="red")
            return False

    async def _record_reply(self, reply: NormalizedReply) -> None:
        async with self.history_lock:
            # Reasoning rides alongside the answer rather than becoming a second
            # assistant turn: two consecutive assistant messages are malformed
            # for most chat APIs, and providers that need the reasoning back
            # want it as a field on the message that produced it.
            self.conversation_history.append(
                Message(
                    role="assistant",
                    content=reply.text,
                    tool_calls=[c.to_wire() for c in reply.tool_calls] or None,
                    reasoning=reply.reasoning,
                )
            )

    async def _nudge(self, content: str) -> None:
        async with self.history_lock:
            self.conversation_history.append(Message(role="user", content=content))

    async def chat(
        self, user_prompt: str, max_iterations: Optional[int] = None
    ) -> Dict[str, Any]:
        """Play until the game ends, the budget runs out, or the model stalls."""
        if max_iterations:
            self.max_iterations = max_iterations

        if not self._agent_registered:
            await self._register_agent_info()
            self._agent_registered = True

        if not self._map_briefing_applied:
            self.system_prompt = apply_join_briefing_to_prompt(
                self.system_prompt,
                map_briefing=self._map_briefing,
                game_actions=self._game_actions,
            )
            self._map_briefing_applied = True

        self.conversation_history = [
            Message(role="system", content=self.system_prompt),
            Message(role="user", content=user_prompt),
        ]

        recoverable_retried = False
        iterations = 0

        while iterations < self.max_iterations:
            iterations += 1

            if self._game_ended(iterations):
                console.print(
                    f"🏁 Game ended @iteration {iterations}, reporting stats and exiting",
                    style="yellow bold",
                )
                self.mode.on_game_ended(self)
                await self.stop()
                return {
                    "success": True,
                    "message": "Game ended, LLM stats reported",
                    "iterations": iterations,
                    "reason": "game_ended",
                }

            try:
                if not await self.mode.before_iteration(self):
                    continue

                console.print(
                    f"🔍 Conversation history length: {len(self.conversation_history)}",
                    style="cyan",
                )
                if len(self.conversation_history) > self.mode.history_limit:
                    await self.shrink_history(window=TRIM_TO_WINDOW)
                    console.print(
                        "🧹 History exceeded the limit and was trimmed", style="cyan"
                    )

                reply = await self.adapter.complete(
                    messages=self.conversation_history,
                    tools=self.tool_manager.get_tool_definitions(),
                    instructions=self.system_prompt,
                )
                await self.mode.after_model_call(self)
                await self._record_reply(reply)

                # Scored out of band: a slow ENV round trip must not stall play.
                asyncio.create_task(self.report_strategy(reply.scoreable_text))

                if not reply.tool_calls and self.content_looks_like_tool_call(reply.text):
                    self.stats.add_tool_in_content()
                    console.print(
                        f"📊 Tool call error: tool_in_content "
                        f"(total: {self.stats.tool_in_content})",
                        style="yellow",
                    )
                    await self._nudge(TOOL_FORMAT_REMINDER)
                    continue

                if reply.tool_calls:
                    console.print(
                        f"🔧 Handling tool calls @iteration {iterations}: "
                        f"{[c.name for c in reply.tool_calls]}",
                        style="cyan",
                    )
                    await self._handle_tool_calls(reply.tool_calls)
                    continue

                if reply.finish_reason == "length":
                    await self._nudge(self.mode.nudge_on_length())
                    continue

                if reply.finish_reason in ("stop", "tool_calls"):
                    nudge = self.mode.nudge_on_stop()
                    if nudge:
                        await self._nudge(nudge)
                    continue

                if reply.finish_reason == "content_filter":
                    console.print(
                        f"🛑 Content filtered @iteration {iterations}", style="red"
                    )
                    return {
                        "success": True,
                        "message": "Response blocked by content filter",
                        "iterations": iterations,
                        "reason": "content_filter",
                    }

                console.print(
                    f"Unexpected finish reason @iteration {iterations}: "
                    f"{reply.finish_reason}",
                    style="red",
                )
                return {
                    "success": False,
                    "error": f"Unexpected finish reason: {reply.finish_reason}",
                    "iterations": iterations,
                }

            except Exception as e:
                error_details = create_error_details(
                    e, iteration=iterations, function_name="RoTKChatAgent.chat"
                )

                if is_account_balance_error(e, error_details):
                    console.print(
                        "🛑 Account balance error detected, stopping agent",
                        style="red bold",
                    )
                    await self.stop()
                    return {
                        "success": False,
                        "error": str(e),
                        "error_details": error_details,
                        "iterations": iterations,
                        "reason": "account_balance_insufficient",
                    }

                if is_network_unreachable_error(e, error_details):
                    console.print(
                        "🛑 LLM endpoint unreachable, stopping agent to avoid "
                        "retrying forever.",
                        style="red bold",
                    )
                    await self.stop()
                    return {
                        "success": False,
                        "error": str(e),
                        "error_details": error_details,
                        "iterations": iterations,
                        "reason": "llm_unreachable",
                    }

                if is_context_overflow_error(e, error_details):
                    await self.shrink_history(window=OVERFLOW_TRIM_WINDOW)
                    console.print(
                        "🧹 Context overflow, history trimmed and continuing",
                        style="cyan",
                    )
                    continue

                if isinstance(e, RecoverableProviderError) and not recoverable_retried:
                    recoverable_retried = True
                    await self.shrink_history(window=TRIM_TO_WINDOW)
                    console.print(
                        "🔄 Provider rejected the request; trimmed history and "
                        "retrying once.",
                        style="yellow",
                    )
                    continue

                log_file = log_error_to_file(error_details, display_console=True)
                return {
                    "success": False,
                    "error": str(e),
                    "error_details": error_details,
                    "iterations": iterations,
                    "error_log_file": log_file,
                }

        await self.report_llm_stats()
        return {
            "success": False,
            "error": "Max iterations reached",
            "iterations": iterations,
        }


__all__ = ["RoTKChatAgent", "AGENT_VERSION"]
