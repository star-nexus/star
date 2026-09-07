# STAR 10K Online Development Roadmap

> **Temporary branch-only development document.**
>
> This file exists only on `perf/10k-online` to keep the active 10K release plan visible during development. **Delete this file before merging the final 10K work to `main`.** Durable experiment evidence and decisions belong in `star-nexus/star-lab`, not in this temporary roadmap.

## 1. Final release objective

Release a STARBench configuration that can sustain **10,000 online Agents** while preserving authoritative realtime world progress and reproducible benchmark semantics.

The release target is intentionally end-to-end:

```text
10K resident world
  -> 10K-scale dynamic state transitions
  -> 10K Agent sessions / protocol connections
  -> observation + action throughput
  -> long-duration stability
  -> reproducible release validation
```

Important distinction:

```text
10K Units != 10K online Agents
```

World capacity and Agent data-plane capacity must be validated separately before full-chain validation.

## 2. Runtime timing model

Canonical architecture separates:

```text
Simulation Tick Rate
  -> authoritative world-state transitions
  -> Movement / Combat / AP-MP / Vision / Fog / Agent action application

Render Frame Rate
  -> samples current world state for presentation
  -> Map / unit visuals / UI / MiniMap / window presentation
```

Planned operating semantics:

- **30 Hz canonical realtime benchmark/runtime target** — competition / benchmark operation.
- **60 Hz engineering stress profile** — measures runtime headroom with `controlled_work_frame_ms.p99 <= 16.67 ms`.
- **Full Interactive profile** — human-facing presentation; auxiliary UI such as MiniMap is configurable and must not define authoritative ENV capacity.

Do not open a separate 30-vs-60 semantic audit unless measured drift demonstrates a real problem.

## 3. Current validated baseline

### Phase 3 — Measurement & Regression Infrastructure — CLOSED

Reusable production measurement plane:

- ~5 s wall-clock rolling window;
- 4096-frame hard sample capacity;
- controlled-work accounting;
- platform input / present / wait separation;
- section inclusive/self timing;
- frame metrics and tail statistics;
- deterministic performance contracts.

All later scale work must reuse this infrastructure rather than create a second profiler.

### Phase 4 — 5K System-scale Frontier / MiniMap tail — CLOSED

Current 5K Core 60Hz results on Mac mini M4, 91x91 map, Fog ON, staggered movement, `realtime_defer`, MiniMap dynamic unit layer OFF:

| Resident | Moving | Density | Controlled P99 | Disposition |
|---:|---:|---:|---:|---|
| 5000 | 1250 | 25% | ~13.666 ms | CLEAR PASS |
| 5000 | 2500 | 50% | 16.68202856 ms median of 3 runs | BORDERLINE ACCEPT |

The literal 50% strict threshold result remains a boundary fail (`16.682 > 16.67`), but the engineering disposition is `BORDERLINE ACCEPT`; the threshold was not moved and no 37.5% binary search is required.

Closed MiniMap case:

```text
15 Hz MiniMap unit refresh
  -> incremental invalidation but O(Nresident) redraw
  -> ~4 ms periodic main-thread pulse at 5000 units
  -> contaminated 60 Hz tail
```

Core stress profile disables only dynamic MiniMap unit dots. Normal interactive default remains unchanged.

## 4. Priority order

| Priority | Phase | Main question | Release relevance |
|---|---|---|---|
| P0 | Phase 5 — 10K Core Runtime | Can the authoritative 10K world progress in realtime? | Required |
| P1 | Phase 6 — 10K Agent Data Plane | Can 10K Agent sessions connect and exchange observations/actions without blocking ENV? | Required |
| P2 | Phase 7 — ECS Parallel Runtime | Does 10K require multi-core scheduling? | Evidence-triggered |
| P3 | Phase 8 — Memory / GC / Long Soak | Does 10K remain stable over long runs? | Required |
| P4 | Phase 9 — 10K End-to-End Synthetic Agents | Can the complete 10K online loop run together? | Required |
| P5 | Phase 10 — Release Hardening | Are regression, deployment, docs and reproducibility release-ready? | Required |

Primary release chain:

```text
Phase 5 Core ENV
  -> Phase 6 Agent Data Plane
  -> Phase 8 Long Soak
  -> Phase 9 Full-chain 10K
  -> Phase 10 Release
```

Phase 7 parallelism is inserted only when measurement proves it is needed.

---

# Phase 5 — 10K Core Runtime Validation

## Goal

Determine current production STAR capacity at **10,000 resident units without redesign first**.

Question:

> Can the authoritative world sustain 10K resident entities and large dynamic workloads under the planned 30 Hz canonical runtime target, and how much 60 Hz engineering headroom remains?

## First experiment set

Use a 10K-scale scenario and the existing scale harness.

Initial density points:

```text
10,000 resident
0% moving      = 0
50% moving     = 5,000
100% moving    = 10,000
```

Do not run a fine-grained density curve unless one of these points reveals a meaningful boundary that matters to the next decision.

## Formal conditions

Keep comparable conditions fixed:

```text
Fog                    ON
motion phase           staggered
seed                    fixed / recorded
route preparation       outside measured window
execution pathfinding   OFF
production animation    ON
production commits      ON
GC                      realtime_defer
render                  uncapped during profiling
MiniMap dynamic units   OFF for Core profile
gameplay input          blocked
Phase-3 profiler        reused
```

## Gates

### Canonical release-oriented gate

```text
controlled_work_frame_ms.p99 <= 33.33 ms
```

This represents the planned 30 Hz realtime runtime budget.

### Engineering stress signal

```text
controlled_work_frame_ms.p99 <= 16.67 ms
```

This is a 60 Hz headroom target, not a release requirement for 10K.

## Required guards / evidence

At minimum preserve:

```text
resident units
configured / active moving units
actual density
Fog state
GC policy and in-window GC state
production animation path
position commits
Vision dirty work
no execution pathfinding
input policy
rolling-window completeness
MiniMap unit-layer state
controlled-work statistics
per-system timing
position commits per second
```

## Decision tree

```text
10K / 100% moving / 30Hz gate PASS
  -> current single-thread Core ENV is sufficient for canonical target
  -> do NOT start ECS parallelism merely because cores are idle
  -> proceed toward Agent Data Plane

10K / relevant workload / 30Hz gate FAIL
  -> profile system composition
  -> check closed-case signatures first
  -> identify actual hot boundary
  -> only then decide whether Phase 7 ECS parallelism is required
```

## Phase 5 completion criteria

- 10K scenario reproducible;
- formal 0/50/100% core runs completed as needed;
- 30 Hz canonical capacity classification recorded;
- 60 Hz engineering headroom reported separately;
- no known measurement contamination;
- important causal case(s) archived in STAR Lab;
- next-phase decision documented.

---

# Phase 6 — 10K Agent Data Plane

## Goal

Validate 10K concurrent Agent sessions independently from LLM inference providers.

Build a synthetic Agent scale driver capable of approximately:

```text
100 -> 1K -> 5K -> 10K clients
```

Each client should exercise the real protocol:

```text
connect
register
receive observation
wait deterministic synthetic latency
send valid action or noop
heartbeat
disconnect / reconnect when explicitly tested
```

Do not use 10K real LLM calls for capacity proof; provider latency/rate limits would confound STAR capacity.

Primary metrics:

```text
connected sessions
register throughput
observations/s
actions/s
observation-build latency
serialization latency
queue latency
action-apply latency
socket backlog / backpressure
dropped messages
reconnect rate
world-tick deadline misses
```

Critical invariant:

> A slow Agent may miss world evolution, but must never stall the authoritative ENV clock.

---

# Phase 7 — ECS Parallel Runtime — Evidence-triggered

Do not start by default.

Trigger only when Phase 5/6 proves a Core critical-path limit that cannot meet the 10K canonical target economically.

Preferred architecture:

```text
System/component read-write declarations
  -> dependency DAG / task graph
  -> parallel compute for independent work
  -> barrier
  -> deterministic authoritative commit
```

Preserve RAW / WAR / WAW dependencies and reproducibility.

For CPython, choose process/native/GIL-releasing work only after profiling establishes a stable hot boundary.

Principle:

> Profile first. Native second.

---

# Phase 8 — Memory / GC / Long Soak

Validate that 10K capacity is durable, not merely a five-second profiler success.

Representative release-oriented soak:

```text
10K resident
10K synthetic sessions when Phase 6 is ready
meaningful sustained dynamic density
Fog ON
30 Hz canonical runtime
30-60 min minimum; extend if trends require
```

Observe:

```text
RSS / live memory
session objects
socket buffers
message queues
Vision/cache state
event/history retention
GC safe-point behavior
world progress / deadline misses
crashes / stalls
```

No unbounded growth or accumulating backlog is acceptable.

---

# Phase 9 — 10K End-to-End Synthetic Agents

Full loop:

```text
10K Synthetic Agents
       <->
Hub / Protocol
       <->
Observation / Action
       <->
10K Authoritative ENV
```

This is the first experiment that can substantiate the phrase **"10,000 Agents online"** end-to-end.

Validate both world timing and data-plane health simultaneously.

---

# Phase 10 — Release Hardening

Add the minimum durable regression structure needed to protect the 10K release:

```text
CI:
  deterministic structural / small timing contracts

Nightly:
  selected 5K / 10K scale smoke
  Agent data-plane smoke

Release validation:
  formal 10K Core
  formal 10K data plane
  long soak
  full-chain 10K
```

Archive durable experiments and causal decisions in STAR Lab according to `PROTOCOL.md`.

Release documentation must clearly distinguish:

```text
canonical 30 Hz benchmark/runtime semantics
60 Hz engineering stress profile
Full Interactive presentation profile
```

---

## 5. Working principles

1. **Keep the main objective visible:** 10K online release.
2. **Do not reopen CLOSED cases without a matching signature.**
3. **Reuse Phase-3 measurement infrastructure.**
4. **Measure before redesign.**
5. **Do not optimize auxiliary UI into the authoritative capacity definition.**
6. **Do not start ECS multi-core work until 10K evidence requires it.**
7. **Separate world capacity from Agent connection/protocol capacity.**
8. **Use synthetic Agents before real LLM-scale testing.**
9. **Archive every major new bottleneck / negative result / frontier movement in STAR Lab.**
10. **Use STAR Lab two-tier artifacts for context-heavy formal runs: Compact Evidence Package + Raw Forensic Package.**
11. **Delete this temporary roadmap before the final merge to `main`.**

## 6. Branch lifecycle

```text
previous active branch:
  perf/system-scale-frontier
  -> Phase 4 CLOSED

current active branch:
  perf/10k-online
  -> starts from c5dd895e242b46f193050d8212fcc45b625ad885

before final merge to main:
  - ensure all durable evidence is in STAR Lab
  - remove docs/dev/10k-online-roadmap.md
  - run regression / release validation
  - merge validated production delta
  - delete perf/10k-online after merge
```

## 7. Phase 5 active investigation ledger — 2026-09-07

### Retained production baseline

The current production-retained Phase-5 runtime remains:

```text
17ced8d2ba1725b4d0c1a5458e6c61c06c1e206a
```

It contains the validated KEEP chain:

```text
A   Animation MovementSystem lookup elimination
B   position-specialized spatial-index movement update
C1  Vision geometry-cache ordering / terrain bypass
C2a explored-history 0->1 incremental update
D1  indexed periodic Vision full-audit elimination
```

No UnitRender investigation after D1 has yet added another production KEEP.

### UnitRender causal chain — E through E5 CLOSED

The moving-dependent UnitRender investigation has narrowed as follows:

```text
moving-dependent UnitRender growth
  -> not exact raster duplicate draw
  -> classification + Cull
  -> classification candidate does not solve 100% moving frontier
  -> Cull candidate volume / Fog branch mix / dict-set replay rejected
  -> spatial first-touch confirmed
  -> MapRender locality-gap hypothesis rejected
  -> record fields dominate spatial first-touch
  -> slots recover only a small fraction; DO_NOT_KEEP
  -> stable UnitSpatialRecord identity is NOT MATERIAL
  -> E5-3 field decomposition
  -> WORLD_COORD_PAYLOAD_FIRST_TOUCH_DOMINANT
```

E5-3 formal result on the slotted attribution base:

```text
100% moving:
  full record-field effect = 0.476 ms
  world_x/world_y          = 0.375 ms (~78.8%)
  faction                  = -0.011 ms
  col/row                  = 0.111 ms

50% moving:
  world_x/world_y share    = ~79.4%
```

E5 is therefore CLOSED as **Spatial Structure Decomposition**. Do not continue the stage as E5-4.

### E6 — Derived World-Geometry Reuse — ATTRIBUTION VALIDATED

Formal experiment branch:

```text
experiment/phase5-unitrender-e6-derived-world-geometry-reuse
```

Formal measurement tooling SHA:

```text
ac68b4e5c50837feb8f978ffe2c2a9dc2caca1df
```

Runtime control/treatment base:

```text
17ced8d2ba1725b4d0c1a5458e6c61c06c1e206a
```

E6 asked only:

> Can Cull materially recover the isolated movement-dependent first-touch cost if pure per-hex derived geometry `(world_x, world_y, bucket)` is long-lived and reused?

Isolation boundary:

```text
KEEP fresh UnitSpatialRecord identity
KEEP ordinary production record layout
KEEP exact Cull implementation
KEEP spatial bucket/cell/entity containers
KEEP authoritative HexPosition semantics
CHANGE only derived geometry payload reuse
```

Formal run:

```text
run_id: 20260907-203733
order: A50 -> B50 -> B100 -> A100
contract: 2 passed
control targeted regressions: 25 passed
treatment targeted regressions: 25 passed
all workload/source guards: PASS
```

Formal result:

```text
50% moving
  controlled avg: 25.412 -> 25.267 ms (-0.57%)
  Cull avg:       2.076 -> 1.875 ms  saving 0.201 ms
  UnitRender avg: 9.268 -> 9.134 ms  saving 0.134 ms
  position rate:  +0.733%
  Vision rate:    +0.447%
  Fog delta:      +0.693%
  decision checks: PASS

100% moving
  controlled avg: 32.880 -> 32.386 ms (-1.50%)
  Cull avg:       2.404 -> 1.971 ms  saving 0.433 ms
  UnitRender avg: 10.242 -> 10.026 ms saving 0.217 ms
  position rate:  -0.109%
  Vision rate:    -0.054%
  Fog delta:      +0.319%
  decision checks: PASS
```

Preregistered decision:

```text
DERIVED_WORLD_GEOMETRY_REUSE_CANDIDATE_JUSTIFIED
```

This is a strong causal continuation of E5-3: at 50% moving, the E6 Cull recovery (`0.201 ms`) exactly matches the E5-3 `world_x/world_y` attribution (`0.201 ms`). Do not over-interpret the 100% recovery (`0.433 ms`) versus E5-3 `0.375 ms`; the treatment also reuses `bucket` and the excess is small enough to be normal run-level variation.

**E6 has still added zero production KEEP.** Production remains `17ced8d2...`.

### E6 next step — bounded production geometry ownership

The next engineering question is no longer whether geometry reuse is material. That is validated.

Now determine the narrowest production representation that preserves the reuse benefit while proving bounded lifetime/ownership:

```text
authoritative map / board geometry lifetime
        -> bounded per-hex derived world geometry
        -> records reference long-lived geometry
        -> exact production-derived controlled A/B
```

Do not retain the attribution-only unbounded visited-coordinate cache.

Do not reopen:

```text
record identity
slots
by_entity lookup
candidate volume
branch mix
MapRender scheduling
duplicate raster draw
```

without a new matching signature.

Required production-candidate validation:

```text
semantic / regression contract
bounded ownership proof
controlled A/B vs production 17ced8d2...
Cull + UnitRender local metrics
workload-equivalence guards
10K canonical 30 Hz revalidation before any frontier update
```

### Two-tier evidence packaging — adopted

STAR Lab `PROTOCOL.md` v1.2 now defines:

```text
Compact Evidence Package = default normal review / Agent / LLM artifact
Raw Forensic Package      = authoritative low-level audit substrate
```

The canonical E6 rerun entrypoint is:

```bash
bash tools/run_phase5_unitrender_e6.sh
```

It emits:

```text
<run-id>-compact.zip
<run-id>-raw.zip
```

with both SHA256 values. Packaging occurs after measurement/analyzer execution and cannot change the preregistered gates.

Formal E6 raw package checksum:

```text
d4f7bab293ced78ab11231fe0e370fe51a257e1cb95b12666340a7a628819bc4
```

STAR Lab case:

```text
experiments/2026-09-10k-unitrender-e6-derived-world-geometry-reuse/
```

Its scientific attribution is validated. Full case CLOSED status waits only for a stable canonical mirror/storage locator for the raw forensic ZIP.

`records/performance-frontier.md` remains unchanged until a validated production state actually moves or formally confirms the 10K capacity frontier.
