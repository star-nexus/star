"""
Type definitions for the Star Client SDK
"""

from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, Union
from dataclasses import dataclass, field
from enum import Enum


class ClientType(str, Enum):
    """Client type, as it appears in the `sender`/`recipient` envelope fields.

    A `str` enum so members serialise to their wire value directly. (This class
    was previously decorated with `@dataclass`, which is meaningless on an Enum
    and only generated a misleading `__repr__`.)
    """

    AGENT = "agent"
    ENVIRONMENT = "env"
    HUMAN = "human"
    HUB = "hub"


class MessageType(str, Enum):
    """Envelope `type`: which transport-level instruction this message is."""

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
    """The Hub envelope. Every message on the wire has this shape.

    See `docs/hub-envelope.md` for the wire format and the payload types that
    ride inside `payload`.
    """

    type: str
    sender: ClientInfo
    recipient: ClientInfo
    payload: Union[str, dict]
    # NOTE: default must be a factory to avoid evaluating at import time
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())


# Hub listener callbacks. Both sync and async handlers are accepted; the
# message loop awaits the result when it is a coroutine.
EventHandler = Callable[[Dict[str, Any]], Any]
AsyncEventHandler = Callable[[Dict[str, Any]], Awaitable[Any]]

# What `send_message(target=...)` accepts: a bare id, a `{"type", "id"}` dict,
# or a ClientInfo.
MessageTarget = Union[str, Dict[str, Any], ClientInfo]
