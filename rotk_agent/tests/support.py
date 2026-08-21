"""Test doubles for the ENV side of the conversation."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from rotk_agent.core.bridge import EnvBridge
from rotk_agent.core.delays import no_delay


class RecordingBridge(EnvBridge):
    """Answers ENV actions from a canned table and records every call."""

    def __init__(self, responses: Optional[Dict[str, Any]] = None):
        super().__init__(delay_policy=no_delay)
        self.responses = responses or {}
        self.calls: List[Tuple[str, Any]] = []

    @property
    def actions(self) -> List[str]:
        return [name for name, _ in self.calls]

    def params_for(self, action: str) -> List[Any]:
        return [p for name, p in self.calls if name == action]

    async def perform_action(self, action: str, params: Any) -> Any:
        self.calls.append((action, params))
        return self.responses.get(action, {"success": True, "result": True})

    async def send_end_turn(self, faction: str) -> Any:
        self.calls.append(("end_turn", {"faction": faction}))
        return self.responses.get("end_turn", {"success": True})

    async def send_turn_start_ack(self, faction: str, turn_number: int) -> None:
        self.calls.append(
            ("turn_start_ack", {"faction": faction, "turn_number": turn_number})
        )
