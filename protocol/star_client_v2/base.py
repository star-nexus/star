"""
Shared base code for WebSocket clients
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
    """Base class for WebSocket clients - shared by sync and async clients."""

    def __init__(self, server_url: str, client_info: ClientInfo):
        self.server_url = server_url
        self.client_info = client_info
        self.hub_event_handlers: Dict[str, List[EventHandler | AsyncEventHandler]] = {}

    def add_hub_listener(
        self, event_type: str, handler: EventHandler | AsyncEventHandler
    ):
        """Add an event listener."""
        if event_type not in self.hub_event_handlers:
            self.hub_event_handlers[event_type] = []
        self.hub_event_handlers[event_type].append(handler)

    def remove_hub_listener(
        self,
        event_type: str,
        handler: Optional[EventHandler | AsyncEventHandler] = None,
    ):
        """Remove an event listener."""
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
        """Prepare the message envelope - used by both sync and async clients."""

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
        """Validate and parse an incoming message from JSON to a dict."""
        try:
            return json.loads(message)
        except json.JSONDecodeError:
            return {"error": f"Invalid JSON: {message}"}

    @abstractmethod
    def url(self) -> str:
        """Build the connection URL - must be implemented by subclasses."""
        pass

    # 抽象方法，同步和异步版本分别实现
    @abstractmethod
    def connect(self):
        """Connect to the server - must be implemented by subclasses."""
        pass

    @abstractmethod
    def disconnect(self):
        """Disconnect - must be implemented by subclasses."""
        pass

    @abstractmethod
    def send_message(
        self,
        instruction: str,
        data: Dict[str, Any],
        target: Optional[MessageTarget] = None,
    ):
        """Send a message - must be implemented by subclasses."""
        pass
