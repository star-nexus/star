"""Real-time mode: the world keeps moving whether or not the agent acts."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from ..core.delays import calculate_action_delay, rpm_limit_interval
from ..profiles import DEFAULT_LANGUAGE, faction_info
from .base import ModeStrategy

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ..core.agent import RoTKChatAgent

LENGTH_NUDGE = (
    "Note: The game is real time, you should think quickly and give only the "
    "critical information of your strategy."
)

STOP_NUDGE = (
    "Note: You are the commander. You decide the strategy and act on it without "
    "asking for confirmation. Issue your next orders as tool calls now."
)

OPENING_PROMPT_CN = (
    "**当前配置**:\n"
    "- **我方势力**: {own_name} ({faction})\n"
    "- **主要敌人**: {enemy_name} ({enemy})\n"
    "- 建议你利用游戏规则和兵种特性思考进攻战术，附加决策说明，以增加决策分指标。\n"
    "- 你要下达多个单位的协同指令，所以每次回复中要多个工具同时调用，以提高效率。\n"
    "- 你无需等待AP恢复，可以立即进行攻击。"
)

OPENING_PROMPT_EN = (
    "**Current setup**:\n"
    "- **Our faction**: {own_name} ({faction})\n"
    "- **Main enemy**: {enemy_name} ({enemy})\n"
    "- Use the rules and unit traits to plan attacks, and add a brief rationale "
    "so the strategy score can register.\n"
    "- Issue coordinated orders for multiple units; call several tools in one reply.\n"
    "- You do not need to wait for AP to recover; attack immediately."
)


class RealTimeMode(ModeStrategy):
    """No gating; pace actions so they do not outrun the ENV's animations."""

    name = "real_time"
    prompt_kind = "realtime"
    history_limit = 100
    delay_policy = staticmethod(calculate_action_delay)

    def __init__(self, language: str = DEFAULT_LANGUAGE):
        self.language = language

    async def after_model_call(self, agent: "RoTKChatAgent") -> None:
        # Respect a provider's requests-per-minute cap between calls.
        await rpm_limit_interval()

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


__all__ = ["RealTimeMode"]
