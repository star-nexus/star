"""
Concrete client implementations based on the async client architecture.
"""

import asyncio
from typing import Any, Dict, List, Optional

from .async_client import AsyncWebSocketClient
from .correlation import Correlator
from .exceptions import ConnectionError as ClientConnectionError
from .exceptions import MessageError, ProtocolError
from .ids import gen_id, normalize_id
from .types import ClientInfo, ClientType, MessageType

DEFAULT_ACTION_TIMEOUT = 30.0


class AgentClient(AsyncWebSocketClient):
    """Agent client.

    Owns request/response correlation. `call()` sends an action and returns its
    outcome, so callers do not track ids or poll a shared dict. `send_action()`
    remains for callers that want the id back and will await it separately.
    """

    def __init__(
        self,
        server_url: str,
        env_id: str,
        agent_id: str,
        action_timeout: float = DEFAULT_ACTION_TIMEOUT,
    ):
        client_info = ClientInfo(type=ClientType.AGENT, id=agent_id)
        super().__init__(server_url, client_info)
        self.env_id = env_id
        self.action_timeout = action_timeout
        self._correlator = Correlator()

        # Registered here rather than left to the application: correlation is
        # the SDK's job. Application listeners still fire, in addition to these.
        self.add_hub_listener("message", self._correlate_message)
        self.add_hub_listener("error", self._correlate_error)
        self.add_hub_listener("disconnect", self._abandon_pending)

    def url(self) -> str:
        """Build the Agent connection URL."""
        return f"{self.server_url}/env/{self.env_id}/agent/{self.client_info.id}"

    # ------------------------------------------------------------ correlation

    def _correlate_message(self, data: Dict[str, Any]) -> None:
        """Resolve the pending request an inbound `outcome` belongs to."""
        payload = (data or {}).get("payload") or {}
        if payload.get("type") != "outcome":
            return
        if "id" not in payload:
            return
        self._correlator.resolve(payload["id"], payload.get("outcome"))

    def _correlate_error(self, data: Dict[str, Any]) -> None:
        """Fail the pending request an inbound error refers to."""
        payload = (data or {}).get("payload") or {}
        request_id = payload.get("id")
        if request_id is None:
            return
        message = payload.get("error") or "Unknown error"
        self._correlator.fail(request_id, ProtocolError(str(message), request_id))

    def _abandon_pending(self, data: Dict[str, Any]) -> None:
        """Fail outstanding requests instead of letting each time out alone."""
        reason = (data or {}).get("reason") or "connection closed"
        self._correlator.abandon_all(
            ClientConnectionError(f"Disconnected while awaiting outcome: {reason}")
        )

    @property
    def pending_requests(self) -> list:
        """Ids awaiting an outcome. For diagnostics and tests."""
        return self._correlator.pending_ids

    # ------------------------------------------------------------- public API

    async def call(
        self,
        action: str,
        parameters: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> Any:
        """Send one action and return its outcome.

        Raises `ActionTimeout` if the ENV does not answer in time, or
        `ProtocolError` if it answers with a protocol-level error.
        """
        request_id = await self.send_action(action, parameters)
        return await self.await_outcome(request_id, timeout, action=action)

    async def call_many(
        self,
        actions: List[Dict[str, Any]],
        timeout: Optional[float] = None,
    ) -> Any:
        """Send a batch of actions and return the batch outcome."""
        request_id = await self.send_actions(actions)
        return await self.await_outcome(request_id, timeout, action="action_batch")

    async def await_outcome(
        self,
        request_id: Any,
        timeout: Optional[float] = None,
        *,
        action: str = "<unknown>",
    ) -> Any:
        """Await the outcome for a previously sent request id."""
        return await self._correlator.wait(
            request_id,
            self.action_timeout if timeout is None else timeout,
            action=action,
        )

    async def send_action(
        self,
        action: str,
        parameters: Optional[Dict[str, Any]] = None,
        *,
        expect_outcome: bool = True,
    ) -> Any:
        """Send an action to the environment and return the request id.

        The id is registered for correlation before the send, so an outcome that
        comes back faster than the caller can await it is not lost.
        """
        if parameters is None:
            parameters = {}

        request_id = gen_id()
        if expect_outcome:
            self._correlator.expect(request_id)

        await self._send_or_raise(
            {
                "type": "action",
                "id": request_id,
                "action": action,
                "parameters": parameters,
            },
            what=f"action '{action}'",
        )
        return request_id

    async def send_actions(self, actions: List[Dict[str, Any]]) -> Any:
        """Send multiple actions to the environment in one batch message.

        Each item in `actions` should be a dict with:
          - action: str (required)
          - parameters: dict (optional, defaults to {})
          - id: Union[str, int] (optional; will be generated if missing)

        Returns the generated batch message id.
        """
        prepared_actions: List[Dict[str, Any]] = []
        for item in actions:
            name = item.get("action")
            if not name:
                raise ValueError("Each action item must include an 'action' field")
            prepared_actions.append(
                {
                    # Per-item ids are the LLM's tool-call ids when it supplies
                    # them, so they are preserved rather than regenerated.
                    "id": item.get("id") or gen_id("call"),
                    "action": name,
                    "parameters": item.get("parameters", {}) or {},
                }
            )

        request_id = gen_id("batch")
        self._correlator.expect(request_id)
        await self._send_or_raise(
            {
                "type": "action_batch",
                "id": request_id,
                "actions": prepared_actions,
            },
            what=f"action batch of {len(prepared_actions)}",
        )
        return request_id

    async def _send_or_raise(self, payload: Dict[str, Any], *, what: str) -> None:
        """Send to the ENV, converting a falsy/raising send into one error type.

        `send_message` raises on transport failure and returns a bool otherwise;
        callers should not have to handle both shapes.
        """
        try:
            sent = await self.send_message(
                MessageType.MESSAGE.value,
                payload,
                target={"type": "env", "id": self.env_id},
            )
        except Exception:
            # Nothing left the process, so no outcome can arrive: drop the slot
            # rather than leaving a settled future for nobody to collect.
            self._correlator.discard(payload.get("id"))
            raise
        if not sent:
            self._correlator.discard(payload.get("id"))
            raise MessageError(f"Failed to send {what}")


class EnvironmentClient(AsyncWebSocketClient):
    """Environment client."""

    def __init__(self, server_url: str, env_id: str):
        client_info = ClientInfo(type=ClientType.ENVIRONMENT, id=env_id)
        super().__init__(server_url, client_info)

    def url(self) -> str:
        """Build the Environment connection URL."""
        return f"{self.server_url}/env/{self.client_info.id}"

    async def response(
        self,
        agent_id: str,
        action_id: Any,
        outcome: Any,
        outcome_type: str,
    ) -> bool:
        """Send an outcome message to the specified Agent.

        `action_id` is echoed back exactly as received, so whatever the agent
        used as its correlation key still matches.
        """
        return await self.send_message(
            MessageType.MESSAGE.value,
            {
                "type": "outcome",
                "id": action_id,
                "outcome": outcome,
                "outcome_type": outcome_type,
            },
            target={
                "type": "agent",
                "id": agent_id,
            },
        )


__all__ = ["AgentClient", "EnvironmentClient", "DEFAULT_ACTION_TIMEOUT"]
