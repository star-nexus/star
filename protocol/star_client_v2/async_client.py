"""
异步 WebSocket 客户端
"""

import asyncio
from datetime import datetime
import json
import time
from typing import Dict, List, Any, Optional

import websockets

from .base import BaseWebSocketClient
from .types import ClientInfo, MessageTarget, MessageType
from .exceptions import ConnectionError, MessageError


class AsyncWebSocketClient(BaseWebSocketClient):
    """异步 WebSocket 客户端"""

    def __init__(self, server_url: str, client_info: ClientInfo):
        super().__init__(server_url, client_info)
        self.websocket = None
        self.env_id = None
        self._heartbeat_task = None
        self._message_task = None

    async def connect(self) -> bool:
        """连接到 WebSocket 服务器"""
        try:
            url = self.url()
            self.websocket = await websockets.connect(url)

            # 启动消息监听和心跳任务
            self._message_task = asyncio.create_task(self._message_loop())
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

            return True

        except Exception as e:
            raise ConnectionError(f"连接失败: {e}")

    async def disconnect(self):
        """断开连接"""

        if self._heartbeat_task:
            self._heartbeat_task.cancel()

        if self._message_task:
            self._message_task.cancel()

        if self.websocket:
            await self.websocket.close()

        return True

    async def send_message(
        self,
        instruction: str,
        data: Dict[str, Any],
        target: Optional[MessageTarget] = None,
    ) -> bool:
        """发送消息"""
        if not self.websocket:
            # if not self.websocket:
            raise ConnectionError("未连接到服务器")

        envelope = self.build_message_envelope(instruction, data, target)

        try:
            await self.websocket.send(json.dumps(envelope))
            return True
        except Exception as e:
            raise MessageError(f"发送消息失败: {e}")

    async def _message_loop(self):
        """消息监听循环"""
        try:
            while self.websocket:
                # while self.websocket:
                message = await self.websocket.recv()
                message_data = self._check_message_format(message)

                if message_data is None:
                    continue

                instruction = message_data.get("type")

                match instruction:
                    case MessageType.CONNECT.value:
                        await self._trigger_event("connect", message_data)
                    case MessageType.DISCONNECT.value:
                        await self._trigger_event("disconnect", message_data)
                    case MessageType.MESSAGE.value:
                        await self._trigger_event("message", message_data)
                    case MessageType.ERROR.value:
                        await self._trigger_event("error", message_data)
                    case _:
                        # 处理其他消息类型
                        await self._trigger_event("other", message_data)

        except websockets.exceptions.ConnectionClosed:
            await self._trigger_event("disconnect", {"reason": "连接被关闭"})
        except Exception as e:
            await self._trigger_event("error", {"error": str(e)})

    async def _heartbeat_loop(self):
        """心跳循环"""
        try:
            while self.websocket:
                await asyncio.sleep(30)  # 每30秒发送心跳
                if self.websocket:
                    await self.send_message(
                        MessageType.HEARTBEAT.value,
                        {},
                    )
        except asyncio.CancelledError:
            pass
        except Exception as e:
            await self._trigger_event("error", f"心跳错误: {e}")

    async def _trigger_event(self, event_type: str, data: Any):
        """触发事件处理器"""
        if event_type in self.hub_event_handlers:
            for handler in self.hub_event_handlers[event_type]:
                # try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(data)
                else:
                    handler(data)
                # except Exception as e:
                #     print(f"事件处理器错误 ({event_type}): {e}")
