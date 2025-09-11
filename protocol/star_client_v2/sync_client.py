"""
Synchronous WebSocket client
Built on top of the "websockets" library but exposes a synchronous API.
"""

import asyncio
import json
import threading
import time
from typing import Dict, Any, Optional

import websockets

from .base import BaseWebSocketClient
from .types import ClientInfo, MessageTarget, MessageType
from .exceptions import ConnectionError, MessageError


class SyncWebSocketClient(BaseWebSocketClient):
    """Synchronous WebSocket client - built on websockets with a sync interface."""

    def __init__(self, server_url: str, client_info: ClientInfo):
        super().__init__(server_url, client_info)
        self.websocket = None
        self._loop = None
        self._loop_thread = None
        self._stop_event = None
        self._loop_ready = None
        self.connected = False

    def connect(self) -> bool:
        """Connect to the WebSocket server (synchronous)."""
        if self.connected:
            return True

        try:
            # Create a new event loop running in a dedicated thread
            self._stop_event = threading.Event()
            self._loop_ready = threading.Event()
            self._loop_thread = threading.Thread(
                target=self._run_event_loop, daemon=True
            )
            self._loop_thread.start()

            # Wait for the event loop to be ready
            if not self._loop_ready.wait(timeout=5):
                raise ConnectionError("Event loop failed to start in time")

            # Run connect coroutine in the event loop
            future = asyncio.run_coroutine_threadsafe(self._async_connect(), self._loop)
            result = future.result(timeout=10)  # 10s timeout

            return result

        except Exception as e:
            raise ConnectionError(f"Connection failed: {e}")

    def disconnect(self):
        """Disconnect (synchronous)."""
        if not self.connected:
            return

        try:
            # Run disconnect coroutine in the event loop
            if self._loop and not self._loop.is_closed():
                future = asyncio.run_coroutine_threadsafe(
                    self._async_disconnect(), self._loop
                )
                future.result(timeout=5)

            # Stop the event loop
            if self._stop_event:
                self._stop_event.set()

            # Wait for the loop thread to finish
            if self._loop_thread and self._loop_thread.is_alive():
                self._loop_thread.join(timeout=2)

        except Exception as e:
            print(f"Error while disconnecting: {e}")
        finally:
            self.connected = False

    def send_message(
        self,
        instruction: str,
        data: Dict[str, Any],
        target: Optional[MessageTarget] = None,
    ) -> bool:
        """Send a message (synchronous)."""
        if not self.connected or not self._loop:
            raise ConnectionError("Not connected to the server")

        try:
            # Run send coroutine in the event loop
            future = asyncio.run_coroutine_threadsafe(
                self._async_send_message(instruction, data, target), self._loop
            )
            return future.result(timeout=5)

        except Exception as e:
            raise MessageError(f"Failed to send message: {e}")

    def _run_event_loop(self):
        """Run the event loop in a dedicated thread."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        if self._loop_ready is not None:
            self._loop_ready.set()

        try:
            # Run the loop until a stop signal is received
            self._loop.run_until_complete(self._wait_for_stop())
        finally:
            # Cleanup
            try:
                # Cancel all pending tasks
                pending = asyncio.all_tasks()
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
        """Wait for a stop signal."""
        while not self._stop_event.is_set():
            await asyncio.sleep(0.1)

    async def _async_connect(self) -> bool:
        """Async connect implementation."""
        try:
            url = self.url()
            self.websocket = await websockets.connect(url)
            self.connected = True

            # Start message listener and heartbeat tasks
            asyncio.create_task(self._message_loop())
            asyncio.create_task(self._heartbeat_loop())

            return True

        except Exception as e:
            raise ConnectionError(f"Connection failed: {e}")

    async def _async_disconnect(self):
        """Async disconnect implementation."""
        self.connected = False

        if self.websocket:
            await self.websocket.close()

        await self._trigger_event("disconnect", {"reason": "Disconnected by client"})

    async def _async_send_message(
        self,
        instruction: str,
        data: Dict[str, Any],
        target: Optional[MessageTarget] = None,
    ) -> bool:
        """Async send message implementation."""
        if not self.connected or not self.websocket:
            raise ConnectionError("Not connected to the server")

        envelope = self.build_message_envelope(instruction, data, target)

        try:
            await self.websocket.send(json.dumps(envelope))
            return True
        except Exception as e:
            raise MessageError(f"Failed to send message: {e}")

    async def _message_loop(self):
        """Message listening loop."""
        try:
            while self.connected and self.websocket:
                message = await self.websocket.recv()
                message_data = self._check_message_format(message)

                if message_data is None:
                    continue

                if "error" in message_data:
                    await self._trigger_event("error", message_data)
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
                        # Handle other message types
                        await self._trigger_event("other", message_data)

        except websockets.exceptions.ConnectionClosed:
            self.connected = False
            await self._trigger_event("disconnect", {"reason": "Connection was closed"})
        except Exception as e:
            self.connected = False
            await self._trigger_event("error", {"error": str(e)})

    async def _heartbeat_loop(self):
        """Heartbeat loop."""
        try:
            while self.connected:
                await asyncio.sleep(30)  # Send heartbeat every 30 seconds
                if self.connected:
                    await self._async_send_message(
                        MessageType.HEARTBEAT.value, {"timestamp": time.time()}
                    )
        except asyncio.CancelledError:
            pass
        except Exception as e:
            await self._trigger_event("error", {"error": f"Heartbeat error: {e}"})

    async def _trigger_event(self, event_type: str, data: Any):
        """Trigger registered event handlers."""
        if event_type in self.hub_event_handlers:
            for handler in self.hub_event_handlers[event_type]:
                try:
                    # Event handlers may be sync or async
                    if asyncio.iscoroutinefunction(handler):
                        await handler(data)
                    else:
                        # Run sync handlers in a thread to avoid blocking the loop
                        loop = asyncio.get_event_loop()
                        await loop.run_in_executor(None, handler, data)
                except Exception as e:
                    print(f"Event handler error ({event_type}): {e}")
