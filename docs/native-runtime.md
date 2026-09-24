# Native runtime migration

Benchmark compatibility differences and historical fixes are tracked in the
[gameplay and mechanism GAP ledger](native-benchmark-gaps.md). Consult it when
comparing results across Python oracles and experimental native checkpoints.

The default game remains Python. R0 normalizes its replay ordering; R1 provides
an owned Rust scene, lifecycle/clock and CPython-compatible random streams.
**The experimental Rust backend now supports offline local play.** R3 is in progress: native movement,
resource recovery, combat, Fog, statistics, team state and faction projections
have differential contract tests. Trusted local registration, ownership checks and
move/attack/faction-query dispatch, world termination and faction turn handoff
are connected, including the five non-image observation variants and explicitly
enabled VLM capture through the Python display adapter. Network post-game
delivery and BOT integration are still pending. Offline GameScene and settlement now use NativeSession. Local input adapters
now redirect commands to Rust. A derived battlefield
presentation adapter now supports existing Python map, unit and effect renderers. There is no silent backend fallback.

## Product boundary: native execution, Python usability

The migration delivers a Python-facing benchmark powered by a Rust kernel. Its
completion criterion is correct behavior and measured capacity, not the fraction
of source files rewritten in Rust. Preserve the four architectural layers; a
language boundary is not an additional product layer.

| Responsibility | Default placement |
| --- | --- |
| Authoritative ECS state, simulation clock, gameplay transitions, movement/path/occupancy, combat, recovery, Fog, permissions and observation computation | Rust |
| Activity tracking, read-phase scheduling, batch evaluation and measured high-volume data assembly | Rust |
| Public Agent/ENV API, Python SDK, configuration, scenario authoring, launch/CLI, experiments and model-provider integration | Python |
| Window/input/UI composition, existing render adapters, reports, examples and community extensions | Python; move measured expensive computations below the interface when needed |
| Protocol authentication/connection orchestration and BOT policy | Python-facing; profile central dispatch, encoding and mass policy execution before assigning their hot paths |

A Python API must submit coarse commands/batches and consume owned results or
compact display deltas. It must not traverse every authoritative component, call
Rust once per Unit every tick, copy the full world per Agent, or require Python
callbacks inside native hot loops. User-authored policies/extensions interact
through explicit commands and validated configuration; they do not mutate a
second authoritative Python world. Future native accelerators remain accessible
through stable Python interfaces rather than requiring benchmark users to learn
Rust. Published wheels should keep compiler setup out of normal installation.

The architecture must accommodate expansion toward **5000 Agents**, independently
of Unit count. The existing first acceptance gate remains 5000 Units / 1000 Agents
at 30Hz with roughly 30-second Agent closed loops. A 5000-Agent capacity result
must state Units, observation/decision rates, payload sizes, hardware and queue
limits; it is not implied by a 5000-Unit result. Do not poll or run Python Agent
callbacks at world frequency merely because the simulation ticks at 30Hz.

Language-placement decisions follow profiling, iteration frequency, data volume
and cross-language transfer cost. Moving implementation below the Python API
must preserve game rules, observation content, permissions and action order;
record any Benchmark-relevant gap in the compatibility ledger. Community-facing
policy remains easy to change without rebuilding Rust; authoritative high-volume
execution has one owner in the kernel.

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
supports normal or fallback statistics and the legacy combat presentation lifecycles. Do not route Agents through
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
move, attack, rest, occupy, fortify, skill, `end_turn` and `get_faction_state`. Combat lifecycles work in none/dummy/window configurations.
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
The runtime now has API version11 and scene schema5 in addition to the rules marker.
The current Python adapter rejects extensions without the matching API marker;
scene schemas1/2/3/4 are rejected on import/reset. This prevents older R2 kernels from
silently ignoring newly introduced lifecycle, territory, observation-cache or combat-presentation metadata. Rebuild after source changes;
experimental historical traces must use their exact source and wheel.

Native Fog preserves line of sight, terrain bonuses, overlapping faction vision,
exploration and geometry-cache ordering. Death invalidation is consumed at the
next vision update, matching Python. Statistics retain ordinary periodic sampling
and the window's bounded multi-frame cycle, including reset partway through a
cycle. Their historical wall timestamps are injected metadata; resource cooldowns
still advance only from simulation time. The bootstrap codec also preserves
public runtime attributes attached to dataclasses. Registration metadata was
already declared in GameStats; the earlier codec did not drop those fields. Fog presentation now uses an accumulated changed-cell journal. Offline scene/window input integration is described below; network hosts remain pending.

Realtime/turn-mode world updates now apply the existing game-over policy: mutual
annihilation, one remaining faction, then timeout (in that precedence). Realtime
timeout uses simulation elapsed seconds. Derived living-faction counts are built on
import/reset and updated on death, so this check does not scan all Units each frame.
The window index's position requirement is retained. GameTimeSystem/AnimationSystem
and lifecycle enabled flags survive import. Agent `end_turn` rotates factions and resets AP/MP/status only on round rollover.
The trusted Framework method `finish_human_turn` preserves the human reset-before-
check path. Turn statistics, battle logs and TurnStartEvent keep their old order;
the GameTime round number synchronizes on the next tick. Cooldown/skill behavior
is not rebalanced. Offline settlement and window handoff are now connected; network orchestration remains pending. The small Player lookup table is derived on import/reset; future commands
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
BOT/network integration and parallel workers remain pending.


## Native display handoff (R3 intermediate)

`take_presentation_delta()` drains owned data for one display consumer. The first
call after create/reset contains all Unit rows, territory controls and Fog cells;
later calls contain changed Unit/territory rows and accumulated Fog changes.
GameTime/GameState/GameMode/TurnManager are small current snapshots. Multiple
writes/ticks before a drain retain final values and ordered events. Idle ticks do
not emit the complete Unit population. Returned objects never alias native data.

Unit rows include position, headcount, movement progress, AP/MP/SP/CP and status.
They drive the display cache and its spatial index; they are not Agent observations
and must not be exposed across the Protocol permission boundary. Terrain/sprites
and other static scene data are prepared once in Python. Map or scene replacement
requires a new prepared display World; an old epoch cannot update the new cache.

Rust now owns attack/effect/projectile/floating-text lifetimes and their external
entity IDs. This preserves the legacy ID stream when later captures allocate
entities. The update phase order and projectile creation tick are unchanged;
reset preserves in-flight progress and the projectile-created flag. This also
retains none/dummy/window differences rather than normalizing them implicitly.

`WorldPresentation` applies these deltas to an already prepared, independent
Python display World. It receives no native runtime handle. `VisualProjection`
uses existing Python easing/arc/rotation math and camera projection. Neither
consumer advances game timers or creates authoritative entities. Events are
returned to the application rather than published into the old gameplay event bus.

`attach_battlefield_renderers(presentation)` mounts only the existing map, unit,
effect and cached floating-text drawing systems. Its World must have no systems,
and the engine/fonts must already be initialized. Its AnimationSystem only updates
camera projection; it never runs the Python movement or combat lifecycle. Original
font, damage/CRIT text, coordinate, Fog and sprite caches remain in use. This is a
building block for the window handoff, not a replacement GameScene or a `--backend`
launch option yet. NativeSession below mounts local input and HUD; settlement and
VLM remain separate host integration work.

A single consumer must drain and apply in order. Recreate the prepared World and
`WorldPresentation` on scene reset. Epoch changes and older revisions are rejected
before display mutation. Resizing, panning and zooming belong to Python, including
reprojection of floating text while the simulation clock is paused. Display
mutations never write back into Rust; all gameplay input needs a runtime command.

### Trusted local controls (R3d1)

`RustRuntime.execute_control(kind, **parameters)` is a Framework input interface,
separate from authenticated Agent requests. Its commands are `move(unit_id,
position)`, `attack(unit_id, target_id)`, `wait(unit_id)`, `garrison(unit_id)`,
`fortify(unit_id, position)`, `set_fog(enabled)` and `toolbar_end_turn()`. Positions
are integer `(col, row)` pairs. Malformed command envelopes raise before execution;
unknown or unavailable commands fail explicitly. Commands use the existing native
movement/combat/resource state and never register a synthetic Agent.

Human attack returns the legacy hit boolean. Local wait/garrison only spend AP;
they do not apply the Agent `rest` status effects. Local fortification retains the
existing real-time resource exception. Keyboard `finish_human_turn()` and toolbar
`toolbar_end_turn()` remain distinct: the former resets actions and checks game
termination, while the latter rotates the explicit `TurnManager` list without
resource reset or turn events. These are compatibility behaviors, not new rules.

`LocalControls(runtime, presentation, initial_state, on_events=...)` connects these
commands to a `WorldPresentation`. Each command applies its display delta before
returning, so another click in the same frame sees the resulting state. The optional
callback receives ordered native presentation events; it must not invoke old Python
simulation handlers. Native simulation has already applied their gameplay effects.
The controller pins its native lifecycle epoch. Rust checks that epoch under the
same lock before command execution or delta extraction, so stale callbacks cannot
modify a reset world or drain the new display's initial baseline.

The classes in `rotk_env.runtime.native_input` retain existing picking, target
selection, keys, camera and panel interactions while redirecting gameplay writes.
Initialize the scene's UI once before importing it into Rust; mount these adapters
on the corresponding derived World after removing all old simulation/input systems
and their subscriptions. Adapter initialization preserves the prepared camera, UI
singletons and toolbar entities rather than allocating new external entity IDs.
Use `CoordinateInputHandlingSystem` for the legacy dummy path and
`InputHandlingSystem` for the window path. `UnitActionButtonSystem` and
`UIButtonSystem` reuse the existing panel rendering and text caches.

The offline GameScene/CLI host below assembles these building blocks. Transport/VLM, BOT and network post-game delivery remain pending; offline local play is not full R3 acceptance.

### Offline scene ownership and HUD (R3d2)

`NativeSession` owns one native world and its independent Python display World:

```python
from rotk_env.runtime.session import NativeSession

with NativeSession(display="none", mode="real_time", scenario="chibi-small",
                   seed=42, threads=1) as session:
    session.step(1 / 30)  # Simulation seconds; wall_time only supplies metadata.
    print(session.runtime.diagnostics())
```

For `dummy` or `window`, initialize GameEngine/SDL and fonts first. Call
`step(dt)` followed by `update_display(dt)` inside the existing owner-thread
frame loop; the host handles input dispatch, screen clearing and presentation.
The display World contains only native input adapters and presentation systems.
It does not execute Python movement, combat, resource, Fog, turn or statistics
updates. Preparing another scene creates another session; close the old one to
release its subscriptions and components. Initialization failure also cleans up
partially mounted input subscriptions. A native command or display failure retires
that native world immediately and raises at the next session boundary, including
when the legacy event bus catches and prints the original callback exception.

The API7 display delta adds `hud`: faction statistics and total simulation time,
plus one initial battle-log baseline followed by newly appended entries. It does
not copy battle/observation/LLM histories every frame. Scrolling and hiding the log
remain local UI operations; newly appended messages retain legacy auto-scrolling.
The display GameStats is a **partial presentation copy**, not a source for final
reports. Full settlement data must come from an explicit authoritative export.

The session itself rejects Hub/BOT startup. GameScene attaches the offline post-game host below. The ordinary Python launch remains the default; R3 and capacity acceptance are still incomplete.


### Experimental offline GameScene and settlement (R3d2b)

After installing the matching API14 release wheel, run from a complete checkout
(including the existing font/assets):

```sh
.venv/bin/python -m rotk_env.main --backend rust --no-hub --skip-start --mode real_time --scenario chibi-small --seed 42
# Add --headless for dummy SDL; use --mode turn_based for turn play.
# To use the normal menu, omit --skip-start; select the offline controller.
```

`--backend python` remains the default. `--native-threads 1|2|4` selects a native
configuration, currently still serial. App-level backend selection survives the
menu/game-over/menu cycle. Selecting Rust never falls back: missing/mismatched
extensions fail before window startup; Hub, rule BOT and the old scale-harness
host are rejected until their native adapters are connected. Rust scene faults
close authority and make the CLI exit nonzero. Quitting closes scene subscriptions.

Input panels poll before native simulation; pure rendering runs after its fresh
display delta. Offline post-game handling follows the simulation step. The host
calls `prepare_game_end(connected_agents, expected_epoch=...)` to update native
collection counters and obtain ordered notification targets/payload; delivery and
once-only notification state belong to the host. Offline has no recipients. It
retains the Python policy of waiting 60 wall seconds even when statistics are ready.
At the deadline it exports one complete authoritative snapshot, builds an independent
report World with no systems, and reuses the existing report schema/persistence.
It never fills a report from partial HUD statistics or mounts Python gameplay.
A report formatting failure retains the existing scene timeout/exit behavior.

Three system actions now execute in Rust: `strategy_ping`, `report_llm_stats` and
`retrieve_game_status`. Identity/faction checks, counters, errors and request order
follow the normalized Python baseline. Strategy throttle uses supplied wall time,
not simulation CD time. Same-faction reports accumulate (including legacy duplicate
reports); completion still counts factions, not individual Agents. Integer counters
retain arbitrary precision; percentage rounding follows integer division before
rounding to two decimals. This does not change scoring or report-completion rules.

`ActionRequest.connected_agents` (or `execute_action(..., connected_agents=N)`) is
trusted ingress metadata from the transport snapshot. The status handler never
reads an Agent-supplied count or guesses connections from registration. Historical
traces omit it and default to zero. Full state export accepts an optional epoch
check so an old report host cannot export a reset world's report.


### Player membership presentation (R3d3a)

API9 adds a complete initial Player baseline and compact subsequent unit-removal
patches. A death updates the same first matching faction Player as Python; the
derived membership set no longer retains dead unit IDs. No full faction member
list is copied across the interface on each death. This fixes a presentation gap,
not a change to combat or authoritative observation rules. Reset requires a new
presentation consumer and baseline. Other dynamic cold-component coverage still
needs audit; see G004 and R002 in the GAP ledger.

### R3d3b: ordered JSON inputs (API10)

JSON-shaped input objects retain insertion order through native parsing, storage,
export and reset. This matters when legacy handlers convert accepted objects into
strategy evidence or accumulated provider/model labels. First reports still store
raw labels; no input is pre-stringified by the Python adapter. Recursive mapping
order is preserved; gameplay entity/event order remains explicitly defined by the
normalized oracle. API10 rejects an older wheel even though scene schema5 and the
rule marker are unchanged. Historical artifacts must use their original wheels.

This is not a promise that every permissive Python string/number conversion is
equivalent. See the [Benchmark GAP ledger](native-benchmark-gaps.md).

API10 also preserves CPython 3.13 / Unicode 15.1 non-printable character escaping
in nested object/list representations. Top-level strings stay raw, as in Python.
The generated table has 713 ranges and is versioned with the oracle; the Lab
generator can verify it using `--check`. Updating Python/Unicode requires an
explicit compatibility audit. No Python callbacks are used inside native text
conversion. This boundary accepts Unicode scalar strings; arbitrary Python objects
and lone-surrogate transport compatibility are not established.

### R3d3c: VLM display attachment (API11)

`RustRuntime.execute_action("get_faction_state_vlm", ..., agent_id=...)` and
ordered request batches support the same explicitly enabled verb as Python.
Skirmish defaults remain move/attack/get_faction_state (plus end_turn in turn mode);
VLM is not silently added to `MatchRules.game_actions`. Native registration,
faction checks, trusted identity, unit selection and structured observation run
before any display read. Failed/unsupported queries do not capture a frame.

The Rust kernel returns the authorized structured projection. The public Python
adapter then copies the existing `RenderEngine.screen` and attaches the legacy
`frame_base64`, `frame_format`, and optional `frame_error`. A capture failure keeps
the successful structured query and its normal counters. The low-level
`star_native.NativeRuntime` JSON methods are the kernel boundary and do not attach
Python-rendered media; applications use `rotk_env.runtime.native.RustRuntime`.

A batch is fully decoded and detached before execution. It splits at each VLM
request so capture completes before later commands; adjacent ordinary faction
queries still share their native read context. A per-runtime admission lock spans
the native query and Python capture, serializing step/reset/close/local controls
through this public adapter. Native computation still releases the GIL. Rendering
and real framebuffer queries belong on the application/display owner thread;
this lock does not synchronize unrelated windows or other runtime instances.

**Inherited visual contract:** this is the current global framebuffer, including
its current camera, UI perspective and Fog. It may precede the latest action;
no redraw or per-Agent faction view is imposed by querying. A Wei request can
therefore receive the current Shu/spectator view, just as in Python. Structured
JSON still obeys the requesting faction and control permissions. Do not describe
this API as an isolated, current-tick, per-Agent visual observation.

The legacy `pygame.image.save(surface, BytesIO())` encoder produces TGA on the
locked pygame 2.6.1 stack, while the response says `frame_format="png"`. API11
preserves that existing wire behavior; it does not relabel or re-encode historical
Benchmark inputs. Correcting the encoding or perspective policy requires a
separate versioned contract change. Missing displays return the same errors; a
headless 1x1 surface stays 1x1. Linux/3.14 and real multimodal model delivery remain
unverified. See [G007 and preserved visual semantics](native-benchmark-gaps.md).

The inherited alpha path is also not a lossless raw-RGB screenshot contract:
on the pinned stack `(200,80,30,128)` decodes as `(100,40,15,128)` after capture;
the TGA packet contains the transformed RGB bytes. Old Python and API11 match
byte-for-byte. The Lab archive preserves the initially failing raw-pixel guard,
the independent codec control, and the corrected comparison against Python's
encoded bytes. This is an existing codec behavior, not a Rust rendering change.

### R3d4a: compact native host authority (API12)

Python continues to own connections, authenticated sender extraction, owner-thread
admission, ACK/retry timers, notification delivery and report formatting. The
following **trusted host APIs are not Agent actions**:

| API | Responsibility |
| --- | --- |
| `host_status(expected_epoch=...)` | Read four authoritative fields: `game_over`, `current_player`, `turn_number`, `winner`; constant-size output without Units or history. |
| `record_message(agent_id, expected_epoch=...)` | Count one inbound message in Rust's GameStats, separately from action counts. |
| `turn_start_context(wall_time=..., expected_epoch=...)` | After successful Agent `end_turn`, read the current faction/turn and registry-then-stats notification candidates. |

The offline settlement host now reads `host_status` rather than the mutable
Python display cache. Report creation still exports one complete state at the
existing 60-second wall-clock deadline. Simulation CD continues to use `step(dt)`.

These APIs release the GIL, use the same native lock and Python admission lock,
and reject stale epochs/closed runtimes. Results own their data. A network owner
must call `turn_start_context` immediately after the successful action, before
admitting another write; separate calls do not create an atomic transaction.
There is no new per-tick Agent scan: status reads a singleton, message recording
updates counters, and turn candidates scan registry/mapping only on handoff.
The candidate path remains O(registered Agents), not a claim of O(active) routing.

Compatibility details matter: single-action messages are counted **after** their
action; batches are counted **before** their actions. An unregistered nonempty
sender increments its personal counter and then raises, preserving Python's
partial write. Counters support integers beyond u64. Turn candidates retain
duplicates and the original registry-then-stats insertion order. The Python host
must add them individually to a set and then filter by connected IDs, retaining
the legacy delivery order. Re-registering to another faction leaves the old
registry row; this migration does not silently change notification eligibility.

API12 is a host contract checkpoint. Hub-enabled GameScene, actual turn ACK/retry
and delivery remain unavailable pending G009 integration; these methods alone do
not establish network support, true parallelism, or 5000-Agent capacity. The
Python backend remains default. Rebuild/install the matching wheel when updating.

### R3k1: exact native attack candidates (API13)

The Rust faction-observation kernel now carries over the original Python
spatial-index optimization for `attackable`. It uses committed occupancy to
collect nearby candidates, intersects them with the faction's visible enemies,
and applies the existing combat predicate. IDs are returned in ascending order.
The same read-batch cache, Fog rules, permission assembly and write boundaries
remain in place. No new Python gameplay work or network integration is added.

For range R and V visible enemies, the kernel chooses between visiting the
`1 + 3R(R+1)` cells of the exact hex disc and scanning V enemy positions. The
latter prevents enormous custom ranges from enumerating an enormous empty disc.
Ineligible attackers exit before searching. The local route costs O(R² + nearby
occupants), plus visibility-set lookups and result sorting; crowded cells and
large output remain real costs. Range filtering is necessary, not a replacement
for the original combat predicate. There is no cross-tick target cache to refresh.

Diagnostic observation metrics now include `attack_cell_lookups`,
`attack_distance_checks` and `attack_rule_checks`. They count work, not accepted
attacks. They do not appear in Agent faction-state responses. API13 requires the
matching wheel; scene schema5 and the Python oracle version are unchanged.

A local single-query probe with 5000 Units, 100 selected friendly Units and
2500 visible enemies measured median 468.45→42.50ms at range1 and
465.20→44.01ms at range3 (five samples after one warmup). Native query plus JSON
encoding was timed; Python decoding, simulation ticks, rendering, network and
Agent scheduling were excluded. These are kernel diagnostics, not the 30Hz
capacity gate. At range80 the same probe measured 143.43→144.66ms; broad visibility
and result assembly cannot be removed by a local candidate index. Exact inputs,
responses, negative controls and source identities are archived in STAR Lab.

The active migration priority is authoritative world execution and observation
cost. Python transport/ACK, BOT policy, UI and reports remain Python work. Their
unfinished integration is tracked separately from Rust kernel implementation;
it does not justify translating those layers into Rust.

### R3k2: native unit membership and terrain projection (API14)

Faction census and enemy projection now visit a stable external-ID Unit index
rather than all ECS entities. The index is derived during scene import/reset,
contains only entity handles (not a second component copy), and is updated at
ECS destruction for combat and expiring visuals. The current kernel imports
Units at scene creation; future dynamic Unit creation/removal must maintain this
membership through the native lifecycle too. Dead-but-retained and incomplete
Units are still counted/filtered using the original component predicates.

With active Fog, terrain projection visits the smaller of the faction's visible
cells and map cells, retaining their exact intersection and coordinate ordering.
Empty/missing visibility visits no terrain; disabled Fog still returns the full
map. Missing Terrain and historical tile ID zero behavior are unchanged. Unit
census is O(Units), not O(all world entities); terrain scanning is bounded by the
smaller set, plus membership lookups and output construction. This is not an
O(active) claim for all observations.

API14 adds diagnostic counters `census_entities_visited`,
`enemy_entities_visited` and `terrain_cells_visited`; Agent response fields,
scene schema5 and rules version remain unchanged. No response persists across
world writes. Python keeps configuration, interfaces, policy, transport and UI.
