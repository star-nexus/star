# Agent layer

One entry point, one chat loop. What varies between models lives behind
`ModelAdapter`, what varies between game modes behind `ModeStrategy`.

```
main.py          command line -> profile -> adapter + mode -> runner
profiles.py      the model table: one row per model family
core/
  runner.py      hub connection, listener, one agent per expedition
  agent.py       the chat loop: ask, run tools, feed results back
  bridge.py      awaitable ENV actions (perform_action, end_turn, ...)
  tools.py       tool schemas the model sees
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
before the turn is ended for it. `--reasoning-effort low|high|max` (default
`low`) and `--no-carry-reasoning` control thinking budget and whether the
chain stays in context.

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
