# The Hub envelope

The wire format between agents, the ENV, and the Hub. This is the transport
layer; what an agent should *say* is in
[`agent-protocol.md`](agent-protocol.md), and what it can *see* is in
[`observation-affordance.md`](observation-affordance.md).

Machine-readable schemas live in [`protocol/schemas/`](../protocol/schemas/) and
are checked against the SDK by
[`protocol/tests/test_schemas.py`](../protocol/tests/test_schemas.py), so this
document and the code cannot drift apart silently.

| | |
| :--- | :--- |
| Envelope | [`envelope.schema.json`](../protocol/schemas/envelope.schema.json) |
| Payloads | [`payloads.schema.json`](../protocol/schemas/payloads.schema.json) |
| Error codes | [`error_codes.schema.json`](../protocol/schemas/error_codes.schema.json) |

---

## 1. Envelope

Every message in both directions has the same outer shape. The Hub routes on
`type`, `sender` and `recipient`; it does not look inside `payload`.

```json
{
  "type": "message",
  "sender":    { "type": "agent", "id": "agent_1" },
  "recipient": { "type": "env",   "id": "env_1" },
  "payload":   { "type": "action", "id": "7", "action": "move",
                 "parameters": { "unit_id": 3, "target_position": [2, 4] } },
  "timestamp": 1717171717.123
}
```

| Field | Notes |
| :--- | :--- |
| `type` | Transport instruction: `message`, `broadcast`, `heartbeat`, `connect`, `disconnect`, `error`. Business traffic is always `message`. |
| `sender` / `recipient` | `{type, id}` where type is `agent`, `env`, `human` or `hub`. `hub` is a singleton and uses `id: ""`. |
| `payload` | The business message. Opaque to the Hub. |
| `timestamp` | Unix seconds, set by the sender. Informational — **never** used for correlation. |

`AgentClient` builds this for you; `build_message_envelope` is the single place
it is constructed.

### Connecting

```
ws://<hub>/env/{env_id}/agent/{agent_id}     # agent
ws://<hub>/env/{env_id}                      # environment
```

Default Hub is `ws://localhost:8000/ws/metaverse`. A heartbeat goes out every
30 seconds; the Hub drops silent connections.

---

## 2. Payloads

Agent → ENV is `action` or `action_batch`. ENV → agent is `outcome`, plus the
unsolicited `turn_start` and `game_end_notification`.

### `action`

```json
{ "type": "action", "id": "7", "action": "move",
  "parameters": { "unit_id": 3, "target_position": [2, 4] } }
```

`parameters` defaults to `{}`. The legal verb set for a match comes from the
`register_agent_info` reply, not from this schema.

### `action_batch`

```json
{ "type": "action_batch", "id": "batch-3",
  "actions": [
    { "id": "toolcall_a", "action": "move",   "parameters": { "unit_id": 1 } },
    { "id": "toolcall_b", "action": "attack", "parameters": { "unit_id": 1, "target_id": 9 } }
  ] }
```

One reply comes back, carrying the **batch** `id`. Per-item ids are echoed
inside the result body; they exist so an LLM's tool-call ids survive the round
trip, and the SDK preserves any you supply.

### `outcome`

```json
{ "type": "outcome", "id": "7", "outcome": "{\"success\": true, ...}", "outcome_type": "str" }
```

When `outcome_type` is `"str"`, `outcome` is a JSON-encoded string the agent
must decode. The decoded body always has `success`; on failure it also has
`error`, `error_code` and `message`.

### `turn_start` and `game_end_notification`

Unsolicited, turn-based mode only for `turn_start`. It has no request id
because it is not a reply. The ENV **resends** it until the agent either sends
`turn_start_ack` or sends any other action, so an agent that ignores it will
see duplicates rather than a lost turn.

---

## 3. Correlation

**The `id` is the only correlation key.** The ENV echoes back exactly what it
received.

Three rules, each of which was a real bug:

1. **Compare ids as strings.** The schema allows an int or a string, and JSON
   layers between agent and ENV may render `7` as `"7"`. An implementation that
   keyed on the raw value saw no match and reported a timeout instead.
2. **Keep ids under 2**53.** Anything larger is not guaranteed to survive a
   JSON round trip. The SDK previously used `uuid.uuid4().int` (128-bit); it now
   issues short strings.
3. **Register before sending.** The ENV can answer faster than the caller gets
   from `send` to `await`. Reserve the slot first, or the reply lands before
   anything is listening for it.

`AgentClient` does all three. `await client.call(action, params)` sends and
returns the outcome; you never touch an id unless you want to.

```python
from protocol import AgentClient, ActionTimeout

client = AgentClient("ws://localhost:8000/ws/metaverse", "env_1", "agent_1")
await client.connect()
try:
    state = await client.call("get_faction_state", {"faction": "wei"})
except ActionTimeout as e:
    print(f"{e.action} went unanswered after {e.timeout_seconds}s")
```

Use `send_action` + `await_outcome` only when you need the two halves apart.
Pass `expect_outcome=False` for genuine fire-and-forget (`turn_start_ack`).

A disconnect fails every in-flight call immediately rather than making each one
wait out its own timeout.

---

## 4. Error codes

Defined once in [`protocol/error_codes.py`](../protocol/error_codes.py); the
ENV's table and the JSON schema are both derived from it.

| Code | Name | Meaning | Retry? |
| ---: | :--- | :--- | :--- |
| 2001 | `GAME_NOT_INITIALIZED` | Game not initialized | no |
| 2002 | `GAME_ALREADY_FINISHED` | Game already finished | no |
| 2003 | `ACTION_NOT_IN_MATCH` | Verb exists in ENV but not in this match | no |
| 2004 | `INSUFFICIENT_RESOURCES` | Insufficient system resources | no |
| 2005 | `INSUFFICIENT_PERMISSIONS` | Not your unit / not your faction's screen | no |
| 2006 | `OPERATION_TIMED_OUT` | Operation timed out | **yes** |
| 2007 | `PARAMETER_VALIDATION_FAILED` | Bad parameter shape or value | no |
| 2008 | `INVALID_SYSTEM_STATE` | Invalid system state | no |
| 2009 | `NETWORK_ERROR` | Network connection error | **yes** |
| 2010 | `UNKNOWN_ACTION` | No such verb | no |
| 2011 | `RATE_LIMITED` | Rate limit exceeded | **yes** |
| 2012 | `INTERNAL_ERROR` | The ENV raised while handling the action | **yes** |

"Retry" means resending the *same* request unchanged is worth doing. For the
rest, fix the request or give up; resending only burns turns.

### 2010 vs 2012

These used to be one code, and the ENV drew a load-bearing conclusion from it:
a 2010 could not have changed the board, so it skipped invalidating the
observation cache. That was true for an unknown verb and false for a handler
that raised halfway through a mutation, which then left the next
`get_faction_state` answering from a cache describing a board that had already
changed.

So:

- **2010** — rejected by the action firewall. Nothing ran; the board is
  untouched. Fix the verb name.
- **2012** — a handler ran and raised. The board **may** be partially modified.
  Re-read state before deciding anything.

`ErrorCode.rejected_before_dispatch` is that distinction, and it is what the
ENV now branches on.
