"""
Agent information registry components.
"""

import datetime
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from urllib.parse import urlparse
from framework import SingletonComponent


@dataclass
class AgentInfo:
    """Information for a single agent."""
    provider: str = "unknown"  # LLM provider: openai, deepseek, vllm, etc.
    model_id: str = "unknown"  # Model id: gpt-4o-mini, deepseek-chat, etc.
    base_url: str = "unknown"  # Sanitized service base URL
    agent_id: Optional[str] = None  # Agent connection identifier
    version: Optional[str] = None  # Agent version
    note: Optional[str] = None  # Notes
    registration_time: Optional[str] = None  # Registration time (ISO)
    enable_thinking: Optional[bool] = None  # Whether "thinking mode" is enabled


@dataclass
class AgentInfoRegistry(SingletonComponent):
    """Singleton registry for agent information.

    Each faction holds a list so two agents on Wei both appear in
    settlement. Re-registering the same ``agent_id`` replaces that row.
    """

    agents: Dict[str, List[AgentInfo]] = field(default_factory=dict)

    def register_agent(self, faction: str, agent_info: AgentInfo) -> bool:
        """Register agent information."""
        try:
            if faction not in ["wei", "shu", "wu"]:
                print(f"[AgentInfoRegistry] ❌ Invalid faction name: {faction}")
                return False
            agent_info.registration_time = datetime.datetime.now().isoformat()
            bucket = self.agents.setdefault(faction, [])
            if agent_info.agent_id:
                for i, existing in enumerate(bucket):
                    if existing.agent_id == agent_info.agent_id:
                        bucket[i] = agent_info
                        print(
                            f"[AgentInfoRegistry] ✅ Updated {faction} agent "
                            f"{agent_info.agent_id}: "
                            f"{agent_info.provider}:{agent_info.model_id}"
                        )
                        return True
            bucket.append(agent_info)
            print(
                f"[AgentInfoRegistry] ✅ Registered {faction} faction agent: "
                f"{agent_info.provider}:{agent_info.model_id}"
                + (f" ({agent_info.agent_id})" if agent_info.agent_id else "")
            )
            return True
        except Exception as e:
            print(f"[AgentInfoRegistry] ❌ Failed to register agent info: {e}")
            return False

    def get_agents(self, faction: str) -> List[AgentInfo]:
        """All agents registered to ``faction``, in registration order."""
        return list(self.agents.get(faction) or [])

    def get_agent_info(self, faction: str) -> Optional[AgentInfo]:
        """The most recently registered agent for ``faction``, if any."""
        infos = self.agents.get(faction) or []
        return infos[-1] if infos else None

    def get_all_agents(self) -> Dict[str, List[AgentInfo]]:
        """Copy of the faction → agents map."""
        return {faction: list(infos) for faction, infos in self.agents.items()}

    def has_agent(self, faction: str) -> bool:
        """Return whether the faction has a registered agent."""
        return bool(self.agents.get(faction))

    def get_summary(self) -> Dict[str, str]:
        """Get a short summary (faction -> provider:model[, ...])."""
        summary = {}
        for faction, infos in self.agents.items():
            summary[faction] = ", ".join(
                f"{info.provider}:{info.model_id}" for info in infos
            )
        return summary

    @staticmethod
    def sanitize_url(url: str) -> str:
        """Sanitize a URL by removing sensitive parts."""
        try:
            parsed = urlparse(url)
            safe_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            return safe_url.rstrip("/")
        except Exception as e:
            print(f"[AgentInfoRegistry] ⚠️ URL sanitization failed: {e}")
            return "invalid_url"
