"""
Agent信息注册组件
Agent Information Registry Components
"""

import datetime
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from urllib.parse import urlparse
from framework import SingletonComponent


@dataclass
class AgentInfo:
    """单个Agent的信息"""
    provider: str = "unknown"  # LLM提供商：openai, deepseek, vllm, infinigence等
    model_id: str = "unknown"  # 模型ID：gpt-4o-mini, deepseek-chat等
    base_url: str = "unknown"  # 已脱敏的服务地址
    agent_id: Optional[str] = None  # Agent连接标识
    version: Optional[str] = None  # Agent版本
    note: Optional[str] = None  # 备注信息
    registration_time: Optional[str] = None  # 注册时间
    # 添加 enable_thinking 字段
    enable_thinking: Optional[bool] = None  # 是否启用思考模式


@dataclass 
class AgentInfoRegistry(SingletonComponent):
    """Agent信息注册表单例组件"""
    
    # 存储各阵营的Agent信息，键为阵营字符串："wei", "shu", "wu"
    agents: Dict[str, AgentInfo] = field(default_factory=dict)
    
    def register_agent(self, faction: str, agent_info: AgentInfo) -> bool:
        """注册Agent信息"""
        try:
            if faction in ["wei", "shu", "wu"]:
                # 添加注册时间
                agent_info.registration_time = datetime.datetime.now().isoformat()
                self.agents[faction] = agent_info
                print(f"[AgentInfoRegistry] ✅ 注册 {faction} 阵营Agent: {agent_info.provider}:{agent_info.model_id}")
                return True
            else:
                print(f"[AgentInfoRegistry] ❌ 无效的阵营名称: {faction}")
                return False
        except Exception as e:
            print(f"[AgentInfoRegistry] ❌ 注册Agent信息失败: {e}")
            return False
    
    def get_agent_info(self, faction: str) -> Optional[AgentInfo]:
        """获取指定阵营的Agent信息"""
        return self.agents.get(faction)
    
    def get_all_agents(self) -> Dict[str, AgentInfo]:
        """获取所有已注册的Agent信息"""
        return self.agents.copy()
    
    def has_agent(self, faction: str) -> bool:
        """检查指定阵营是否已注册Agent信息"""
        return faction in self.agents
    
    def get_summary(self) -> Dict[str, str]:
        """获取简要信息摘要"""
        summary = {}
        for faction, info in self.agents.items():
            summary[faction] = f"{info.provider}:{info.model_id}"
        return summary
    
    @staticmethod
    def sanitize_url(url: str) -> str:
        """脱敏URL，移除敏感信息"""
        try:
            parsed = urlparse(url)
            # 构建安全的URL：scheme + netloc + path
            safe_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            # 移除尾部斜杠
            return safe_url.rstrip('/')
        except Exception as e:
            print(f"[AgentInfoRegistry] ⚠️ URL脱敏失败: {e}")
            return "invalid_url"
