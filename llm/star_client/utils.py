"""
消息处理器和工具函数
"""

import asyncio
from typing import Dict, Any, Callable, Optional
from .types import EventHandler


class MessageProcessor:
    """消息处理器，提供常用的消息处理功能"""

    def __init__(self):
        self.action_handlers: Dict[str, Callable] = {}

    def register_action(self, action_name: str, handler: Callable):
        """注册动作处理器"""
        self.action_handlers[action_name] = handler

    async def process_message(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """处理消息并返回响应"""
        action = data.get("action")
        if action and action in self.action_handlers:
            handler = self.action_handlers[action]
            try:
                if asyncio.iscoroutinefunction(handler):
                    return await handler(data)
                else:
                    return handler(data)
            except Exception as e:
                return {"type": "error", "id": "", "error": str(e)}
        return None


def create_default_handlers() -> Dict[str, EventHandler]:
    """创建默认的事件处理器"""

    def on_connect(data):
        """连接成功处理器"""
        client_info = data.get("client_info", {})
        print(f"✅ {client_info.get('role_type', 'Unknown').upper()} 客户端连接成功!")

    def on_disconnect(data):
        """断开连接处理器"""
        reason = data.get("reason", "未知原因")
        print(f"❌ 连接已断开: {reason}")

    def on_message(data):
        """消息接收处理器"""
        msg_ins = data.get("instruction", "unknown")
        msg_from = data.get("msg_from", {})
        msg_data = data.get("data", {})
        from_type = msg_from.get("role_type", "unknown")

        print(f"📨 [{msg_ins.upper()}] 来自 {from_type}: {msg_data}")

    def on_error(data):
        """错误处理器"""
        error = data.get("error", "未知错误")
        print(f"⚠️ 错误: {error}")

    return {
        "connect": on_connect,
        "disconnect": on_disconnect,
        "message": on_message,
        "error": on_error,
    }


# 预定义的动作处理器
async def echo_handler(data: Dict[str, Any]) -> Dict[str, Any]:
    """回声处理器"""
    parameters = data.get("parameters", [])
    action_id = data.get("id", "")
    return {
        "type": "outcome",
        "id": action_id,
        "outcome": f"回声: {' '.join(parameters)}",
    }


async def add_handler(data: Dict[str, Any]) -> Dict[str, Any]:
    """加法处理器"""
    parameters = data.get("parameters", [])
    action_id = data.get("id", "")
    # 确保有足够的参数进行加法
    if len(parameters) >= 2:
        try:
            a, b = int(parameters[0]), int(parameters[1])
            result = a + b
            return {
                "type": "outcome",
                "id": action_id,
                "outcome": result,
                "status": "success",
            }
        except ValueError:
            return {
                "type": "outcome",
                "id": action_id,
                "outcome": "参数必须是数字",
                "status": "error",
            }
    else:
        return {
            "type": "outcome",
            "id": action_id,
            "outcome": "需要至少两个参数",
            "status": "error",
        }


# 默认动作处理器映射
DEFAULT_ACTION_HANDLERS = {
    "echo": echo_handler,
    "add": add_handler,
}
