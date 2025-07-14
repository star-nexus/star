"""
WebSocket 客户端共同基础代码
"""

from dataclasses import asdict
import json
import time
from typing import Dict, List, Any, Optional
from abc import ABC, abstractmethod

from .types import (
    Envelope,
    ClientInfo,
    MessageTarget,
    EventHandler,
    AsyncEventHandler,
    MessageType,
)
from .exceptions import ConnectionError, MessageError


class BaseWebSocketClient(ABC):
    """WebSocket 客户端基类 - 包含同步和异步客户端的共同代码"""

    def __init__(self, server_url: str, client_info: ClientInfo):
        self.server_url = server_url
        self.client_info = client_info
        self.hub_event_handlers: Dict[str, List[EventHandler | AsyncEventHandler]] = {}

    def add_hub_listener(
        self, event_type: str, handler: EventHandler | AsyncEventHandler
    ):
        """添加事件监听器"""
        if event_type not in self.hub_event_handlers:
            self.hub_event_handlers[event_type] = []
        self.hub_event_handlers[event_type].append(handler)

    def remove_hub_listener(
        self,
        event_type: str,
        handler: Optional[EventHandler | AsyncEventHandler] = None,
    ):
        """移除事件监听器"""
        if handler is None:
            self.hub_event_handlers[event_type] = []
        elif event_type in self.hub_event_handlers:
            self.hub_event_handlers[event_type] = [
                h for h in self.hub_event_handlers[event_type] if h != handler
            ]

    def build_message_envelope(
        self,
        instruction: str,
        data: Dict[str, Any],
        target: Optional[MessageTarget] = None,
    ) -> Dict[str, Any]:
        """准备消息信封 - 同步和异步版本都会用到"""

        if target is None:
            target = {"type": "hub", "id": ""}
        elif isinstance(target, str):
            target = target.strip()
            if target == "":
                target = {"type": "hub", "id": ""}
            else:
                target = {"type": target, "id": ""}
        elif isinstance(target, ClientInfo):
            target = {"type": target.type.value, "id": target.id}

        sender = {"type": self.client_info.type.value, "id": self.client_info.id}

        return asdict(
            Envelope(
                type=instruction,
                sender=sender,
                recipient=target,
                payload=data,
            )
        )

    def _check_message_format(self, message: str) -> Optional[Dict[str, Any]]:
        """检查接收到的消息格式 - 解析 JSON 并返回消息数据"""
        try:
            return json.loads(message)
        except json.JSONDecodeError:
            return {"error": f"无效的 JSON: {message}"}

    @abstractmethod
    def url(self) -> str:
        """构建连接 URL - 子类必须实现"""
        pass

    # 抽象方法，同步和异步版本分别实现
    @abstractmethod
    def connect(self):
        """连接到服务器 - 子类必须实现"""
        pass

    @abstractmethod
    def disconnect(self):
        """断开连接 - 子类必须实现"""
        pass

    @abstractmethod
    def send_message(
        self,
        instruction: str,
        data: Dict[str, Any],
        target: Optional[MessageTarget] = None,
    ):
        """发送消息 - 子类必须实现"""
        pass
