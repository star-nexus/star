"""LLM connection config, loaded from `.configs.toml`.

`enable_thinking` has no default here on purpose: whether a model reasons by
default is a property of the profile (see `rotk_agent/profiles.py`), and the
old per-file agents disagreed about it. The caller must decide.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import toml

# Hard cap on completion tokens (reasoning + answer). DeepSeek V4 can emit
# hundreds of thousands otherwise; a game turn does not need that.
DEFAULT_MAX_TOKENS = 8192
# DeepSeek's low tier. high/max are available on the CLI for experiments.
DEFAULT_REASONING_EFFORT = "low"


@dataclass
class LLMConfig:
    """Everything needed to reach one model endpoint."""

    provider: str
    model_id: str
    api_key: str = field(repr=False)
    base_url: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    enable_thinking: bool = True
    #: Reasoning intensity when thinking is on: "low" | "high" | "max".
    #: Only families that expose a budget knob read it (DeepSeek, Responses API).
    reasoning_effort: Optional[str] = None


def resolve_section(config: Dict[str, Any], provider: str) -> Dict[str, Any]:
    """Read one section, following `inherits` so variants stay DRY.

    A section may set `inherits = "<other section>"` to borrow credentials and
    endpoint from it and override only what differs. That is how the same model
    gets an A/B pair for reasoning on versus off without duplicating the key.
    """
    seen: List[str] = []
    merged: Dict[str, Any] = {}

    name = provider
    while True:
        if name in seen:
            raise ValueError(
                f"Circular 'inherits' in config: {' -> '.join(seen + [name])}"
            )
        seen.append(name)

        try:
            section = config[name]
        except KeyError:
            origin = (
                f" (inherited by '{seen[-2]}')" if len(seen) > 1 else ""
            )
            raise ValueError(f"Invalid provider: {name}{origin}")

        if not isinstance(section, dict):
            raise ValueError(f"Config section '{name}' is not a table")

        # The child was merged first, so it wins over anything it inherits.
        merged = {**section, **merged}

        parent = section.get("inherits")
        if not parent:
            merged.pop("inherits", None)
            return merged
        name = parent


def load_config(
    config_path: str = ".configs.toml",
    provider: str = "vllm",
    enable_thinking_default: bool = True,
    reasoning_effort_default: Optional[str] = DEFAULT_REASONING_EFFORT,
) -> LLMConfig:
    """Read one provider section out of the TOML config."""
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")

    config = toml.load(config_path)
    provider_config = resolve_section(config, provider)

    try:
        model_id = provider_config["model_id"]
    except KeyError:
        raise ValueError(f"Model ID not found for {provider}")

    return LLMConfig(
        provider=provider,
        model_id=model_id,
        api_key=provider_config.get("api_key", "EMPTY"),
        base_url=provider_config.get("base_url", ""),
        temperature=provider_config.get("temperature"),
        max_tokens=provider_config.get("max_tokens", DEFAULT_MAX_TOKENS),
        top_p=provider_config.get("top_p"),
        top_k=provider_config.get("top_k"),
        enable_thinking=provider_config.get(
            "enable_thinking", enable_thinking_default
        ),
        reasoning_effort=provider_config.get(
            "reasoning_effort", reasoning_effort_default
        ),
    )


__all__ = [
    "DEFAULT_MAX_TOKENS",
    "DEFAULT_REASONING_EFFORT",
    "LLMConfig",
    "load_config",
    "resolve_section",
]
