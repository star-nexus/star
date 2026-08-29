"""
Star Client SDK - A concise and efficient multi-role WebSocket client SDK.

Provides a unified interface to connect and manage Agent and Environment clients.
Supports both synchronous and asynchronous usage.
"""

from .client import AgentClient, EnvironmentClient
from .base import BaseWebSocketClient
from .async_client import AsyncWebSocketClient
from .sync_client import SyncWebSocketClient
from .exceptions import (
    ConnectionError,
    MessageError,
    AgentClientError,
    ActionTimeout,
    ProtocolError,
)
from .ids import gen_id, normalize_id
from .types import Envelope, ClientInfo, EventHandler, ClientType, MessageType

__version__ = "0.2.0"
PROTOCOL_VERSION = "1.0"

__all__ = [
    "AgentClient",
    "EnvironmentClient",
    "BaseWebSocketClient",
    "AsyncWebSocketClient",
    "SyncWebSocketClient",
    "ConnectionError",
    "MessageError",
    "AgentClientError",
    "ActionTimeout",
    "ProtocolError",
    "gen_id",
    "normalize_id",
    "Envelope",
    "ClientInfo",
    "EventHandler",
    "ClientType",
    "MessageType",
    "PROTOCOL_VERSION",
]
