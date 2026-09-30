# Rust parallel phase P0: dependencies before scheduling

2026-09-30. Baseline annotated tag `rust-kernel-r4e-2026-09-29` resolves to
`7e145d169433695cd4957e186a6b2fda06813c26`; measured implementation
`5147e4d8e0c33c997bd86960d87fa4b5b3ca90c5`, API18/schema5,
oracle `python-r0c-3cc4ffe`. Target remains 5000 Units + 1000 Agents;
5000 Agents is paused. Rust owns world execution; Python owns SDK/policy/UI/transport.

Progress: `recovery █ | dependency audit █ | attribution █ | parallel implementation ░ | capacity ░`.
This describes stage coverage, not elapsed-work percentages.

## Current next task (E1 user steering)

2026-09-30: the next task explores **ECS between-System and within-System
parallelism**. [E1 design and mechanism evidence](native-ecs-parallel-design.md)
supersedes the P0 adjacent-query proposal as active priority; keep P0 results
and historical decision intact. Narrow Recovery/Lifecycle/Vision accesses are
semantic candidates, while current whole Runtime interfaces remain exclusive.
E2 selects Statistics current-batch compute/ordered commit for the first prototype.
No production parallel scheduling is enabled by this design.

## Three distinct mechanisms

| Mechanism | Current implementation | Requirement for extending it |
|---|---|---|
| Between Systems | `Runtime::step` is sequential, methods borrow the entire Runtime | Minimal component/resource access AND original business/event dependencies must permit overlap; no pair is approved by this audit |
| Inside a System | Observation panels already use a scoped fixed 2/4-worker pool; threads=1 creates none | Stable inputs, independent candidate outputs, bounded jobs, join and deterministic commit; shared occupancy/Fog/LRU/deadlines must not be written by completion order |
| Across requests | ObservationBatch already shares encoded facts/panels within adjacent read queries; Lab loop uses single calls | Measure already-admitted contiguous reads; never cross a write (even failed), tick, display read, reset, or wait for future requests |

An Arc represents immutable shared ownership, not a scheduler. GIL release does not
remove the native instance mutex. Display extraction drains queues and events;
it is a mutating boundary, not an unrestricted read.

## Runtime read/write dependency table

R/W includes typed ECS, cold InitialComponents, derived indexes, resources,
activity ledgers and display deltas. Disabled phases and none/dummy/window differ.
This is a scoped audit of the baseline ingress; new writers require a new audit.

| Phase / source | Reads | Writes / hidden resources | Order / internal parallel candidate | Cost at R4e |
|---|---|---|---|---|
| Clock + sync_turn_clock (`runtime.rs:341`, `lifecycle.rs:50`) | config, dt, GameState turn | SimClock, GameTime cold singleton, wall_time, revision | Before all other phases; dt is simulation time, diagnostic timers never drive it | Not separately measured |
| Statistics (`statistics.rs:399`, StatisticsSystem::update) | clock/wall_time, Position, UnitInfo, Headcount, Movement, Fog, prior visibility; sampled IDs/config | GameStats/GameModeStatistics, UnitObservation, VisibilityTracker/history, sampling cursor and accumulators | Before movement and current-tick Fog; moving after it changes recorded observations; independent candidate sampling may be separated only with original chunk/history order | Not separately measured; periodic/chunked work is not uniformly O(active) |
| Movement (`movement.rs:259`) | moving IDs in BTree order, Position, Movement/path, display/hex geometry | Position, Movement, spatial occupancy, moving removals, vision_dirty, presentation_dirty | Before Vision/Capture. Arithmetic candidates could be parallel, but old/new-cell writes and set updates must commit in original ID order | Not separately measured; O(active moving + advanced path segments) |
| Visuals (`presentation.rs:286`, Visuals::advance) | Position, dt, animation payloads/config | attack/projectile/effect/damage maps, entity allocation/removal, OrderedWorld/ID counter, dirty/removed queues | attack→projectile→effect→text; projectile spawned this tick receives full dt. Structural changes conflict with World borrowers and recovery's new-ID audit | Not separately measured; active visual maps |
| Recovery (`recovery.rs:238`, Recovery::update) | simulation elapsed, AP/MP/SP, world next ID, due/version/pending ledgers | AP/MP/SP/cooldowns, deadline/version maps, elapsed/last/known cursors, pending MP, presentation_dirty | Keep due/version cancellation and MP cadence; independent per-ID arithmetic is only a candidate, duplicate/stale tasks and commits need ordering | Not separately measured; due work + pending + new IDs, not full resident scan |
| Lifecycle (`lifecycle.rs:71`) | enabled mode, LivingFactions all/positioned, GameState turn, simulation time/limits | GameState winner/end_reason/game_over, ordered GameOverEvent | Annihilation before timeout; singletons/events conflict with ingress/turn. Indexed liveness maintained by death/import | Not separately measured; faction count / singleton work |
| Vision (`vision.rs:395`, VisionSystem::update) | post-movement Position, UnitInfo, Vision, terrain/rules, dirty IDs, audit mode | Vision, Fog visible/explored, per-faction cell refcounts, geometry cache/LRU clock, counters, unit visibility/faction, vision_dirty drain, presentation_fog | Movement→Vision. Geometry cache misses are possible pure candidates; cache hit/miss/LRU and refcount/delta commit remain in ID order. Bootstrap/optional audits scan resident entities | Not separately measured; dirty/recomputed geometry + optional audit |
| Capture (`territory.rs:310`) | capturing IDs, CaptureAction, post-movement Position, UnitInfo, clock, territory/map | CaptureAction, TerritoryControl/owner, tile flags/queues, capture cancel/removal, World entity removal, statistics/log side effects of owner change | After Movement and current tick's earlier phases; keep active-ID order, errors and partial writes. Shared target tiles prohibit naive entity parallelism | Not separately measured; O(active captures), possible shared tile |
| Ordered Agent combat (`combat.rs`, `actions.rs`) — NOT a step phase | attacker/target Position, occupancy, CombatStats, Headcount, status, AP, skills/rules, permissions, RNG | AP, Headcount/death, CombatRoll and RNG streams, cold Player/UnitStatistics, Unit membership/spatial/liveness/activity indexes, Fog dirty, stats/logs/events/visuals/team ownership | Accepted action order fixes RNG consumption and immediate death. Cannot defer all actions to frame end or parallelize attacks on shared targets | No standalone R4e cost; included in action service, not step |
| Turn/control/team (`turn.rs`, `controls.rs`, `team.rs`, `actions.rs`) — ingress | trusted identity, faction/mode, ownership, GameState/TurnManager, resources | clock/turn/current faction, AP/MP/SP/status, member/owner indexes, FIFO messages, stats/events/display changes | Keep human/Agent different reset timing and claim/release→query permissions; query counters commit at read-segment boundary | No standalone R4e cost |
| Observation public facts (`observation.rs`) | living Unit membership/typed and cold panels, terrain/occupancy/Fog, GameState/logs, request selection | Batch-local census/faction/encoded fact caches and counters; caller captures permissions, commits query stats | Stable immutable borrow; per-request permissions; write ends segment; response owns bytes beyond world lifetime | Entire long-run observation service mean 3.07–3.12ms includes client decode; NOT public-only cost |
| Observation panels (`observation.rs:412`, `read_pool.rs`) | stable world, selected IDs, visible enemies, reachable/attack rules | Worker-local output/counters; caller merges batch-local caches in chunk/input order | Existing System-internal read parallelism. No RNG or world mutation; join before returning; tiny selections can regress | R4a historical MP6/100-selected query median 25.0→20.9/21.3ms at 1/2/4; not current R4e panel-only cost |
| Presentation (`runtime.rs:463`) | ECS, cold/HUD/statistics and dirty projections | drains dirty/tile/Fog/player/visual/removed/log/event queues; full baseline flags | One-shot events and queue drains under exclusive lock. Owned output after serialization | R4e run1 extraction mean 0.709ms; Python application 2.768ms; display systems 8.679ms |
| Whole step | all advancing phases above | all above, revision finalization | Explicit sequential calls; Bevy multi_threaded feature does not schedule these methods | R4e run1 mean 0.295ms / P99 0.758ms, excludes Agent observations |

External IDs are stable and ordered by OrderedWorld/BTree structures, not Bevy
Entity allocation order. RNG is CPython-compatible per domain; workers may not
choose its consumption order. Reset reconstructs derived ledgers and reuses the
read pool only after validation; failed reset retains the old world.

## P0 measured cost (fixed-input diagnostic)

Measurement implementation `2ac2b29a7a3bf09d92370a0352dcf0fd47f741e5`.
All 40994 requests / 9880 ticks / 9880 complete display extractions match frozen
R4e at 1/2/4 threads. Candidate ordinary/profiled full decoded responses, deltas
and final states compare directly. Frozen cross-process full-output-stream and
final-state hashes also match. 2239 Python tests (22 new), 4 Rust tests, fmt,
Clippy and release build passed. Archived binary SHA is in the Lab manifest.

| System phase | P0 t1 mean ms | P0 t1 P99 ms |
|---|---:|---:|
| Clock / turn sync | 0.000906 | 0.001875 |
| Statistics | 0.167297 | 0.591833 |
| Movement | 0.027429 | 0.054417 |
| Visuals | 0.010109 | 0.033875 |
| Recovery | 0.003624 | 0.012750 |
| Lifecycle | 0.000429 | 0.001167 |
| Vision | 0.045143 | 0.127208 |
| Capture | 0.000072 | 0.000250 |

Native diagnostic total mean0.256917ms includes about0.001908ms not attributed to
phases (including timer/map/report work); this is NOT a measured profiler overhead
A/B. Samples include recorded warmup and paired headless execution. Do not compare
these times as language, thread or window-frame speedup; tiny phases are noisy.
The earlier dependency table's unmeasured cells refer specifically to R4e live
per-System attribution. P0 now fills them only for this scoped diagnostic.

11007 observations occupy6938 immutable read segments. Lengths1/2/3/4/5 occur
3910/2048/921/57/2 times.7097 queries(64.48%) are in multi-query segments; only1604
(14.57%) repeat their faction and no selected panel repeats. This is an upper
opportunity count, not predicted saved time or proof of scheduler feasibility.

Select P1 **ordered encoded read-batch integration for already-admitted adjacent
queries**, reusing existing public facts. Audit the admission queue/callbacks
before implementation; never reorder to create these segments. Keep cross-faction
Fog/permissions and per-request output/client decode. Movement/Vision worker
candidates are deferred at current cost; statistics needs an ordered sampling and
reduction audit. System-between scheduling remains unapproved.

## Evidence and first implementation

The R4e table does not identify the most expensive individual world phase.
It cannot support moving every advance_* into a pool, nor predict a frame speedup
by adding/subtracting P99 components. Existing R4a/R4b evidence also shows that
reducing repeated construction/allocation may beat increasing workers.

First implement **an opt-in advancing step profiler** and a Lab fixed-trace audit.
`NativeRuntime._step_profile_json(dt, wall_time)` executes ONE ordinary step and
returns owned timing JSON. It is a private Lab diagnostic, not an Agent verb or
new Python policy API. It uses the same monomorphized step_inner as normal step;
normal step has no Instant reads, no retained profile state or output allocation.
The opt-in report measures disjoint executed phase wall durations (nanoseconds),
including clock/validation/sync, plus native total and active counts at entry.
Absent movement/visual keys mean disabled/skipped phase, not a zero-time sample.
Phase times include each phase's commits; they are not worker CPU times. Total
also includes timer/map overhead; tiny phases are noisy. Errors keep original
partial writes and return the original error; no successful timing report is
returned for a failing step. Binding/lock wait and JSON encoding are outside
native total. API18/schema5/oracle stay compatible; this additive private
capability still requires a freshly built wheel identified by source/hash.

The Lab tool must measure exact R4e recorded inputs, compare complete decoded
responses and presentation deltas against ordinary step, compare final full state,
and compare the output stream against the frozen R4e binary. Also count genuine
contiguous read segments before choosing cross-request integration. This phase
validates attribution, not a performance fix or a new capacity frontier.

P1 selects adjacent-query sharing as above. If admission cannot preserve its
existing order, record the negative feasibility result. Preserve sequential
commits and reuse the existing pool,
measure 1/2/4 with unchanged input, and retain scheduling losses as negative
results. Then use original R4e commands/guards for the actual window gate. Keep
5000-Agent expansion paused, Python/default one thread, G008/G009/R001/R002 open.

## Recovery / validation

The active worktree is `/Users/liyang/.codex/worktrees/rust-ecs-parallel/star-main`,
branch `codex/rust-ecs-parallel`. Preserve the original 49 deletions in star-main
and both frozen Python/Rust measurement worktrees. Lab entry is
`records/rust-ecs-parallel.md`; experiment is `2026-09-rust-system-attribution`.
See `native-benchmark-gaps.md` and `native-state-boundaries.md` before new writers.
