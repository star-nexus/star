"""The provider seam.

An adapter owns everything about talking to one model API: request shape,
error taxonomy, and how to read tool calls back out. It hands the chat loop a
`NormalizedReply`, so the loop itself never branches on provider.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional

from ..core.config import LLMConfig
from ..core.errors import ProviderError, RecoverableProviderError
from ..core.stats import ErrorStatsCollector
from ..core.types import Message, NormalizedReply, ToolDefinition


class ModelAdapter(ABC):
    """Base class for provider adapters."""

    #: Human-readable name used in logs.
    name: str = "adapter"

    #: Render booleans in tool results as "true"/"false" strings. Needed by
    #: models that echo bare JSON booleans back as tool arguments.
    booleans_as_strings: bool = False

    def __init__(self, config: LLMConfig, stats: ErrorStatsCollector):
        self.config = config
        self.stats = stats

    @abstractmethod
    async def complete(
        self,
        messages: List[Message],
        tools: Optional[List[ToolDefinition]] = None,
        instructions: str = "",
    ) -> NormalizedReply:
        """Run one model turn.

        `instructions` is the system prompt. Adapters whose API takes a system
        message put it in the message list; those with a dedicated field use
        that instead.
        """

    async def close(self) -> None:
        """Release transport resources."""

    def describe(self) -> str:
        return f"{self.name}({self.config.provider}:{self.config.model_id})"


__all__ = [
    "ModelAdapter",
    "ProviderError",
    "RecoverableProviderError",
]
