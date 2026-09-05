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
10. **Delete this temporary roadmap before the final merge to `main`.**

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
