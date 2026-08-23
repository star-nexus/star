"""The mode seam.

A mode decides *when* the agent is allowed to act and how it is paced. It hooks
into the chat loop rather than duplicating it, which is what the separate
`*_turn.py` scripts used to do.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from ..core.bridge import DelayPolicy
from ..core.delays import calculate_action_delay
from ..core.types import ToolDefinition

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ..core.agent import RoTKChatAgent


class ModeStrategy(ABC):
    """Hooks the chat loop calls at fixed points in each iteration."""

    #: Identifier used in logs and on the command line.
    name: str = "mode"

    #: Which prompt family to load: "realtime" or "turn".
    prompt_kind: str = "realtime"

    #: Trim the conversation once it exceeds this many messages.
    history_limit: int = 100

    #: How long to wait after an ENV action before acting again.
    delay_policy: DelayPolicy = staticmethod(calculate_action_delay)

    def tools(self, agent: "RoTKChatAgent") -> List[ToolDefinition]:
        """Extra tools this mode contributes beyond `perform_action`."""
        return []

    async def before_iteration(self, agent: "RoTKChatAgent") -> bool:
        """Return False to skip this iteration without calling the model."""
        return True

    async def after_model_call(self, agent: "RoTKChatAgent") -> None:
        """Runs immediately after each model call returns."""

    def on_game_ended(self, agent: "RoTKChatAgent") -> None:
        """Runs once the ENV reports the game is over, before shutdown."""

    def on_tool_result(
        self,
        agent: "RoTKChatAgent",
        name: str,
        arguments: Dict[str, Any],
        result: Any,
    ) -> None:
        """Runs after a tool returns, before the result is written to history."""

    def reset(self) -> None:
        """Clear per-expedition mutable state.

        The runner calls this at the start of every expedition so a shared
        mode instance cannot leak turn-gate bookkeeping into the next launch.
        Stateless modes leave this as a no-op.
        """

    async def intercept_tool_call(
        self,
        agent: "RoTKChatAgent",
        name: str,
        arguments: Dict[str, Any],
        tool_call_id: str,
    ) -> bool:
        """Handle a tool call specially. Return True if it was handled here."""
        return False

    @abstractmethod
    def opening_prompt(self, faction: str) -> str:
        """The first user message, framing how this mode should be played."""

    @abstractmethod
    def nudge_on_length(self) -> str:
        """What to tell the model when it hit the output token limit."""

    @abstractmethod
    def nudge_on_stop(self) -> Optional[str]:
        """What to tell the model when it replied without acting.

        Without a nudge the next iteration would resend an unchanged history and
        get the same non-answer back, spending budget for nothing.
        """


__all__ = ["ModeStrategy"]
