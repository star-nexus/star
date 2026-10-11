# Agent layer

STAR’s **reference** LLM client for STARBench — not the SDK. The agent–ENV
contract a third party must implement is
[`docs/agent-protocol.md`](../docs/agent-protocol.md) (`protocol.AgentClient`).

One entry point, one chat loop. What varies between models lives behind
`ModelAdapter`, what varies between game modes behind `ModeStrategy`.

```
main.py          command line -> profile -> adapter + mode -> runner
profiles.py      the model table: one row per model family
core/
  runner.py      hub connection, listener, one agent per expedition
  agent.py       the chat loop: ask, run tools, feed results back
  bridge.py      awaitable ENV actions (perform_action, end_turn, ...)
  tools.py       tool schemas the model sees (catalog-backed perform_action)
  filters.py     trims ENV responses before they enter the history
  scoring.py     the strategy rubric (single source of truth)
  stats.py       API and error accounting reported at game end
  config.py      .configs.toml loading
  errors.py      error classification and logging
  delays.py      real-time pacing
adapters/        chat_completions | responses | nemotron | fake
modes/           realtime | turn
prompts/         system_prompt_{realtime,turn}_{cn,en}[_variant].md
tests/           pytest suite
```

## Run

```bash
# provider decides the model profile; mode must match how the ENV was started
uv run rotk_agent/main.py --faction wei --provider deepseek --mode turn_based

# or the shorthand: ENV_ID AGENT_ID FACTION PROVIDER MODE
./run_agent.sh env_1 agent_1 wei deepseek turn_based
```

Useful flags: `--profile` pins the model profile instead of inferring it from
`--provider`, `--lang {cn,en}` picks the prompt language, and
`--max-api-calls-per-turn` caps how long a turn-based agent may deliberate
before the turn is ended for it. `--state-filter {A,B,C,D,E,F}` (default `F`)
selects the faction-state ablation pack. `--reasoning-effort low|high|max` (default
`low`) and `--no-carry-reasoning` control thinking budget and whether the
chain stays in context.

## Controlling reasoning

Two flags govern how much the model thinks and how much of that thinking stays
in context. They only affect model families that expose the corresponding knob
(DeepSeek and the Responses API); elsewhere they are ignored.

| Flag | Default | Effect |
| --- | --- | --- |
| `--reasoning-effort low\|high\|max` | `low` | Per-turn thinking budget. |
| `--carry-reasoning` / `--no-carry-reasoning` | on | Keep the model's own reasoning in the conversation history. |

Reasoning is off entirely for a provider whose `.configs.toml` section sets
`enable_thinking = false`, which is how the baseline control group is defined.

`--carry-reasoning` is on by default because DeepSeek's tool-calling protocol
requires the field back on every later request, and sending the chain verbatim
lets the model continue its previous thought — which is usually cheaper than
re-deriving it as new output tokens. Pass `--no-carry-reasoning` to echo an
empty field instead (still valid, but the model re-thinks each turn). Strategy
scoring reads the reasoning from the reply either way, so the metric is unaffected.

Each successful API call logs `prompt_cache_hit_tokens` / `prompt_cache_miss_tokens`.
Those totals are included in the end-of-game report sent to the ENV.

`max_tokens` defaults to 8192 (reasoning plus the answer). Set it in
`.configs.toml` per provider to override.

Model variants can be defined without duplicating credentials by using
`inherits` in `.configs.toml`:

```toml
[deepseek-v4-flash]
model_id = "deepseek-v4-flash"
api_key = "sk-..."
base_url = "https://api.deepseek.com/chat/completions"
max_tokens = 8192

[deepseek-v4-flash-off]
inherits = "deepseek-v4-flash"
enable_thinking = false
```

## Tools the model sees

The LLM only calls what is registered as a tool. There is one shared
`perform_action` tool in every mode; turn-based mode adds a second tool.

| Tool | When | What it does |
| :--- | :--- | :--- |
| `perform_action` | every mode | ENV verbs allowed in this match. Before join the enum is a local fallback of the skirmish three (`move`, `attack`, `get_faction_state`). After `register_agent_info` the enum, param shapes, and board col/row range are taken from that reply — the agent does not import ENV modules. |
| `end_turn` | turn-based only | Empty-arg tool. Ends the faction's turn and closes the turn gate. Real-time has no turn to end. |

The ENV is the allow-list: a guessed name is **2010**, a verb that exists but is not in this match is **2003**. There is no `STAR_ACTION_PROFILE` upgrade.

`end_turn` is not a `perform_action` action. Nesting it there is intercepted
and rejected: the dedicated tool owns gate handling, and routing through
`perform_action` would skip it. The agent also calls `end_turn` itself when
the per-turn API budget is exhausted.

## Dry run, no model

`--provider fake` swaps in a scripted adapter that plays a short game (look,
move, attack, end turn) against the real hub and ENV. Everything but the model
is exercised, for free and deterministically.

```bash
uv run rotk_agent/main.py --faction wei --provider fake --mode turn_based
```

## Adding a model

Add a section to `.configs.toml`, then add a row to `PROFILES` in `profiles.py`.
Only a genuinely new API shape needs new code, and that code is a new adapter.

## Tests

```bash
uv run pytest
```

The suite covers the pure logic (scoring rubric, response filtering, both wire
formats, profile and prompt resolution) plus the chat loop and turn gate, driven
by scripted replies. No network access and no hub required.
