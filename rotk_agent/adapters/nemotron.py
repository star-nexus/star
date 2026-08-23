"""Nemotron's two-stage reasoning flow.

Nemotron's chat template expects reasoning to arrive in a closed `<think>`
block before the model commits to an answer. Doing that in one call lets the
reasoning eat the whole token budget, so the adapter splits it: a budgeted
thinking call with no tools, then an answering call that sees the reasoning and
has the tools available.

This lives in the adapter, not the chat loop, because it is a property of the
model family rather than of the game mode.
"""

from __future__ import annotations

from typing import List, Optional

from ..core.console import console
from ..core.types import Message, NormalizedReply, ToolDefinition
from .chat_completions import ChatCompletionsAdapter

DEFAULT_THINKING_BUDGET = 256
MIN_STAGE_TOKENS = 16
THINKING_TEMPERATURE = 0.4
THINKING_TOP_P = 0.7


def ensure_closed_think_block(reasoning: str) -> str:
    """Close the `<think>` block so the chat template stays well formed."""
    if not reasoning:
        return "</think>\n\n"
    text = reasoning
    if "</think>" not in text:
        if not text.endswith("."):
            text = f"{text}."
        text = f"{text}\n</think>\n\n"
    return text


class NemotronAdapter(ChatCompletionsAdapter):
    """Chat completions, called twice: think, then answer."""

    name = "nemotron"

    def __init__(
        self,
        config,
        stats,
        thinking_budget: int = DEFAULT_THINKING_BUDGET,
        carry_reasoning: bool = True,
    ):
        super().__init__(config, stats, carry_reasoning=carry_reasoning)
        self.thinking_budget = thinking_budget

    def _stage_budgets(self) -> tuple[int, int]:
        """Split the token budget so the answer stage always has room."""
        total = self.config.max_tokens or 512
        thinking = min(
            max(MIN_STAGE_TOKENS, self.thinking_budget),
            max(MIN_STAGE_TOKENS, total - MIN_STAGE_TOKENS),
        )
        answering = max(MIN_STAGE_TOKENS, total - thinking)
        return thinking, answering

    async def complete(
        self,
        messages: List[Message],
        tools: Optional[List[ToolDefinition]] = None,
        instructions: str = "",
    ) -> NormalizedReply:
        if not self.config.enable_thinking:
            return await super().complete(messages, tools, instructions)

        thinking_budget, answer_budget = self._stage_budgets()

        console.print(
            f"🧠 Stage-1 thinking with budget tokens: {thinking_budget}", style="cyan"
        )
        stage1 = await self._post(
            self._build_payload(
                messages,
                tools=None,
                max_tokens=thinking_budget,
                stop=["</think>"],
                temperature=THINKING_TEMPERATURE,
                top_p=THINKING_TOP_P,
            )
        )
        stage1_message = (stage1.get("choices") or [{}])[0].get("message") or {}
        reasoning = ensure_closed_think_block(stage1_message.get("content") or "")

        console.print(
            f"💬 Stage-2 answering with tokens: {answer_budget}", style="cyan"
        )
        # The answering call must see the reasoning, but it is the loop's job to
        # persist it, so extend a local copy rather than the caller's list.
        answering_messages = list(messages) + [
            Message(role="assistant", content=reasoning)
        ]
        stage2 = await self._post(
            self._build_payload(
                answering_messages, tools=tools, max_tokens=answer_budget
            )
        )

        reply = self._normalize(stage2)
        reply.reasoning = reasoning
        return reply


__all__ = ["NemotronAdapter", "ensure_closed_think_block", "DEFAULT_THINKING_BUDGET"]
