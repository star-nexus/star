"""The single agent entry point.

    uv run rotk_agent/main.py --faction wei --provider deepseek --mode real_time

Which model API gets used follows from `--provider` via the profile table in
`profiles.py`, or can be pinned with `--profile`. This replaced six near-identical
scripts selected by a shell dispatcher.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

# Allow `uv run rotk_agent/main.py` as well as `python -m rotk_agent.main`.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rotk_agent.adapters.base import ModelAdapter
from rotk_agent.adapters.chat_completions import ChatCompletionsAdapter
from rotk_agent.adapters.fake import FakeAdapter, ProbeScript
from rotk_agent.adapters.nemotron import NemotronAdapter
from rotk_agent.adapters.responses import ResponsesAdapter
from rotk_agent.core.agent import RoTKChatAgent
from rotk_agent.core.bridge import EnvBridge
from rotk_agent.core.config import (
    DEFAULT_REASONING_EFFORT,
    LLMConfig,
    load_config,
)
from rotk_agent.core.console import console_system
from rotk_agent.core.runner import DEFAULT_HUB_URL, AgentRunner
from rotk_agent.core.stats import ErrorStatsCollector
from rotk_agent.modes.base import ModeStrategy
from rotk_agent.modes.realtime import RealTimeMode
from rotk_agent.modes.turn import DEFAULT_MAX_API_CALLS_PER_TURN, TurnBasedMode
from rotk_agent.profiles import (
    DEFAULT_LANGUAGE,
    PROFILES,
    Profile,
    load_prompt,
    render_prompt,
    resolve_profile,
)

MODES = {"real_time": RealTimeMode, "turn_based": TurnBasedMode}


def build_adapter(
    profile: Profile,
    config: LLMConfig,
    stats: ErrorStatsCollector,
    carry_reasoning: bool = True,
) -> ModelAdapter:
    """Instantiate the transport this profile calls for."""
    if profile.adapter == "chat_completions":
        return ChatCompletionsAdapter(config, stats, carry_reasoning=carry_reasoning)
    if profile.adapter == "responses":
        return ResponsesAdapter(config, stats)
    if profile.adapter == "nemotron":
        return NemotronAdapter(
            config, stats, thinking_budget=profile.thinking_budget or 256
        )
    if profile.adapter == "fake":
        return FakeAdapter(config, stats)
    raise ValueError(f"Unknown adapter '{profile.adapter}' in profile '{profile.name}'")


def build_mode(
    mode_name: str, bridge: EnvBridge, faction: str, max_api_calls_per_turn: int
) -> ModeStrategy:
    if mode_name == "real_time":
        return RealTimeMode()
    if mode_name == "turn_based":
        return TurnBasedMode(
            bridge=bridge,
            faction=faction,
            max_api_calls_per_turn=max_api_calls_per_turn,
        )
    raise ValueError(f"Unknown mode '{mode_name}'. Available: {', '.join(MODES)}")


def fake_config(provider: str) -> LLMConfig:
    """A config for the scripted adapter, which needs no credentials."""
    return LLMConfig(
        provider=provider,
        model_id="fake-model",
        api_key="EMPTY",
        base_url="fake://local",
        enable_thinking=False,
    )


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run an LLM agent against a STAR environment.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--env-id", default="env_1", help="Environment to join.")
    parser.add_argument("--agent-id", default="agent_1", help="This agent's id.")
    parser.add_argument(
        "--faction", default=None, choices=["wei", "shu", "wu"],
        help="Faction to command. Defaults to $AGENT_FACTION, then wei.",
    )
    parser.add_argument(
        "--provider", default="vllm_qwen3_14b",
        help="Section name in .configs.toml holding the model endpoint.",
    )
    parser.add_argument(
        "--profile", default=None, choices=sorted(PROFILES),
        help="Pin the model profile instead of inferring it from --provider.",
    )
    parser.add_argument(
        "--mode", default="turn_based", choices=sorted(MODES),
        help="Whether the ENV runs turn-based or real-time.",
    )
    parser.add_argument(
        "--lang", default=DEFAULT_LANGUAGE, choices=["cn", "en"],
        help="System prompt language.",
    )
    parser.add_argument(
        "--reasoning-effort",
        default=DEFAULT_REASONING_EFFORT,
        choices=["low", "high", "max"],
        help=(
            "How hard the model may think per turn. Only families with a budget "
            "knob honour it (DeepSeek, Responses API); a per-provider "
            "reasoning_effort in .configs.toml overrides it."
        ),
    )
    parser.add_argument(
        "--carry-reasoning",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Keep the model's reasoning in the conversation context. On by "
            "default so DeepSeek tool loops send the chain back verbatim "
            "(required by the API, and the cheaper path once disk cache hits). "
            "Pass --no-carry-reasoning to echo an empty field instead."
        ),
    )
    parser.add_argument("--hub-url", default=DEFAULT_HUB_URL, help="Hub websocket URL.")
    parser.add_argument(
        "--config", default=".configs.toml", help="Path to the provider config."
    )
    parser.add_argument(
        "--max-api-calls-per-turn", type=int, default=DEFAULT_MAX_API_CALLS_PER_TURN,
        help="Turn-based only: force end_turn after this many model calls.",
    )
    parser.add_argument(
        "--max-iterations", type=int, default=1000,
        help="Cap on chat-loop iterations per expedition.",
    )
    return parser.parse_args(argv)


async def run(args: argparse.Namespace) -> int:
    faction = args.faction or os.environ.get("AGENT_FACTION", "wei").lower()
    profile = resolve_profile(args.provider, args.profile)

    console_system.print(
        f"🧩 Profile: {profile.name} (adapter={profile.adapter}) — {profile.description}",
        style="bold blue",
    )

    if profile.adapter == "fake":
        config = fake_config(args.provider)
    else:
        try:
            config = load_config(
                args.config,
                provider=args.provider,
                enable_thinking_default=profile.enable_thinking,
                reasoning_effort_default=args.reasoning_effort,
            )
        except (ValueError, KeyError, FileNotFoundError) as e:
            # A bad provider name or missing config never fixes itself on retry.
            console_system.print(f"Fatal LLM config error: {e}", style="red bold")
            # markup=False: rich would read the TOML section brackets as a style
            # tag and swallow the provider name, which is the one thing the
            # reader needs here.
            console_system.print(
                f"Check the [{args.provider}] section in {args.config} and retry.",
                style="yellow",
                markup=False,
            )
            return 2

    bridge = EnvBridge()
    mode = build_mode(args.mode, bridge, faction, args.max_api_calls_per_turn)
    # The mode decides the pacing, so hand its policy to the already-built bridge.
    bridge.delay_policy = mode.delay_policy

    system_prompt = render_prompt(
        load_prompt(mode.prompt_kind, args.lang, profile.prompt_variant), faction
    )

    stats = ErrorStatsCollector()

    def make_agent() -> RoTKChatAgent:
        # A fresh adapter per expedition, so a closed transport never gets reused.
        return RoTKChatAgent(
            adapter=build_adapter(
                profile, config, stats, carry_reasoning=args.carry_reasoning
            ),
            mode=mode,
            bridge=bridge,
            stats=stats,
            faction=faction,
            system_prompt=system_prompt,
            agent_id=args.agent_id,
            max_iterations=args.max_iterations,
        )

    runner = AgentRunner(
        agent_factory=make_agent,
        mode=mode,
        faction=faction,
        hub_url=args.hub_url,
        env_id=args.env_id,
        agent_id=args.agent_id,
    )
    await runner.run()
    return 0


def main(argv=None) -> int:
    args = parse_args(argv)
    try:
        return asyncio.run(run(args))
    except KeyboardInterrupt:
        console_system.print("\n👋 Interrupted", style="yellow")
        return 130


if __name__ == "__main__":
    sys.exit(main())
