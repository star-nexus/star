"""
Asynchronous WebSocket client
"""

import asyncio
import json
from typing import Dict, Any, Optional

import websockets

from .base import BaseWebSocketClient
from .types import ClientInfo, MessageTarget, MessageType
from .exceptions import ConnectionError, MessageError


class AsyncWebSocketClient(BaseWebSocketClient):
    """Asynchronous WebSocket client."""

    def __init__(self, server_url: str, client_info: ClientInfo):
        super().__init__(server_url, client_info)
        self.websocket = None
        self.env_id = None
        self._heartbeat_task = None
        self._message_task = None

    async def connect(self) -> bool:
        """Connect to the WebSocket server."""
        try:
            url = self.url()
            self.websocket = await websockets.connect(url)

            # Start message listener and heartbeat tasks
            self._message_task = asyncio.create_task(self._message_loop())
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

            return True

        except Exception as e:
            raise ConnectionError(f"Connection failed: {e}")

    async def disconnect(self):
        """Disconnect from the server."""

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
        """Send a message."""
        if not self.websocket:
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
            while self.websocket:
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
                        # Handle other message types
                        await self._trigger_event("other", message_data)

        except websockets.exceptions.ConnectionClosed:
            await self._trigger_event("disconnect", {"reason": "Connection was closed"})
        except Exception as e:
            await self._trigger_event("error", {"error": str(e)})

    async def _heartbeat_loop(self):
        """Heartbeat loop."""
        try:
            while self.websocket:
                await asyncio.sleep(30)  # Send heartbeat every 30 seconds
                if self.websocket:
                    await self.send_message(
                        MessageType.HEARTBEAT.value,
                        {"timestamp": asyncio.get_event_loop().time()},
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
                    if asyncio.iscoroutinefunction(handler):
                        await handler(data)
                    else:
                        handler(data)
                except Exception as e:
                    print(f"Event handler error ({event_type}): {e}")
