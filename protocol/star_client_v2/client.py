"""
Concrete client implementations based on the async client architecture.
"""

import asyncio
import time
import uuid
from typing import Dict, Any, List, Optional
from .async_client import AsyncWebSocketClient
from .types import ClientInfo, MessageType, ClientType


def gen_id() -> int:
    """Generate a unique request id (integer)."""
    # return int(asyncio.get_event_loop().time() * 1000)
    return uuid.uuid4().int


class AgentClient(AsyncWebSocketClient):
    """Agent client."""

    def __init__(self, server_url: str, env_id: str, agent_id: str):
        client_info = ClientInfo(type=ClientType.AGENT, id=agent_id)
        super().__init__(server_url, client_info)
        self.env_id = env_id

    def url(self) -> str:
        """Build the Agent connection URL."""
        return f"{self.server_url}/env/{self.env_id}/agent/{self.client_info.id}"

    async def send_action(self, action: str, parameters: Optional[Dict[str, Any]] = None) -> int:
        """Send an action to the environment and return the generated request id."""
        if parameters is None:
            parameters = {}

        request_id = gen_id()
        print(f"Performing action '{action}' with id {request_id}")
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

    async def send_actions(self, actions: List[Dict[str, Any]]) -> int:
        """Send multiple actions to the environment in one batch message.

        Each item in `actions` should be a dict with:
          - action: str (required)
          - parameters: dict (optional, defaults to {})
          - id: Union[str, int] (optional; will be generated if missing)

        Returns the generated batch message id.
        """
        prepared_actions: List[Dict[str, Any]] = []
        request_id = gen_id()
        for item in actions:
            name = item.get("action")
            params = item.get("parameters", {}) or {}
            if not name:
                raise ValueError("Each action item must include an 'action' field")
            item_id = item.get("id") or gen_id() # function tool call ID
            prepared_actions.append(
                {
                    "id": item_id,
                    "action": name,
                    "parameters": params,
                }
            )
        success = await self.send_message(
            MessageType.MESSAGE.value,
            {
                "type": "action_batch",
                "id": request_id,
                "actions": prepared_actions,
            },
            target={"type": "env", "id": self.env_id},
        )
        if success:
            return request_id
        else:
            raise Exception("Failed to send action batch")


class EnvironmentClient(AsyncWebSocketClient):
    """Environment client."""

    def __init__(self, server_url: str, env_id: str):
        client_info = ClientInfo(type=ClientType.ENVIRONMENT, id=env_id)
        super().__init__(server_url, client_info)

    def url(self) -> str:
        """Build the Environment connection URL."""
        return f"{self.server_url}/env/{self.client_info.id}"

    async def response(
        self,
        agent_id: str,
        action_id: int,
        outcome: Any,
        outcome_type: str,
    ) -> bool:
        """Send an outcome message to the specified Agent."""
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
