"""Provider transports. One per model API shape."""

from __future__ import annotations

from typing import Callable, Dict

from ..core.config import LLMConfig
from ..core.stats import ErrorStatsCollector
from ..profiles import Profile
from .base import ModelAdapter, ProviderError, RecoverableProviderError
from .chat_completions import ChatCompletionsAdapter
from .fake import FakeAdapter, ProbeScript
from .nemotron import DEFAULT_THINKING_BUDGET, NemotronAdapter
from .responses import ResponsesAdapter

AdapterBuilder = Callable[..., ModelAdapter]

ADAPTER_BUILDERS: Dict[str, AdapterBuilder] = {
    "chat_completions": lambda profile, config, stats, **kw: ChatCompletionsAdapter(
        config, stats, carry_reasoning=kw.get("carry_reasoning", True)
    ),
    "responses": lambda profile, config, stats, **kw: ResponsesAdapter(
        config, stats, carry_reasoning=kw.get("carry_reasoning", True)
    ),
    "nemotron": lambda profile, config, stats, **kw: NemotronAdapter(
        config,
        stats,
        thinking_budget=profile.thinking_budget or DEFAULT_THINKING_BUDGET,
        carry_reasoning=kw.get("carry_reasoning", True),
    ),
    "fake": lambda profile, config, stats, **kw: FakeAdapter(config, stats),
}


def register_adapter(name: str, builder: AdapterBuilder) -> None:
    """Add or replace a transport. Community adapters register here."""
    ADAPTER_BUILDERS[name] = builder


def build_adapter(
    profile: Profile,
    config: LLMConfig,
    stats: ErrorStatsCollector,
    *,
    carry_reasoning: bool = True,
) -> ModelAdapter:
    """Construct the transport named by `profile.adapter`."""
    try:
        builder = ADAPTER_BUILDERS[profile.adapter]
    except KeyError:
        raise ValueError(
            f"Unknown adapter '{profile.adapter}' in profile '{profile.name}'. "
            f"Available: {', '.join(sorted(ADAPTER_BUILDERS))}"
        )
    return builder(profile, config, stats, carry_reasoning=carry_reasoning)


__all__ = [
    "ModelAdapter",
    "ProviderError",
    "RecoverableProviderError",
    "ChatCompletionsAdapter",
    "ResponsesAdapter",
    "NemotronAdapter",
    "FakeAdapter",
    "ProbeScript",
    "ADAPTER_BUILDERS",
    "register_adapter",
    "build_adapter",
]
