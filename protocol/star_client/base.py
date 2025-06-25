"""
WebSocket 客户端共同基础代码
"""

import json
import time
from typing import Dict, List, Any, Optional
from abc import ABC, abstractmethod

from .types import ClientInfo, MessageTarget, EventHandler, MessageInstruction
from .exceptions import ConnectionError, MessageError


class BaseWebSocketClient(ABC):
    """WebSocket 客户端基类 - 包含同步和异步客户端的共同代码"""

    def __init__(self, server_url: str, client_info: ClientInfo):
        self.server_url = server_url
        self.client_info = client_info
        self.connected = False
        self._server_event_handlers: Dict[str, List[EventHandler]] = {}

    def add_event_listener(self, event_type: str, handler: EventHandler):
        """添加事件监听器"""
        if event_type not in self._server_event_handlers:
            self._server_event_handlers[event_type] = []
        self._server_event_handlers[event_type].append(handler)

    def remove_event_listener(
        self, event_type: str, handler: Optional[EventHandler] = None
    ):
        """移除事件监听器"""
        if handler is None:
            self._server_event_handlers[event_type] = []
        elif event_type in self._server_event_handlers:
            self._server_event_handlers[event_type] = [
                h for h in self._server_event_handlers[event_type] if h != handler
            ]

    def _prepare_message_envelope(
        self,
        instruction: str,
        data: Dict[str, Any],
        target: Optional[MessageTarget] = None,
    ) -> Dict[str, Any]:
        """准备消息信封 - 同步和异步版本都会用到"""
        if target is None:
            target = {"role_type": "server"}
        elif isinstance(target, str):
            target = {"role_type": target}
        elif isinstance(target, ClientInfo):
            target = {
                "role_type": target.role_type,
                "env_id": target.env_id,
            }
            if target.agent_id:
                target["agent_id"] = target.agent_id
            if target.human_id:
                target["human_id"] = target.human_id

        return {
            "instruction": instruction,
            "msg_from": self.client_info.to_dict(),
            "msg_to": target,
            "data": data,
            "timestamp": time.time(),
        }

    def _process_received_message(self, message: str) -> Optional[Dict[str, Any]]:
        """处理接收到的消息 - 解析 JSON 并返回消息数据"""
        try:
            return json.loads(message)
        except json.JSONDecodeError:
            return {"error": f"无效的 JSON: {message}"}

    def _get_message_instruction(self, message_data: Dict[str, Any]) -> str:
        """获取消息指令"""
        return message_data.get("instruction", "")

    @abstractmethod
    def _build_connection_url(self) -> str:
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
