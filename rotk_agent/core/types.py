"""Data types shared by every agent path.

`ToolCall` and `NormalizedReply` are the seam that lets one chat loop drive
both the Chat Completions and the Responses API: each adapter converts its
provider's wire format into these, so the loop never branches on provider.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class Message:
    """One conversation entry."""

    role: str  # "user", "assistant", "system", "tool"
    content: str
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None
    #: Reasoning the model emitted alongside `content`, kept beside it rather
    #: than merged in. Some providers require it back verbatim (DeepSeek rejects
    #: an assistant message carrying tool_calls without it), and each adapter
    #: decides whether and how to put it back on the wire.
    reasoning: str = ""


@dataclass
class ToolDefinition:
    """A tool the model may call, plus the coroutine that implements it."""

    name: str
    description: str
    parameters: Dict[str, Any]
    function: Callable


@dataclass
class ToolCall:
    """A single tool call, normalized across provider wire formats."""

    id: str
    name: str
    arguments: str  # raw JSON string, exactly as the provider emitted it

    def to_wire(self) -> Dict[str, Any]:
        """Chat-Completions-shaped dict for storing in assistant history."""
        return {
            "id": self.id,
            "type": "function",
            "function": {"name": self.name, "arguments": self.arguments},
        }


@dataclass
class NormalizedReply:
    """One LLM turn in a shape the chat loop consumes without branching."""

    text: str = ""
    tool_calls: List[ToolCall] = field(default_factory=list)
    finish_reason: str = "stop"  # stop | length | tool_calls | content_filter
    raw: Any = None
    # Set when the adapter produced reasoning as a distinct step (Nemotron's
    # two-stage flow, or a Responses API reasoning block). The loop persists it
    # so the next iteration can see what the model already worked out.
    reasoning: str = ""

    @property
    def scoreable_text(self) -> str:
        """Text the strategy rubric should read: reasoning plus the answer."""
        return "\n".join(part for part in (self.reasoning, self.text) if part)


__all__ = ["Message", "ToolDefinition", "ToolCall", "NormalizedReply"]
