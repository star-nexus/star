"""`AgentClient` request/response behaviour, without a real websocket.

`send_message` is the only transport touchpoint, so a fake ENV is just a stub
that records envelopes and feeds outcomes back through the client's own hub
listeners -- the same path a live Hub would use.
"""

import asyncio
import json

import pytest

from protocol import AgentClient
from protocol.star_client_v2.exceptions import (
    ActionTimeout,
    ConnectionError as ClientConnectionError,
    MessageError,
    ProtocolError,
)
from protocol.star_client_v2.types import MessageType


class FakeEnv:
    """Stands in for the Hub plus ENV.

    `auto_reply` mirrors the ENV's normal behaviour: every action gets an
    outcome. Tests that care about timing set it False and reply by hand.
    """

    def __init__(self, client: AgentClient, auto_reply=True, echo_id_as_str=False):
        self.client = client
        self.sent: list[dict] = []
        self.auto_reply = auto_reply
        self.echo_id_as_str = echo_id_as_str
        self.send_result = True
        self.raise_on_send: Exception | None = None
        client.send_message = self._send_message  # type: ignore[method-assign]

    async def _send_message(self, instruction, data, target=None):
        if self.raise_on_send is not None:
            raise self.raise_on_send
        self.sent.append({"instruction": instruction, "payload": data, "target": target})
        if self.auto_reply and self.send_result:
            self.reply(data.get("id"), {"success": True, "action": data.get("action")})
        return self.send_result

    def _deliver(self, event: str, payload: dict) -> None:
        for handler in self.client.hub_event_handlers.get(event, []):
            handler({"payload": payload})

    def reply(self, request_id, outcome, outcome_type="str") -> None:
        """Send an `outcome` back, as the ENV would."""
        if self.echo_id_as_str:
            request_id = str(request_id)
        self._deliver(
            "message",
            {
                "type": "outcome",
                "id": request_id,
                "outcome": outcome,
                "outcome_type": outcome_type,
            },
        )

    def error(self, request_id, message="boom") -> None:
        self._deliver("error", {"id": request_id, "error": message})

    def disconnect(self, reason="hub closed") -> None:
        for handler in self.client.hub_event_handlers.get("disconnect", []):
            handler({"reason": reason})


@pytest.fixture
def client():
    return AgentClient("ws://test", "env_1", "agent_1", action_timeout=1.0)


# ------------------------------------------------------------------ happy path


async def test_call_returns_the_outcome(client):
    env = FakeEnv(client)
    outcome = await client.call("get_faction_state", {"faction": "wei"})
    assert outcome == {"success": True, "action": "get_faction_state"}


async def test_call_sends_a_well_formed_action(client):
    env = FakeEnv(client)
    await client.call("move", {"unit_id": 3})

    assert len(env.sent) == 1
    sent = env.sent[0]
    assert sent["instruction"] == MessageType.MESSAGE.value
    assert sent["target"] == {"type": "env", "id": "env_1"}
    assert sent["payload"]["type"] == "action"
    assert sent["payload"]["action"] == "move"
    assert sent["payload"]["parameters"] == {"unit_id": 3}
    assert "id" in sent["payload"]


async def test_request_ids_are_json_safe(client):
    """Ids must survive a JSON round trip unchanged."""
    env = FakeEnv(client)
    await client.call("move", {})
    request_id = env.sent[0]["payload"]["id"]
    assert json.loads(json.dumps(request_id)) == request_id


async def test_outcome_with_stringified_id_still_matches(client):
    """The regression that used to look like a timeout.

    A JSON layer between agent and ENV may turn `123` into `"123"`.
    """
    env = FakeEnv(client, echo_id_as_str=True)
    assert await client.call("move", {}) == {"success": True, "action": "move"}


async def test_concurrent_calls_get_their_own_outcomes(client):
    env = FakeEnv(client, auto_reply=False)

    tasks = [
        asyncio.create_task(client.call("move", {"unit_id": i}, timeout=2.0))
        for i in range(5)
    ]
    await asyncio.sleep(0)

    ids = [s["payload"]["id"] for s in env.sent]
    assert len(set(ids)) == 5, "ids must be unique"

    for i, request_id in enumerate(reversed(ids)):  # answer out of order
        env.reply(request_id, {"index": i})

    results = await asyncio.gather(*tasks)
    for i, result in enumerate(reversed(results)):
        assert result == {"index": i}


async def test_pending_requests_clears_after_a_call(client):
    env = FakeEnv(client)
    await client.call("move", {})
    assert client.pending_requests == []


# ---------------------------------------------------------------- batch calls


async def test_call_many_returns_the_batch_outcome(client):
    env = FakeEnv(client, auto_reply=False)
    task = asyncio.create_task(
        client.call_many([{"action": "move"}, {"action": "attack"}], timeout=2.0)
    )
    await asyncio.sleep(0)

    payload = env.sent[0]["payload"]
    assert payload["type"] == "action_batch"
    assert [a["action"] for a in payload["actions"]] == ["move", "attack"]

    env.reply(payload["id"], {"results": ["a", "b"]})
    assert await task == {"results": ["a", "b"]}


async def test_batch_preserves_caller_supplied_item_ids(client):
    """Per-item ids are the LLM's tool-call ids; regenerating them breaks replies."""
    env = FakeEnv(client, auto_reply=False)
    asyncio.create_task(
        client.call_many(
            [{"action": "move", "id": "toolcall_abc"}, {"action": "rest"}], timeout=2.0
        )
    )
    await asyncio.sleep(0)

    actions = env.sent[0]["payload"]["actions"]
    assert actions[0]["id"] == "toolcall_abc"
    assert actions[1]["id"], "missing ids must be generated"


async def test_batch_rejects_an_item_without_an_action(client):
    FakeEnv(client)
    with pytest.raises(ValueError, match="action"):
        await client.call_many([{"parameters": {}}])


# -------------------------------------------------------------------- failures


async def test_timeout_raises_action_timeout_naming_the_action(client):
    FakeEnv(client, auto_reply=False)
    with pytest.raises(ActionTimeout) as excinfo:
        await client.call("move", {}, timeout=0.01)
    assert excinfo.value.action == "move"


async def test_timeout_is_also_a_builtin_timeout_error(client):
    """Callers written against the old polling loop caught the builtin."""
    FakeEnv(client, auto_reply=False)
    with pytest.raises(TimeoutError):
        await client.call("move", {}, timeout=0.01)


async def test_hub_error_surfaces_as_protocol_error(client):
    env = FakeEnv(client, auto_reply=False)
    task = asyncio.create_task(client.call("move", {}, timeout=2.0))
    await asyncio.sleep(0)

    env.error(env.sent[0]["payload"]["id"], "env exploded")
    with pytest.raises(ProtocolError, match="env exploded"):
        await task


async def test_disconnect_fails_pending_calls_immediately(client):
    """Otherwise every in-flight call waits out its own timeout."""
    env = FakeEnv(client, auto_reply=False)
    task = asyncio.create_task(client.call("move", {}, timeout=30.0))
    await asyncio.sleep(0)

    env.disconnect("hub restarted")
    with pytest.raises(ClientConnectionError, match="hub restarted"):
        await asyncio.wait_for(task, timeout=1.0)


async def test_failed_send_raises_rather_than_hanging(client):
    env = FakeEnv(client)
    env.send_result = False
    with pytest.raises(MessageError):
        await client.call("move", {})
    assert client.pending_requests == []


async def test_transport_exception_propagates(client):
    env = FakeEnv(client)
    env.raise_on_send = RuntimeError("socket gone")
    with pytest.raises(RuntimeError, match="socket gone"):
        await client.call("move", {})


# ------------------------------------------------------------ fire and forget


async def test_fire_and_forget_reserves_no_slot(client):
    env = FakeEnv(client, auto_reply=False)
    await client.send_action("turn_start_ack", {"faction": "wei"}, expect_outcome=False)
    assert client.pending_requests == []


async def test_unsolicited_outcome_is_ignored_not_crashing(client):
    env = FakeEnv(client, auto_reply=False)
    env.reply("an-id-nobody-sent", {"success": True})
    assert client.pending_requests == []


async def test_non_outcome_messages_are_ignored(client):
    env = FakeEnv(client, auto_reply=False)
    env._deliver("message", {"type": "turn_start", "faction": "wei"})
    env._deliver("message", {})
    assert client.pending_requests == []
