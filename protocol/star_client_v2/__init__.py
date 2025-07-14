"""
Star Client SDK - 一个简洁高效的多角色 WebSocket 客户端 SDK

提供统一的接口来连接和管理 Agent、Environment 客户端
支持同步和异步两种使用方式
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
