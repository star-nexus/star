"""The agent's side of the ENV conversation.

Requests go out over the protocol client and come back asynchronously through
the hub listener, which parks each outcome in `RemoteContext.id_map` keyed by
request id. `EnvBridge` turns that into awaitable calls, and its bound methods
are what gets registered as LLM tools.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Callable, Dict, List, Optional

from protocol import AgentClient

from .console import console
from .delays import calculate_action_delay
from .errors import handle_error_with_logging

DelayPolicy = Callable[[str, Any, Any], float]


class RemoteContext:
    """Process-wide handles shared between the hub listener and the agent.

    Deliberately plain module state rather than `ContextVar`s. The listener runs
    in its own task, and `asyncio.create_task` copies the context, so a
    `ContextVar.set` there is invisible to the agent loop. The previous version
    used `ContextVar`s and worked only because every writer happened to mutate
    the dict in place; replacing a dict wholesale silently lost the update.
    """

    _client: Optional[AgentClient] = None
    _status: Dict[str, Any] = {}
    _task_manager: Optional[object] = None
    _id_map: Dict[Any, Any] = {}

    @staticmethod
    def set_client(client: AgentClient):
        RemoteContext._client = client

    @staticmethod
    def get_client() -> AgentClient:
        if RemoteContext._client is None:
            raise LookupError("No AgentClient registered; connect to the hub first.")
        return RemoteContext._client

    @staticmethod
    def set_status(status: dict):
        RemoteContext._status = status

    @staticmethod
    def get_status() -> dict:
        return RemoteContext._status

    @staticmethod
    def update_status(**fields) -> dict:
        """Merge fields into the status, preserving whatever is already there."""
        RemoteContext._status.update(fields)
        return RemoteContext._status

    @staticmethod
    def set_task_manager(task_manager: object):
        RemoteContext._task_manager = task_manager

    @staticmethod
    def get_task_manager() -> object:
        return RemoteContext._task_manager

    @staticmethod
    def set_id_map(id_map: dict):
        RemoteContext._id_map = id_map

    @staticmethod
    def get_id_map() -> dict:
        return RemoteContext._id_map


class EnvBridge:
    """Awaitable ENV actions, with mode-specific pacing."""

    def __init__(
        self,
        delay_policy: DelayPolicy = calculate_action_delay,
        response_timeout: float = 5.0,
    ):
        self.delay_policy = delay_policy
        self.response_timeout = response_timeout

    async def get_env_response(
        self, request_id: Any, timeout_seconds: Optional[float] = None
    ) -> Any:
        """Wait for the outcome the hub listener files under `request_id`."""
        timeout = self.response_timeout if timeout_seconds is None else timeout_seconds
        start_time = time.time()
        console.print(
            f"⏳ Waiting for ENV response ID: {request_id}, timeout set to: {timeout}s",
            style="cyan",
        )

        while True:
            response = RemoteContext.get_id_map().get(request_id, None)
            if response is not None:
                RemoteContext.get_id_map().pop(request_id, None)
                elapsed = time.time() - start_time
                console.print(
                    f"✅ Received ENV response ID: {request_id}, elapsed time: {elapsed:.2f}s",
                    style="cyan",
                )
                return response

            elapsed = time.time() - start_time
            if elapsed >= timeout:
                console.print(
                    f"⏰ ENV response timeout ID: {request_id}, elapsed time: {elapsed:.2f}s",
                    style="red",
                )
                console.print(
                    f"🔍 Current ID mapping state: {dict(RemoteContext.get_id_map())}",
                    style="red",
                )
                error = TimeoutError(
                    f"ENV response timeout: ID {request_id}, timeout time: {timeout}s"
                )
                error.request_id = request_id
                error.elapsed_time = elapsed
                error.timeout_seconds = timeout
                raise error

            await asyncio.sleep(0.1)

    async def perform_action(self, action: str, params: Any) -> Any:
        """Send one action and wait for its outcome."""
        # `end_turn` is a standalone tool with its own gate handling; routing it
        # through here would skip that and leave the turn gate open.
        if action == "end_turn":
            raise ValueError(
                "Invalid tool usage: 'end_turn' must be called via the standalone "
                "'end_turn' tool, not 'perform_action'."
            )

        try:
            client = RemoteContext.get_client()
            request_id = await client.send_action(action, params)
            response = await self.get_env_response(request_id)

            delay = self.delay_policy(action, params, response)
            if delay > 0:
                console.print(
                    f"⏳ Waiting for {delay}s to complete the action...", style="cyan"
                )
                await asyncio.sleep(delay)

            return response

        except TimeoutError as e:
            console.print(
                f"⏰ [perform_action] Action execution timeout: {e}", style="red"
            )
            handle_error_with_logging(
                e,
                function_name="perform_action",
                action=action,
                params=params,
                request_id=getattr(e, "request_id", "unknown"),
                elapsed_time=getattr(e, "elapsed_time", "unknown"),
                timeout_seconds=getattr(e, "timeout_seconds", "unknown"),
            )
            raise
        except Exception as e:
            console.print(f"❌ [perform_action] Action execution error: {e}", style="red")
            handle_error_with_logging(
                e, function_name="perform_action", action=action, params=params
            )
            raise

    async def perform_multiple_actions(
        self,
        actions: List[Any],
        params: Optional[List[Dict[str, Any]]] = None,
    ) -> Any:
        """Send several actions in one ENV message.

        Accepts either a list of `{"id", "action", "parameters"}` dicts, or a
        list of action names paired with a matching list of parameter dicts.
        """
        try:
            if not actions:
                return {"results": [], "count": 0}

            if params is None and isinstance(actions[0], dict):
                requests: List[Dict[str, Any]] = []
                for item in actions:
                    if "action" not in item:
                        raise ValueError(
                            "Each action dict must include an 'action' field"
                        )
                    requests.append(
                        {
                            "id": item.get("id") or f"toolcall_{int(time.time() * 1e6)}",
                            "action": item["action"],
                            "parameters": item.get("parameters")
                            or item.get("params")
                            or {},
                        }
                    )
            else:
                if params is None:
                    raise ValueError(
                        "params must be provided when actions are not action dicts"
                    )
                if len(actions) != len(params):
                    raise ValueError("actions and params must have the same length")
                timestamp = int(time.time() * 1e6)
                requests = [
                    {
                        "id": f"toolcall_{timestamp}_{idx}",
                        "action": name,
                        "parameters": param or {},
                    }
                    for idx, (name, param) in enumerate(zip(actions, params))
                ]

            client = RemoteContext.get_client()
            request_id = await client.send_actions(requests)
            return await self.get_env_response(request_id)

        except TimeoutError as e:
            console.print(
                f"⏰ [perform_multiple_actions] Action execution timeout: {e}",
                style="red",
            )
            handle_error_with_logging(
                e,
                function_name="perform_multiple_actions",
                action=actions,
                params=params,
                request_id=getattr(e, "request_id", "unknown"),
                elapsed_time=getattr(e, "elapsed_time", "unknown"),
                timeout_seconds=getattr(e, "timeout_seconds", "unknown"),
            )
            raise
        except Exception as e:
            console.print(
                f"❌ [perform_multiple_actions] Action execution error: {e}", style="red"
            )
            handle_error_with_logging(
                e,
                function_name="perform_multiple_actions",
                action=actions,
                params=params,
            )
            raise

    async def get_available_actions(self) -> Any:
        """Ask the ENV which actions it currently accepts."""
        return await self.perform_action("get_action_list", {})

    async def send_end_turn(self, faction: str) -> Any:
        """End the turn. The caller owns the turn-gate consequences."""
        client = RemoteContext.get_client()
        request_id = await client.send_action("end_turn", {"faction": faction})
        return await self.get_env_response(request_id)

    async def send_turn_start_ack(self, faction: str, turn_number: int) -> None:
        """Acknowledge a turn start so the ENV stops resending it."""
        client = RemoteContext.get_client()
        await client.send_action(
            "turn_start_ack", {"faction": str(faction).lower(), "turn_number": turn_number}
        )


__all__ = ["RemoteContext", "EnvBridge", "DelayPolicy"]
