# Using STAR and connecting Agents

For gameplay, victory conditions and controls, see [game rules](game-rules.md).
This guide covers desktop/browser play and the existing Agent connection path.

## Install and start

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and the
[Rust toolchain](https://www.rust-lang.org/tools/install). From a terminal:

```bash
git clone https://github.com/star-nexus/star.git
cd star
uv run starbench.py --no-hub
```

The launcher prepares dependencies automatically. The first launch builds the
Rust ENV and may take longer. Choose a map and start from the menu. Offline AI
slots have no automatic opponent and make no model calls.

| Goal | Command |
| --- | --- |
| Desktop preview without Hub | `uv run starbench.py --no-hub` |
| Connected desktop match | `uv run starbench.py --env-id env_1` |
| Headless two-Agent real-time match | `uv run starbench.py --headless --players ai_vs_ai --mode real_time --env-id env_1` |
| Repeat a map/RNG seed | `uv run starbench.py --no-hub --scenario chibi-small --seed 42` |
| Local BOT demo | `uv run starbench.py --backend python --skip-start --no-hub --mock-ai --players human_vs_two_ai` |
| Launch options | `uv run starbench.py --help` |

Rust is the default backend. `--headless` removes the desktop window;
`--no-hub` disables networking. A missing or incompatible Rust installation
produces an error rather than silently changing the backend. The same seed
repeats map/random choices, but does not fix model latency or network ordering.

## Play in a browser

Install Node/npm, then prepare the pinned browser dependency once:

```bash
npm ci --prefix rotk_env/rendering/web/client
uv run starbench.py --renderer web --no-hub --scenario chibi-small --seed 42
```

Open a faction or spectator link printed by the terminal. By default, Web uses
two human factions. All links share one match; faction credentials determine
the visible information and whether commands are permitted. Spectator and
AI-slot links are read-only. Keep control links private. Restarting the server
creates new credentials, so use the newly printed links.

The simulation runs on the server; the browser must stay connected. Select a
unit to see its movement/attack preview. The FPS corner label counts browser
draws and updates about once a second; it is separate from simulation speed.

To connect Web to a Hub, specify its address:

```bash
uv run starbench.py --renderer web --players human_vs_ai \
  --hub-url ws://localhost:8000/ws/metaverse --env-id env_1
```

Web defaults to offline unless `--hub-url` or `STAR_HUB_URL` is supplied.
`--no-hub` takes precedence. Web does not support desktop `--headless` or
the local BOT option. Agents still use the Hub, rather than browser control links.

## Connect through the Hub

**Terminal 1 — start GameServer.** Clone it alongside STAR:

```bash
git clone https://github.com/star-nexus/GameServer.git
cd GameServer
uv run fastapi dev gameserver/main.py
```

**Terminal 2 — start ENV from STAR:**

```bash
uv run starbench.py --env-id env_1
```

Choose the game mode, AI slots and **External Agent / Hub**, then start. Wait
for the Hub connection to be confirmed. Use the same `env_id` in ENV and Agents,
and a unique `agent_id` for each participant. Each Agent's faction and mode must
match its ENV slot. Three-faction matches require a three-faction layout.

**Terminal 3 — check the connection without a model:**

```bash
uv run rotk_agent/main.py \
  --env-id env_1 --agent-id agent_1 --faction wei \
  --provider fake --mode turn_based
```

`fake` is a scripted connection-check participant. Repeat with another unique
Agent ID and faction for the opposing slot. To use a model, configure a provider
in `.configs.toml` and replace `fake` with its profile name; see
[the reference Agent guide](../rotk_agent/README.md) and the
[root quick start](../README.md#-quick-start).

Use the same Hub URL in every process. The default is
`ws://localhost:8000/ws/metaverse`; `--hub-url` or `STAR_HUB_URL` selects another
Hub. If local connections fail, check GameServer and your proxy/VPN. On
macOS/Linux, exclude local traffic before launching:

```bash
export NO_PROXY="localhost,127.0.0.1,::1" no_proxy="localhost,127.0.0.1,::1"
```

## Bring your own Agent

Use `protocol.AgentClient`. Your Agent does not need to import `rotk_agent`,
`rotk_env` or the Rust extension. `rotk_agent` is an optional reference client.

The session flow is:

1. Connect and call `register_agent_info` with your faction and model identity.
2. Read the reply's map bounds and permitted `game_actions`.
3. Query `get_faction_state`, choose an available action and inspect its outcome.
4. In turn-based mode, handle/acknowledge `turn_start` and call `end_turn`.
5. On `game_end_notification`, submit `report_llm_stats` and disconnect. Non-LLM
   Agents report zero usage.

The default benchmark uses one Agent process per faction. Multiple Agents can
use the same faction with unique IDs; unit ownership still governs commands.
Always use unit IDs returned by the current match, rather than hard-coded IDs
or IDs from an earlier recording.

A no-model protocol probe is available after ENV connects:

```bash
uv run python examples/protocol_conformance.py --faction wei --mode turn_based
```

| Reference | Use it for |
| --- | --- |
| [Agent–ENV protocol](agent-protocol.md) | Registration, actions, turns and settlement |
| [Observations and action availability](observation-affordance.md) | State fields, movement/attack choices and image capability |
| [Hub messages](hub-envelope.md) | Message shapes, request IDs, batches and error codes |

For batch evaluation with the reference clients, see
[the root batch instructions](../README.md#running-agent-evaluation-in-batch).
