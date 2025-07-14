"""
异步 WebSocket 客户端
"""

import asyncio
import json
import time
from typing import Dict, List, Any, Optional

import websockets

from .base import BaseWebSocketClient
from .types import ClientInfo, MessageTarget, MessageInstruction
from .exceptions import ConnectionError, MessageError


class AsyncWebSocketClient(BaseWebSocketClient):
    """异步 WebSocket 客户端"""

    def __init__(self, server_url: str, client_info: ClientInfo):
        super().__init__(server_url, client_info)
        self.websocket = None
        self._heartbeat_task = None
        self._message_task = None

    async def connect(self) -> bool:
        """连接到 WebSocket 服务器"""
        try:
            url = self._build_connection_url()
            self.websocket = await websockets.connect(url)
            self.connected = True

            # 启动消息监听和心跳任务
            self._message_task = asyncio.create_task(self._message_loop())
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

            return True

        except Exception as e:
            raise ConnectionError(f"连接失败: {e}")

    async def disconnect(self):
        """断开连接"""
        self.connected = False

        if self._heartbeat_task:
            self._heartbeat_task.cancel()

        if self._message_task:
            self._message_task.cancel()

        if self.websocket:
            await self.websocket.close()

        await self._trigger_event("disconnect", {"reason": "主动断开"})

    async def send_message(
        self,
        instruction: str,
        data: Dict[str, Any],
        target: Optional[MessageTarget] = None,
    ) -> bool:  # tuple[bool, Any]:
        """发送消息"""
        if not self.connected or not self.websocket:
            raise ConnectionError("未连接到服务器")

        envelope = self._prepare_message_envelope(instruction, data, target)

        try:
            await self.websocket.send(json.dumps(envelope))
            # return (True, data)
            return True
        except Exception as e:
            raise MessageError(f"发送消息失败: {e}")

    async def _message_loop(self):
        """消息监听循环"""
        try:
            while self.connected and self.websocket:
                message = await self.websocket.recv()
                message_data = self._process_received_message(message)

                if message_data is None:
                    continue

                if "error" in message_data:
                    await self._trigger_event("error", message_data)
                    continue

                instruction = self._get_message_instruction(message_data)

                match instruction:
                    case MessageInstruction.HEARTBEAT.value:
                        await self._trigger_event("heartbeat", message_data)
                    case MessageInstruction.CONNECT.value:
                        await self._trigger_event("connect", message_data)
                    case MessageInstruction.DISCONNECT.value:
                        await self._trigger_event("disconnect", message_data)
                    case MessageInstruction.MESSAGE.value:
                        await self._trigger_event("message", message_data)
                    case MessageInstruction.ERROR.value:
                        await self._trigger_event("error", message_data)
                    case _:
                        # 处理其他消息类型
                        await self._trigger_event("other", message_data)

        except websockets.exceptions.ConnectionClosed:
            self.connected = False
            await self._trigger_event("disconnect", {"reason": "连接被关闭"})
        except Exception as e:
            self.connected = False
            await self._trigger_event("error", {"error": str(e)})

    async def _heartbeat_loop(self):
        """心跳循环"""
        try:
            while self.connected:
                await asyncio.sleep(30)  # 每30秒发送心跳
                if self.connected:
                    await self.send_message(
                        MessageInstruction.HEARTBEAT.value, {"timestamp": time.time()}
                    )
        except asyncio.CancelledError:
            pass
        except Exception as e:
            await self._trigger_event("error", {"error": f"心跳错误: {e}"})

    async def _trigger_event(self, event_type: str, data: Any):
        """触发事件处理器"""
        if event_type in self._server_event_handlers:
            for handler in self._server_event_handlers[event_type]:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(data)
                    else:
                        handler(data)
                except Exception as e:
                    print(f"事件处理器错误 ({event_type}): {e}")
