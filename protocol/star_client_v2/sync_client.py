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
        self._message_task = None
        self._heartbeat_task = None
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
            # A failed connect previously left the loop thread alive. Always
            # release the helper loop before surfacing the connection failure.
            if self._stop_event:
                self._stop_event.set()
            if (
                self._loop_thread
                and self._loop_thread.is_alive()
                and self._loop_thread is not threading.current_thread()
            ):
                self._loop_thread.join(timeout=2)
            raise ConnectionError(f"Connection failed: {e}")

    def disconnect(self):
        """Disconnect and stop all background asyncio work (synchronous).

        Do not return early merely because ``connected`` is already false: the
        message loop may observe a remote close first while the heartbeat task
        and helper event-loop thread are still alive. Shutdown is intentionally
        idempotent and owns the thread lifecycle, not just websocket state.
        """
        try:
            loop = self._loop
            thread_alive = bool(self._loop_thread and self._loop_thread.is_alive())

            if loop and not loop.is_closed() and thread_alive:
                future = asyncio.run_coroutine_threadsafe(
                    self._async_disconnect(), loop
                )
                future.result(timeout=5)

            if self._stop_event:
                self._stop_event.set()

            if (
                self._loop_thread
                and self._loop_thread.is_alive()
                and self._loop_thread is not threading.current_thread()
            ):
                self._loop_thread.join(timeout=5)

        except Exception as e:
            print(f"Error while disconnecting: {e}")
            if self._stop_event:
                self._stop_event.set()
        finally:
            self.connected = False
            self.websocket = None
            if not self._loop_thread or not self._loop_thread.is_alive():
                self._loop_thread = None
                self._loop = None
                self._message_task = None
                self._heartbeat_task = None

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
            try:
                pending = asyncio.all_tasks(self._loop)
                for task in pending:
                    task.cancel()

                if pending:
                    self._loop.run_until_complete(
                        asyncio.gather(*pending, return_exceptions=True)
                    )
                self._loop.run_until_complete(self._loop.shutdown_asyncgens())
            except Exception:
                pass
            finally:
                self._loop.close()

    async def _wait_for_stop(self):
        """Wait for a stop signal."""
        while self._stop_event and not self._stop_event.is_set():
            await asyncio.sleep(0.1)

    async def _async_connect(self) -> bool:
        """Async connect implementation."""
        try:
            url = self.url()
            self.websocket = await websockets.connect(url)
            self.connected = True

            # Track background tasks explicitly so shutdown can cancel + await
            # them before the helper loop is closed.
            self._message_task = asyncio.create_task(self._message_loop())
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

            return True

        except Exception as e:
            raise ConnectionError(f"Connection failed: {e}")

    async def _cancel_background_tasks(self):
        """Cancel and await listener/heartbeat tasks owned by this client."""
        current = asyncio.current_task()
        tasks = []
        for task in (self._message_task, self._heartbeat_task):
            if task is not None and task is not current and not task.done():
                task.cancel()
                tasks.append(task)

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        self._message_task = None
        self._heartbeat_task = None

    async def _async_disconnect(self):
        """Async disconnect implementation."""
        had_transport = self.websocket is not None
        was_connected = self.connected
        self.connected = False

        # Stop background work before tearing down the transport. In particular,
        # a heartbeat sleeping for 30 seconds must be cancelled and awaited, not
        # left pending until the event loop object is destroyed.
        await self._cancel_background_tasks()

        if self.websocket:
            await self.websocket.close()
            self.websocket = None

        if was_connected or had_transport:
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

        except asyncio.CancelledError:
            raise
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
            raise
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
