"""
具体的客户端实现类
基于新的异步客户端架构
"""

import asyncio
import time
from typing import Dict, Any, List
from .async_client import AsyncWebSocketClient
from .types import ClientInfo, MessageInstruction


def gen_id() -> int:
    """生成唯一ID"""
    return int(asyncio.get_event_loop().time() * 1000)  # 毫秒级时间戳作为ID


class AgentClient(AsyncWebSocketClient):
    """智能体客户端"""

    def __init__(self, server_url: str, env_id: int, agent_id: int):
        client_info = ClientInfo(role_type="agent", env_id=env_id, agent_id=agent_id)
        super().__init__(server_url, client_info)

    def _build_connection_url(self) -> str:
        """构建 Agent 连接 URL"""
        return f"{self.server_url}/agent/{self.client_info.env_id}/{self.client_info.agent_id}"

    async def _send_connection_message(self):
        """发送 Agent 连接消息"""
        await self.send_message(
            MessageInstruction.CONNECT.value,
            {},
        )

    async def perform_action(
        self, action: str, parameters: Dict[str, Any] = None
    ) -> bool:
        """执行动作"""
        if parameters is None:
            parameters = {}

        request_id = gen_id()
        success = await self.send_message(
            MessageInstruction.MESSAGE.value,
            {
                "type": "action",
                "id": request_id,
                "action": action,
                "parameters": parameters,
            },
            target={"role_type": "env", "env_id": self.client_info.env_id},
        )
        if success:
            return request_id
        else:
            raise Exception("Failed to send action")

    async def observe_environment(self) -> bool:
        """观察环境"""
        return await self.perform_action("observe", {"env": self.client_info.env_id})

    async def ping_environment(self) -> bool:
        """Ping 环境"""
        return await self.send_message(
            "ping",
            {
                "timestamp": time.time(),
                "message": f"来自 Agent {self.client_info.agent_id} 的 Ping",
            },
            target={"role_type": "env", "env_id": self.client_info.env_id},
        )


class EnvironmentClient(AsyncWebSocketClient):
    """环境客户端"""

    def __init__(self, server_url: str, env_id: int):
        client_info = ClientInfo(role_type="env", env_id=env_id)
        super().__init__(server_url, client_info)

    def _build_connection_url(self) -> str:
        """构建环境连接 URL"""
        return f"{self.server_url}/env/{self.client_info.env_id}"

    async def _send_connection_message(self):
        """发送环境连接消息"""
        await self.send_message(
            MessageInstruction.CONNECT.value,
            {},
        )

    async def broadcast_status(self, status: str) -> bool:
        """广播环境状态"""
        return await self.send_message(
            MessageInstruction.BROADCAST.value, {"status": status}
        )

    async def response_to_agent(
        self,
        agent_id: int,
        action_id: int,
        outcome: Any,
        outcome_type: str,
    ) -> bool:
        """向指定 Agent 发送消息"""
        return await self.send_message(
            MessageInstruction.MESSAGE.value,
            {
                "type": "outcome",
                "id": action_id,
                "outcome": outcome,
                "outcome_type": outcome_type,
            },
            target={
                "role_type": "agent",
                "env_id": self.client_info.env_id,
                "agent_id": agent_id,
            },
        )

    async def send_to_human(self, human_id: int, message: str) -> bool:
        """向指定 Human 发送消息"""
        return await self.send_message(
            MessageInstruction.MESSAGE.value,
            {"message": message},
            target={
                "role_type": "human",
                "env_id": self.client_info.env_id,
                "human_id": human_id,
            },
        )


class HumanClient(AsyncWebSocketClient):
    """人类客户端"""

    def __init__(self, server_url: str, env_id: int, human_id: int):
        client_info = ClientInfo(role_type="human", env_id=env_id, human_id=human_id)
        super().__init__(server_url, client_info)

    def _build_connection_url(self) -> str:
        """构建人类连接 URL"""
        return f"{self.server_url}/human/{self.client_info.env_id}/{self.client_info.human_id}"

    async def _send_connection_message(self):
        """发送人类连接消息"""
        await self.send_message(
            MessageInstruction.CONNECT.value,
            {},
        )

    async def say(self, message: str, to: str = None) -> bool:
        """向指定角色发送消息"""
        if to is None:
            to = {"role_type": "env", "env_id": self.client_info.env_id}
        elif isinstance(to, str):
            to = to.split(".")
            if len(to) == 1 and to[0] == "env":
                to = {"role_type": "env", "env_id": self.client_info.env_id}
            elif len(to) == 2:
                if to[0] == "agent":
                    to = {
                        "role_type": "agent",
                        "env_id": self.client_info.env_id,
                        "agent_id": int(to[1]),
                    }
                elif to[0] == "human":
                    to = {
                        "role_type": "human",
                        "env_id": self.client_info.env_id,
                        "human_id": int(to[1]),
                    }
                else:
                    raise ValueError("Invalid target format")
            else:
                raise ValueError("Invalid target format")
        return await self.send_message(
            "human_action",
            {"action": "say", "message": message},
            target=to,
        )

    async def perform_action(self, action: str, parameters: List[str] = None) -> bool:
        """执行人类动作"""
        if parameters is None:
            parameters = []

        return await self.send_message(
            "human_action",
            {"action": action, "parameters": parameters},
            target={"role_type": "env", "env_id": self.client_info.env_id},
        )
