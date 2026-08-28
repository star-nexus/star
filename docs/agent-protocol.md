# Agent–ENV protocol

This is the contract a **custom agent** must implement to compete in STARBench.
The plug-in point is [`protocol.AgentClient`](../protocol/star_client_v2/client.py).
You do not import `rotk_agent` or `rotk_env`.

`rotk_agent` / `RoTKChatAgent` is STAR’s **reference LLM client** (tool-use loop,
prompts, scoring). It is not the SDK and not the only legal architecture.

Wire verbs, parameter shapes, and board bounds for a given match come from the
`register_agent_info` reply. Do not hard-code ENV internals.

A no-LLM probe of the MUST sequence lives at
[`examples/protocol_conformance.py`](../examples/protocol_conformance.py).

---

## 1. Connect

Connect a WebSocket as an agent:

```
ws://<hub>/env/{env_id}/agent/{agent_id}
```

Default Hub: `ws://localhost:8000/ws/metaverse`.
`AgentClient(hub_url, env_id, agent_id)` builds that path.

Send business traffic as Hub `message` envelopes whose **payload** is:

| Field | Single action | Batch |
| :--- | :--- | :--- |
| `type` | `"action"` | `"action_batch"` |
| `id` | request id (int or string) | batch id |
| `action` | verb name | — |
| `parameters` | object (default `{}`) | — |
| `actions` | — | list of `{id, action, parameters}` |

ENV replies with payload `type: "outcome"`, **the same `id`**, and `outcome`
(object or JSON string). Match replies to requests by `id`.

`AgentClient.send_action` / `send_actions` wrap this. The LLM-facing tool
`perform_action` exists only inside `rotk_agent`; **it is not on the wire**.

---

## 2. Join

First action MUST be `register_agent_info`.

**Required parameters**

| Field | Notes |
| :--- | :--- |
| `faction` | `"wei"` / `"shu"` / `"wu"` |
| `provider` | Free string. Non-LLM agents may send `"custom"`. |
| `model_id` | Free string. Non-LLM agents may send `"custom"`. |
| `base_url` | Required by the current ENV even for non-LLM agents; a placeholder such as `http://localhost` is fine. |

**Optional:** `agent_id`, `version`, `note`, `enable_thinking`.
If you send `agent_id`, it MUST equal the WebSocket `agent_id`. ENV overwrites
a mismatch with the authenticated sender id.

**Success reply** includes the allow-list for this match:

```json
{
  "success": true,
  "map": {
    "width": 15,
    "height": 15,
    "col_min": -7,
    "col_max": 7,
    "row_min": -7,
    "row_max": 7,
    "map_id": "chibi",
    "home_bases": {
      "wei": {"col": 0, "row": 6, "kind": "home_base"}
    },
    "home_bases_meaning": "..."
  },
  "game_actions": {
    "names": ["move", "attack", "get_faction_state"],
    "docs": { "move": { "description": "...", "parameters": {} } }
  }
}
```

- `map.col_min` / `col_max` / `row_min` / `row_max` are inclusive even-q hex
  bounds. Use them for coordinates; do not assume a centered ±7 board.
- `game_actions.names` is the **only** legal board-verb list for this match.
  `game_actions.docs` gives parameter shapes (types, required, nested
  `col`/`row`, enums). Unknown names are **2010**. A verb that exists in ENV
  but is not in this match is **2003**.
- Default skirmish names: `move`, `attack`, `get_faction_state`. Turn-based
  matches also list `end_turn`.

`get_action_list` returns the same subset (`names` + `docs` under `actions`).
It is MAY; join already carried the list.

---

## 3. Perceive and act

ENV does **not** push observations. Pull state with catalog query verbs
(default: `get_faction_state` with `faction` equal to your own; another
faction is rejected with **2005**).

`get_faction_state` is **observation + current action affordance**: own units
include `reachable` (legal `move` targets now) and `attackable` (legal
`attack` `target_id`s now). Enemies and terrain are observation only. The
benchmark split is in [`docs/observation-affordance.md`](observation-affordance.md).

Mutate the board with names from join `game_actions.names` and parameter
objects from join `docs`. Typical skirmish shapes:

| Action | Parameters |
| :--- | :--- |
| `move` | `unit_id`, `target_position: {col, row}` |
| `attack` | `unit_id`, `target_id` |
| `get_faction_state` | `faction` |

Do not import `rotk_agent.core.tools` or ENV modules for these shapes.

---

## 4. Turn-based vs real-time

**Real-time:** no `turn_start`, no `end_turn` (`end_turn` is **2003**).
The world keeps ticking while you think.

**Turn-based:** ENV pushes (not an `outcome`):

```json
{
  "type": "turn_start",
  "faction": "wei",
  "turn_number": 3,
  "timestamp": 0.0,
  "message": "Your turn starts."
}
```

Retry: every ~8s, at most 5 times, until ACK or game over.

The agent MUST acknowledge. Either:

- send `turn_start_ack` (empty parameters; ENV replies `{success: true}`), or
- send any other business action (ENV treats that as ACK too).

Prefer the dedicated ACK. Then issue board actions. End the turn with
`end_turn` and `{ "faction": "<yours>" }`. `end_turn` is a wire verb in
turn-based matches; it is **not** nested under a `perform_action` wrapper.

`turn_start_ack` is handled in ENV’s action path. It is not listed in
`system_actions` and not in `game_actions.names`.

---

## 5. End of game

ENV pushes:

```json
{
  "type": "game_end_notification",
  "winner": "wei",
  "reason": "game_completed",
  "timestamp": 0.0,
  "message": "Game has ended. Please report your LLM statistics."
}
```

The agent MUST then `report_llm_stats` and disconnect. Settlement waits until
every **registered** faction has reported. Non-LLM agents send zeros.

| Field | Required | Notes |
| :--- | :--- | :--- |
| `faction` | yes | Your faction |
| `api_stats` | yes | Object; see below |
| `toolcall_error_total` | yes | Int; `0` if unused |
| `http_error_total` | yes | Int; `0` if unused |
| `spatial_awareness_error` | yes | Int; `0` if unused |
| `provider` | yes | Same idea as join |
| `model_id` | yes | Same idea as join |

`api_stats` fields (missing keys default to `0` / `0.0` on the ENV side):

`total_calls`, `successful_calls`, `failed_calls`, `success_rate`,
`prompt_tokens`, `completion_tokens`, `reasoning_tokens`,
`prompt_cache_hit_tokens`, `prompt_cache_miss_tokens`, `cache_hit_rate`.

---

## 6. Reference client

| Piece | Role |
| :--- | :--- |
| `protocol.AgentClient` | SDK / plug-in point |
| [`docs/agent-protocol.md`](agent-protocol.md) | This contract |
| `rotk_agent` / `RoTKChatAgent` | Reference LLM tool-use client |
| [`examples/protocol_conformance.py`](../examples/protocol_conformance.py) | No-LLM MUST-sequence probe |
| [`examples/probe_get_faction_state.py`](../examples/probe_get_faction_state.py) | Live fog / vision probe |
| [`examples/multiagent_team.py`](../examples/multiagent_team.py) | Team primitives demo (MAY) |

Do not subclass `RoTKChatAgent` to “plug in an architecture.” Speak this
protocol.

---

## MUST / MAY

**MUST (every session)**

1. Connect with `AgentClient`.
2. `register_agent_info`.
3. Handle `outcome` messages keyed by request `id`.
4. On `game_end_notification`, `report_llm_stats` then disconnect.

**MUST (default skirmish board, from join `names`)**

- `move`, `attack`, `get_faction_state`
- Turn-based only: handle `turn_start`, ACK, `end_turn`

**MAY**

- `strategy_ping` (self-reported rubric; not required to score a match)
- Team: `claim_units`, `release_units`, `list_team`, `broadcast_to_team`,
  `read_team_messages` (default bench is one process per faction)
- `get_action_list`, `retrieve_game_status`
- `action_batch`
- Extra catalog verbs if join `names` includes them (`occupy`, `fortify`, …)

The default evaluation is **one agent process per faction**. Team collab and
the strategy rubric are not part of the competitive MUST surface.
