"""
Star Client SDK - A concise and efficient multi-role WebSocket client SDK.

Provides a unified interface to connect and manage Agent and Environment clients.
Supports both synchronous and asynchronous usage.
"""

from .client import AgentClient, EnvironmentClient
from .base import BaseWebSocketClient
from .async_client import AsyncWebSocketClient
from .sync_client import SyncWebSocketClient
from .exceptions import ConnectionError, MessageError, AgentClientError
from .types import Envelope, ClientInfo, EventHandler, ClientType, MessageType

__version__ = "0.1.0"
__all__ = [
    "AgentClient",
    "EnvironmentClient",
    "BaseWebSocketClient",
    "AsyncWebSocketClient",
    "SyncWebSocketClient",
    "ConnectionError",
    "MessageError",
    "AgentClientError",
    "Envelope",
    "ClientInfo",
    "EventHandler",
    "ClientType",
    "MessageType",
]
