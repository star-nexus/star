# Native runtime migration

The default game remains Python. R0 normalizes its replay ordering; R1 provides
an owned Rust scene, lifecycle/clock and CPython-compatible random streams.
**The Rust backend is not yet playable.** R3 is in progress: native movement,
resource recovery, combat, Fog, statistics, team state and faction projections
have differential contract tests. Trusted local registration, ownership checks and
move/attack/faction-query dispatch, world termination and faction turn handoff
are connected, including the five non-image observation variants. VLM frame capture,
settlement and window handoff are still pending. There is no silent backend fallback.

The Cargo workspace has three crates:

- `native/core`: generic ECS ownership, stable external IDs, simulation clock, RNG.
- `native/rotk`: RoTK scene/rules and native runtime.
- `native/python`: PyO3 binding and the standalone `star-native` Python package.

Rust 1.98.1, bevy_ecs 0.19.1, PyO3 0.29.2 and maturin 1.15.0 are pinned.
`Cargo.lock` records the complete Rust dependency resolution. Bevy rendering is
not included. Build/install for development from the repository root:

```sh
# Requires the pinned Rust toolchain on PATH for local source builds.
uv sync --extra native
cargo test -p star-core -p star-rotk --locked
cargo clippy --workspace --all-targets --locked -- -D warnings
uv run --extra native pytest -q
```

After editing Rust files, rebuild explicitly with
`uv sync --extra native --reinstall-package star-native` to avoid an old extension
in the active interpreter. Start a fresh Python process after rebuilding.
Performance measurements must use a release wheel, with its hash recorded in Lab.
Users of eventual published wheels will not need a Rust compiler. Cross-platform
wheel release/install acceptance remains R5 work.

R1 initialization can be exercised without changing the game entry point:

```python
from rotk_env.runtime.bootstrap import prepare_scene
from rotk_env.runtime.native import RustRuntime

initial = prepare_scene(mode="real_time", scenario="chibi-small", seed=42)
with RustRuntime(initial, threads=1) as runtime:
    assert not runtime.diagnostics()["gameplay_ready"]
    runtime.step(1 / 30, wall_time=1720000000.0)
    print(runtime.diagnostics())
```

`prepare_scene` uses the current Python loader once, returns detached data and
cleans up the temporary world. Hub/BOT startup is prohibited there; subscriptions
are isolated and restored. The native world never retains Python component
references. Imported component columns currently preserve cold initial state;
typed gameplay computation is added in R2/R3. `export_state` is a diagnostic
operation, not a per-frame synchronization mechanism.

The R2 intermediate implementation includes dynamic unit occupancy and stable
A* ties, instantaneous rule-mode movement and animated dummy/window movement,
and the existing severe-headcount-loss MP rule. Movement advances only active
units. AP/MP/skill cooldowns use versioned deadline buckets; an imported scene
preserves the scheduler ledger, including superseded tasks and pending MP spends.
Paused simulation time never advances recovery. Repeated AP spends preserve the
active cadence; MP recovery restarts at the next advancing recovery boundary.

Private `_movement_probe_json`, `_resource_probe_json`, `_combat_probe_json`
and `_vision_probe_json`
methods exist only for differential tests. They are **not Agent action APIs**:
they have no registration/claim authorization boundary. The combat probe currently
supports rule mode with normal or fallback statistics; presentation combat entities
remain pending. Do not route Agents through
these probes or use them for a capacity claim. `gameplay_ready` remains false.

`_team_probe_json` and `_observation_probe_json` also exercise internal contracts
only. Team ownership has a reverse index for release-all; existing inboxes retain
their original FIFO capacity across import/reset. Faction queries share census,
unit panels, enemy facts and terrain only within one immutable runtime borrow.
Per-request owner/commandable fields are assembled separately. A later call starts
a fresh batch, so a move/query/attack sequence cannot reuse a pre-move snapshot.
The current projection still clones response trees and performs some full scans;
no 5K/10K throughput or parallel speedup is claimed.

The staged public interface is `RustRuntime.execute_action` and `execute_actions`.
The caller supplies trusted `agent_id` separately from action parameters; a Hub
adapter must derive it from the authenticated connection. The local API does not
authenticate a network peer or connect Hub. Supported requests currently include
registration, claim/release, list/broadcast/read team messages, action discovery,
move, attack, rest, occupy, fortify, skill, `end_turn` and `get_faction_state`. Attack presentation is still rule-mode only.
Other configured gameplay verbs fail explicitly until their migration is complete.

```python
from rotk_env.runtime.native import ActionRequest

with RustRuntime(initial) as runtime:
    result = runtime.execute_action("register_agent_info", {
        "faction": "wei", "provider": "synthetic", "model_id": "fake",
        "base_url": "http://local",
    }, agent_id="agent-1")
    responses = runtime.execute_actions([
        ActionRequest("agent-1", "get_faction_state", {"faction": "wei"}),
        ActionRequest("agent-1", "get_faction_state", {"faction": "wei", "unit_ids": []}),
    ])
```

Batch requests execute in supplied order, without waiting to collect more work.
Only adjacent faction queries share an immutable native read context. An intervening
command ends that context even if it fails. This preserves move → query → attack
and claim/release → query visibility. Query action counters are committed in order
at the read-segment boundary under the same exclusive runtime lock; projections do
not read those counters. No other observer can see an intermediate deferred count.
`execute_actions_diagnostic` returns the same results plus segment boundaries and
cache-build counts for Lab. Batch size is chosen by the caller, with no internal
unbounded request queue; nothing persists beyond the call.

Parameters must already be normalized dictionaries containing JSON data. Envelope
serialization/deserialization errors occur before executing the batch. Execution
is sequential, not transactional: prior commands and legacy partial writes are not
rolled back if a later request fails. Ordinary game errors remain per-request
responses; an unsupported native capability or internal failure raises visibly.
Responses own their data across later queries/reset/close. There is no default
backend change or capacity acceptance from this interface checkpoint.

The current native rules marker is `python-r0c-3cc4ffe`. R0b adds lexical ordering
for available skill names, omitted by the initial R0 normalization. Old oracle
tags and historical extension wheels remain reproducible at their recorded source.
R0c also orders the two legacy/named observation terrain lists by coordinates.
The runtime now has API version4 and scene schema4 in addition to the rules marker.
The current Python adapter rejects extensions without the matching API marker;
scene schemas1/2/3 are rejected on import/reset. This prevents older R2 kernels from
silently ignoring newly introduced lifecycle, territory or observation-cache metadata. Rebuild after source changes;
experimental historical traces must use their exact source and wheel.

Native Fog preserves line of sight, terrain bonuses, overlapping faction vision,
exploration and geometry-cache ordering. Death invalidation is consumed at the
next vision update, matching Python. Statistics retain ordinary periodic sampling
and the window's bounded multi-frame cycle, including reset partway through a
cycle. Their historical wall timestamps are injected metadata; resource cooldowns
still advance only from simulation time. The bootstrap codec also preserves
public runtime attributes attached to dataclasses. Registration metadata was
already declared in GameStats; the earlier codec did not drop those fields. Fog presentation deltas and the actual window integration are pending.

Realtime/turn-mode world updates now apply the existing game-over policy: mutual
annihilation, one remaining faction, then timeout (in that precedence). Realtime
timeout uses simulation elapsed seconds. Derived living-faction counts are built on
import/reset and updated on death, so this check does not scan all Units each frame.
The window index's position requirement is retained. GameTimeSystem/AnimationSystem
and lifecycle enabled flags survive import. Agent `end_turn` rotates factions and resets AP/MP/status only on round rollover.
The trusted Framework method `finish_human_turn` preserves the human reset-before-
check path. Turn statistics, battle logs and TurnStartEvent keep their old order;
the GameTime round number synchronizes on the next tick. Cooldown/skill behavior
is not rebalanced. Settlement orchestration and actual window input handoff remain
pending. The small Player lookup table is derived on import/reset; future commands
that change Player membership/faction must also update it.

The initialization codec preserves the difference between `UnitState` enum values
and historical raw status strings, since Python's coefficient lookup distinguishes
them. It does not normalize or rebalance those rules during migration.

`step(dt)` advances the simulation clock from dt. Its optional wall timestamp is
external metadata, never the source of CD/recovery elapsed time. Clock changes
have an explicit command boundary. Invalid reset leaves the existing world intact;
valid reset starts a new epoch. Returned data belongs to Python and remains usable
after reset/close; its epoch identifies the old lifecycle. Close is idempotent and
subsequent computation on the closed instance fails.

All native operations detach from Python before acquiring the world mutex.
The mutex serializes writes and diagnostics; it is not a claim of parallel ECS
execution. Worker scheduling is R4 work. A poisoned instance fails visibly and
never resumes by constructing another world. RNG compatibility includes BLAKE2b
64-bit domain seeds, CPython integer seeding, MT state, random/getrandbits,
randbelow/randint, choice via randbelow, uniform and shuffle. The bounded
getrandbits probe supports the 0–64-bit range used by the kernel; it is not a
replacement for Python's unrestricted `random` module.

See [ordering contract](runtime-determinism.md),
[PyO3 detachment](https://pyo3.rs/v0.29.2/parallelism) and
[Bevy ECS](https://docs.rs/bevy_ecs/0.19.1/bevy_ecs/).

The remaining unit-action dispatch preserves the current Python rules, including
legacy behavior that must be fixed separately from this migration:

- Rest increments the wait streak, clears enum confusion on the second wait, and
  does not consume AP or restore SP. A raw status string stays distinct.
- Agent occupy immediately changes the current/adjacent tile owner and spends one
  AP. The Framework `start_capture(unit_id, (col, row))` creates a separate timed
  capture task. It completes on a later update, using simulation time in realtime
  and one update in turn mode; city task metadata says two AP but consumes one.
- Fortification checks AP/CP, spends them only in turn mode, and builds level one.
  The handler reports one AP less than the resulting state. There is no added range
  check or upgrade rule. Territory bonuses participate in combat when its system
  is installed, even if updates are disabled.
- The existing terrain-skill helper returns `success`, but its caller checks
  `result`. Valid terrain therefore returns `Skill execution failed` without
  AP/SP/cooldown effects. The Rust version preserves this mismatch; it does not
  claim to add working terrain skills.

Territory components and capture entities are Rust-owned. Unfinished capture IDs
form an ordered active set, rebuilt on reset, so the capture update is O(active).
A vanished capturing unit removes its task without clearing the tile's capture
marker, as in Python. A unit moving away cancels the marker. Existing completed
capture entities remain inert. Actual window buttons will be wired in the later
presentation handoff. These contracts do not constitute a capacity measurement.


R3b adds `observation`, `unit_observation`, `faction_observation`,
`limited_observation` and `godview_observation` to the same trusted action API.
The match must explicitly enable these actions. Each keeps its own historical
visibility, optional fields, readiness and error behavior. Common own-unit facts
are shared with `get_faction_state`; geometric reachability remains dynamic.

Named observations cache immutable results at the current world revision. The
public `from_cache` flag and original wall timestamp are retained on a hit.
Writes/ticks invalidate this cache, including failed mutating actions after
dispatch. Import/reset carries only cache entries valid in the imported world;
old-world results cannot become new-world observations. This is separate from
the call-scoped `get_faction_state` batch cache. No TTL or past-frame observation
has been introduced. The diagnostic scene includes this cache because its hit
metadata is observable. The Python unit observation still returns a `set` of
coordinate tuples in `data.visible_area`; the native JSON boundary uses a tagged
set for that field, decoded only at that exact schema location by the adapter.

The existing god-view BattleLog attribute mismatch is preserved: normal nonempty
BattleLogEntry lists cause `INTERNAL_ERROR` (missing `turn`), as in Python. This
migration does not silently repair rules or legacy API quirks. VLM frame capture,
actual window integration, BOT/settlement, and parallel workers remain pending.
