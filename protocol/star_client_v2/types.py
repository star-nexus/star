"""
Type definitions for the Star Client SDK
"""

from datetime import datetime
from typing import Dict, Any, Callable, Optional, Union
from dataclasses import dataclass, field
from enum import Enum


@dataclass
class ClientType(Enum):
    """Client type enum."""

    AGENT = "agent"
    ENVIRONMENT = "env"
    HUMAN = "human"
    HUB = "hub"


class MessageType(Enum):
    """Message instruction enum."""

    BROADCAST = "broadcast"
    # Message instruction
    MESSAGE = "message"
    # Heartbeat instruction
    HEARTBEAT = "heartbeat"
    # Connection state
    CONNECT = "connect"
    DISCONNECT = "disconnect"
    # Error instruction
    ERROR = "error"


# Historical alternative ClientInfo commented out in legacy version

#     role_type: str
#     env_id: int
#     agent_id: Optional[int] = None
#     human_id: Optional[int] = None

#     def to_dict(self) -> Dict[str, Any]:
#         """将客户端信息转换为字典"""
#         d = {
#             "role_type": self.role_type,
#             "env_id": self.env_id,
#         }
#         if self.agent_id is not None:
#             d["agent_id"] = self.agent_id
#         if self.human_id is not None:
#             d["human_id"] = self.human_id
#         return d


@dataclass
class ClientInfo:
    """Client identity information for envelope addressing."""

    type: ClientType
    id: str


@dataclass
class Envelope:
    """Message envelope structure."""

    type: str
    sender: ClientInfo
    recipient: ClientInfo
    payload: Union[str, dict]
    # NOTE: default must be a factory to avoid evaluating at import time
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())


# Event handler types
EventHandler = Callable[[Dict[str, Any]], Any]
AsyncEventHandler = Callable[[Dict[str, Any]], Any]

# Message target type
MessageTarget = Union[str, Dict[str, Any], ClientInfo]
