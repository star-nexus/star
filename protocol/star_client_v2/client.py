"""
具体的客户端实现类
基于新的异步客户端架构
"""

import asyncio
import time
from typing import Dict, Any, List
from .async_client import AsyncWebSocketClient
from .types import ClientInfo, MessageType, ClientType


def gen_id() -> int:
    """生成唯一ID"""
    return int(asyncio.get_event_loop().time() * 1000)  # 毫秒级时间戳作为ID


class AgentClient(AsyncWebSocketClient):
    """智能体客户端"""

    def __init__(self, server_url: str, env_id: str, agent_id: str):
        client_info = ClientInfo(type=ClientType.AGENT, id=agent_id)
        super().__init__(server_url, client_info)
        self.env_id = env_id

    def url(self) -> str:
        """构建 Agent 连接 URL"""
        return f"{self.server_url}/env/{self.env_id}/agent/{self.client_info.id}"

    async def send_action(self, action: str, parameters: Dict[str, Any] = None) -> bool:
        """执行动作"""
        if parameters is None:
            parameters = {}

        request_id = gen_id()
        print(f"Performing action {action} with id {request_id}")
        success = await self.send_message(
            MessageType.MESSAGE.value,
            {
                "type": "action",
                "id": request_id,
                "action": action,
                "parameters": parameters,
            },
            target={"type": "env", "id": self.env_id},
        )
        if success:
            return request_id
        else:
            raise Exception("Failed to send action")


class EnvironmentClient(AsyncWebSocketClient):
    """环境客户端"""

    def __init__(self, server_url: str, env_id: str):
        client_info = ClientInfo(type=ClientType.ENVIRONMENT, id=env_id)
        super().__init__(server_url, client_info)

    def url(self) -> str:
        """构建环境连接 URL"""
        return f"{self.server_url}/env/{self.client_info.id}"

    async def response(
        self,
        agent_id: int,
        action_id: int,
        outcome: Any,
        outcome_type: str,
    ) -> bool:
        """向指定 Agent 发送消息"""
        return await self.send_message(
            MessageType.MESSAGE.value,
            {
                "type": "outcome",
                "id": action_id,
                "outcome": outcome,
                "outcome_type": outcome_type,
            },
            target={
                "type": "agent",
                "id": agent_id,
            },
        )
