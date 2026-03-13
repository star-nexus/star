"""
Agent information registry components.
"""

import datetime
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
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
    """Singleton registry for agent information."""
    
    # Stores agent info by faction key: "wei", "shu", "wu"
    agents: Dict[str, AgentInfo] = field(default_factory=dict)
    
    def register_agent(self, faction: str, agent_info: AgentInfo) -> bool:
        """Register agent information."""
        try:
            if faction in ["wei", "shu", "wu"]:
                # Attach registration timestamp
                agent_info.registration_time = datetime.datetime.now().isoformat()
                self.agents[faction] = agent_info
                print(
                    f"[AgentInfoRegistry] ✅ Registered {faction} faction agent: "
                    f"{agent_info.provider}:{agent_info.model_id}"
                )
                return True
            else:
                print(f"[AgentInfoRegistry] ❌ Invalid faction name: {faction}")
                return False
        except Exception as e:
            print(f"[AgentInfoRegistry] ❌ Failed to register agent info: {e}")
            return False
    
    def get_agent_info(self, faction: str) -> Optional[AgentInfo]:
        """Get agent info for a given faction."""
        return self.agents.get(faction)
    
    def get_all_agents(self) -> Dict[str, AgentInfo]:
        """Get all registered agents."""
        return self.agents.copy()
    
    def has_agent(self, faction: str) -> bool:
        """Return whether the faction has a registered agent."""
        return faction in self.agents
    
    def get_summary(self) -> Dict[str, str]:
        """Get a short summary (faction -> provider:model)."""
        summary = {}
        for faction, info in self.agents.items():
            summary[faction] = f"{info.provider}:{info.model_id}"
        return summary
    
    @staticmethod
    def sanitize_url(url: str) -> str:
        """Sanitize a URL by removing sensitive parts."""
        try:
            parsed = urlparse(url)
            # Build safe URL: scheme + netloc + path
            safe_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            # Strip trailing slash
            return safe_url.rstrip("/")
        except Exception as e:
            print(f"[AgentInfoRegistry] ⚠️ URL sanitization failed: {e}")
            return "invalid_url"
