"""Model profiles: everything that varies between models, in one table.

Adding a model means adding a row here. Only a genuinely new API shape needs
new code, and that code goes in `adapters/`.

`enable_thinking` here is only the fallback used when `.configs.toml` does not
say. It is on everywhere except the `baseline` profile, which exists to measure
the same model with reasoning disabled. The old per-file agents disagreed about
this within a single model family — GPT-OSS and Nemotron defaulted it off in
real-time but on in turn-based — which made their two modes incomparable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from string import Template
from typing import Dict, Optional, Tuple

from rotk_agent.core.tools import FALLBACK_ACTION_NAMES, board_bounds_from_map

PROMPT_DIR = Path(__file__).parent / "prompts"

DEFAULT_LANGUAGE = "cn"


@dataclass(frozen=True)
class Profile:
    """How to talk to one family of models."""

    name: str
    adapter: str  # chat_completions | responses | nemotron | fake
    #: Fallback for `enable_thinking` when the config file omits it.
    enable_thinking: bool = True
    #: Substrings of `--provider` that select this profile automatically.
    provider_match: Tuple[str, ...] = ()
    #: Suffix selecting a prompt variant, e.g. "baseline".
    prompt_variant: Optional[str] = None
    #: Stage-1 token budget, for adapters that reason in a separate call.
    thinking_budget: Optional[int] = None
    description: str = ""


PROFILES: Dict[str, Profile] = {
    "qwen3": Profile(
        name="qwen3",
        adapter="chat_completions",
        enable_thinking=True,
        description="Qwen3 and other OpenAI-compatible chat completions endpoints.",
    ),
    "baseline": Profile(
        name="baseline",
        adapter="chat_completions",
        enable_thinking=False,
        prompt_variant="baseline",
        description=(
            "Control group: same transport as qwen3, reasoning disabled, and a "
            "prompt without tactical priming."
        ),
    ),
    "gpt_oss": Profile(
        name="gpt_oss",
        adapter="responses",
        enable_thinking=True,
        provider_match=("gpt",),
        description="GPT-OSS family via the OpenAI Responses API.",
    ),
    "nemotron": Profile(
        name="nemotron",
        adapter="nemotron",
        enable_thinking=True,
        provider_match=("nvidia", "nemotron"),
        thinking_budget=256,
        description="Nemotron, which reasons in a separate budgeted call.",
    ),
    "fake": Profile(
        name="fake",
        adapter="fake",
        enable_thinking=False,
        provider_match=("fake",),
        description="Scripted replies, for testing the harness without a model.",
    ),
}

DEFAULT_PROFILE = "qwen3"


def resolve_profile(provider: str, explicit: Optional[str] = None) -> Profile:
    """Pick a profile by name, or infer one from the provider string."""
    if explicit:
        try:
            return PROFILES[explicit]
        except KeyError:
            raise ValueError(
                f"Unknown profile '{explicit}'. Available: {', '.join(sorted(PROFILES))}"
            )

    lowered = (provider or "").lower()
    for profile in PROFILES.values():
        if any(token in lowered for token in profile.provider_match):
            return profile
    return PROFILES[DEFAULT_PROFILE]


def prompt_candidates(kind: str, language: str, variant: Optional[str]) -> list[str]:
    """Prompt file stems to try, most specific first."""
    base = f"system_prompt_{kind}_{language}"
    return [f"{base}_{variant}", base] if variant else [base]


def load_prompt(
    kind: str,
    language: str = DEFAULT_LANGUAGE,
    variant: Optional[str] = None,
    prompt_dir: Path = PROMPT_DIR,
) -> str:
    """Read the most specific prompt available for this mode and profile."""
    tried = []
    for stem in prompt_candidates(kind, language, variant):
        path = prompt_dir / f"{stem}.md"
        tried.append(path.name)
        if path.exists():
            return path.read_text(encoding="utf-8")

    raise FileNotFoundError(
        f"No prompt found for kind={kind} language={language} variant={variant}. "
        f"Tried: {', '.join(tried)}"
    )


FACTIONS = {
    "wei": {"name": "魏", "enemy": "shu"},
    "shu": {"name": "蜀", "enemy": "wei"},
    "wu": {"name": "吴", "enemy": "wei"},
}


def faction_info(faction: str) -> dict:
    return FACTIONS.get(faction, FACTIONS["wei"])


def render_prompt(template_text: str, faction: str) -> str:
    """Fill in the faction placeholders every prompt shares.

    ``$home_bases_block`` and ``$game_actions_block`` are left in place until
    the agent joins the ENV and ``apply_join_briefing_to_prompt`` writes them.
    """
    own = faction_info(faction)
    enemy = faction_info(own["enemy"])
    return Template(template_text).safe_substitute(
        faction=faction,
        faction_name=own["name"],
        opponent=own["enemy"],
        opponent_name=enemy["name"],
    )


def format_home_bases_block(briefing: Optional[dict]) -> str:
    """Markdown list of home-base hexes for the system prompt."""
    home_bases = (briefing or {}).get("home_bases") or {}
    lines = []
    for key, cell in home_bases.items():
        if not isinstance(cell, dict):
            continue
        info = faction_info(str(key))
        lines.append(
            f"- **{info['name']} ({key}) 基地 / home base**: "
            f"`({cell.get('col')}, {cell.get('row')})`"
        )
    if not lines:
        text = "本局尚未提供基地坐标。 / No home-base coordinates for this match."
    else:
        meaning = (briefing or {}).get("home_bases_meaning") or ""
        text = "\n".join(lines)
        if meaning:
            text += f"\n\n{meaning}"
    bounds = board_bounds_from_map(briefing)
    if bounds is not None:
        text += (
            f"\n\nBoard (even-q offset): col {bounds.col_min}..{bounds.col_max}, "
            f"row {bounds.row_min}..{bounds.row_max}."
        )
    return text


FACTION_STATE_PROMPT_BLURB = "compact state; see tool definition for row format"


def format_game_actions_block(payload: Optional[dict]) -> str:
    """Markdown list of this match's board verbs for the system prompt."""
    names: list = []
    docs: dict = {}
    if isinstance(payload, dict):
        raw_names = payload.get("names") or []
        names = [n for n in raw_names if n != "end_turn"]
        docs = payload.get("docs") or {}
    if not names:
        names = list(FALLBACK_ACTION_NAMES)
    lines = []
    for name in names:
        if name == "get_faction_state":
            desc = FACTION_STATE_PROMPT_BLURB
        else:
            desc = ""
            if isinstance(docs.get(name), dict):
                desc = docs[name].get("description") or ""
        if desc:
            lines.append(f"- `{name}`: {desc}")
        else:
            lines.append(f"- `{name}`")
    return "\n".join(lines) if lines else "- (none)"


def apply_game_actions_to_prompt(
    system_prompt: str, payload: Optional[dict]
) -> str:
    """Write this match's allowed board verbs into the system prompt after register."""
    block = format_game_actions_block(payload)
    if "$game_actions_block" in system_prompt:
        return system_prompt.replace("$game_actions_block", block)
    if not payload:
        return system_prompt
    return (
        system_prompt.rstrip()
        + "\n\n## 本局允许的棋盘动作 / Game actions this match\n"
        + block
    )


def apply_join_briefing_to_prompt(
    system_prompt: str,
    map_briefing: Optional[dict] = None,
    game_actions: Optional[dict] = None,
) -> str:
    """Fill home bases and the match action subset after ``register_agent_info``."""
    filled = apply_map_briefing_to_prompt(system_prompt, map_briefing)
    return apply_game_actions_to_prompt(filled, game_actions)


def apply_map_briefing_to_prompt(
    system_prompt: str, briefing: Optional[dict]
) -> str:
    """Write ENV home bases into the system prompt after register."""
    block = format_home_bases_block(briefing)
    if "$home_bases_block" in system_prompt:
        return system_prompt.replace("$home_bases_block", block)
    if not briefing:
        return system_prompt
    return (
        system_prompt.rstrip()
        + "\n\n## 本局各阵营基地坐标 / Home bases this match\n"
        + block
    )


__all__ = [
    "Profile",
    "PROFILES",
    "DEFAULT_PROFILE",
    "DEFAULT_LANGUAGE",
    "resolve_profile",
    "load_prompt",
    "render_prompt",
    "format_home_bases_block",
    "format_game_actions_block",
    "apply_map_briefing_to_prompt",
    "apply_game_actions_to_prompt",
    "apply_join_briefing_to_prompt",
    "faction_info",
    "FACTIONS",
]
