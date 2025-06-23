"""
同步 WebSocket 客户端
使用 websockets 库但提供同步接口
"""

import asyncio
import json
import threading
import time
from typing import Dict, List, Any, Optional
import concurrent.futures

import websockets

from .base import BaseWebSocketClient
from .types import ClientInfo, MessageTarget, MessageInstruction
from .exceptions import ConnectionError, MessageError


class SyncWebSocketClient(BaseWebSocketClient):
    """同步 WebSocket 客户端 - 使用 websockets 库但提供同步接口"""

    def __init__(self, server_url: str, client_info: ClientInfo):
        super().__init__(server_url, client_info)
        self.websocket = None
        self._loop = None
        self._loop_thread = None
        self._executor = None
        self._stop_event = None

    def connect(self) -> bool:
        """连接到 WebSocket 服务器 - 同步接口"""
        if self.connected:
            return True

        try:
            # 创建新的事件循环在独立线程中运行
            self._stop_event = threading.Event()
            self._loop_thread = threading.Thread(
                target=self._run_event_loop, daemon=True
            )
            self._loop_thread.start()

            # 等待事件循环启动
            time.sleep(0.1)

            # 在事件循环中执行连接
            future = asyncio.run_coroutine_threadsafe(self._async_connect(), self._loop)
            result = future.result(timeout=10)  # 10秒超时

            return result

        except Exception as e:
            raise ConnectionError(f"连接失败: {e}")

    def disconnect(self):
        """断开连接 - 同步接口"""
        if not self.connected:
            return

        try:
            # 在事件循环中执行断开连接
            if self._loop and not self._loop.is_closed():
                future = asyncio.run_coroutine_threadsafe(
                    self._async_disconnect(), self._loop
                )
                future.result(timeout=5)

            # 停止事件循环
            if self._stop_event:
                self._stop_event.set()

            # 等待线程结束
            if self._loop_thread and self._loop_thread.is_alive():
                self._loop_thread.join(timeout=2)

        except Exception as e:
            print(f"断开连接时出错: {e}")
        finally:
            self.connected = False

    def send_message(
        self,
        instruction: str,
        data: Dict[str, Any],
        target: Optional[MessageTarget] = None,
    ) -> bool:
        """发送消息 - 同步接口"""
        if not self.connected or not self._loop:
            raise ConnectionError("未连接到服务器")

        try:
            # 在事件循环中执行发送消息
            future = asyncio.run_coroutine_threadsafe(
                self._async_send_message(instruction, data, target), self._loop
            )
            return future.result(timeout=5)

        except Exception as e:
            raise MessageError(f"发送消息失败: {e}")

    def _run_event_loop(self):
        """在独立线程中运行事件循环"""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        try:
            # 运行事件循环直到停止
            self._loop.run_until_complete(self._wait_for_stop())
        finally:
            # 清理
            try:
                # 取消所有未完成的任务
                pending = asyncio.all_tasks(self._loop)
                for task in pending:
                    task.cancel()

                if pending:
                    self._loop.run_until_complete(
                        asyncio.gather(*pending, return_exceptions=True)
                    )
            except Exception:
                pass
            finally:
                self._loop.close()

    async def _wait_for_stop(self):
        """等待停止信号"""
        while not self._stop_event.is_set():
            await asyncio.sleep(0.1)

    async def _async_connect(self) -> bool:
        """异步连接方法"""
        try:
            url = self._build_connection_url()
            self.websocket = await websockets.connect(url)
            self.connected = True

            # 启动消息监听和心跳任务
            asyncio.create_task(self._message_loop())
            asyncio.create_task(self._heartbeat_loop())

            await self._send_connection_message()

            return True

        except Exception as e:
            raise ConnectionError(f"连接失败: {e}")

    async def _async_disconnect(self):
        """异步断开连接方法"""
        self.connected = False

        if self.websocket:
            await self.websocket.close()

        await self._trigger_event("disconnect", {"reason": "主动断开"})

    async def _async_send_message(
        self,
        instruction: str,
        data: Dict[str, Any],
        target: Optional[MessageTarget] = None,
    ) -> bool:
        """异步发送消息方法"""
        if not self.connected or not self.websocket:
            raise ConnectionError("未连接到服务器")

        envelope = self._prepare_message_envelope(instruction, data, target)

        try:
            await self.websocket.send(json.dumps(envelope))
            return True
        except Exception as e:
            raise MessageError(f"发送消息失败: {e}")

    async def _send_connection_message(self):
        """发送连接消息 - 子类可以重写"""
        await self._async_send_message(
            "connect", {"client_info": self.client_info.to_dict()}
        )

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

                if instruction == MessageInstruction.HEARTBEAT.value:
                    await self._trigger_event("heartbeat", message_data)
                elif instruction == MessageInstruction.CONNECT.value:
                    await self._trigger_event("connect", message_data)
                elif instruction == MessageInstruction.DISCONNECT.value:
                    await self._trigger_event("disconnect", message_data)
                elif instruction == MessageInstruction.MESSAGE.value:
                    await self._trigger_event("message", message_data)
                elif instruction == MessageInstruction.ERROR.value:
                    await self._trigger_event("error", message_data)
                else:
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
                    await self._async_send_message(
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
                    # 同步客户端的事件处理器都是同步的
                    if asyncio.iscoroutinefunction(handler):
                        await handler(data)
                    else:
                        # 在线程池中执行同步处理器，避免阻塞事件循环
                        loop = asyncio.get_event_loop()
                        await loop.run_in_executor(None, handler, data)
                except Exception as e:
                    print(f"事件处理器错误 ({event_type}): {e}")
