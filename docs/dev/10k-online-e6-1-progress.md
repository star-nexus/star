# Phase 5 Live Progress — E6-1 Bounded Geometry Ownership

> Temporary active-work supplement to `docs/dev/10k-online-roadmap.md`.
> Durable evidence and final decisions belong in STAR Lab. This file is the
> current authoritative live note for E6-1 until the branch result is folded
> into the main roadmap ledger.

**Date:** 2026-09-07  
**Status:** VALIDATED / KEEP — canonical 30 Hz @100% still FAIL

## Upstream closed evidence

E5-3 established:

```text
WORLD_COORD_PAYLOAD_FIRST_TOUCH_DOMINANT
```

E6 formal attribution established:

```text
DERIVED_WORLD_GEOMETRY_REUSE_CANDIDATE_JUSTIFIED
```

Formal E6 recovery:

```text
50% moving:  Cull saving 0.201 ms
100% moving: Cull saving 0.433 ms
```

E6 attribution did not create a production KEEP because its visited-coordinate cache was intentionally unbounded.

## E6-1 production result

Formal run:

```text
run_id: 20260907-213322
order: A50 -> B50 -> B100 -> A100
```

Control:

```text
17ced8d2ba1725b4d0c1a5458e6c61c06c1e206a
```

Validated candidate / new retained production state:

```text
e7ba18b31870577110b591104ef8fa7b4713e43c
```

Active branch:

```text
experiment/phase5-unitrender-e6-bounded-geometry-ownership
```

Formal runner branch HEAD at run:

```text
8cd4215e1d11d0778ee9db737cc757213f13630d
```

Non-test `rotk_env` runtime diff:

```text
rotk_env/utils/unit_spatial_index.py
```

## Candidate representation

```text
MapData board snapshot
        ↓
UnitSpatialIndex-owned lazy geometry cache
        ↓
cache only board-member (col,row)
        ↓
canonical (world_x, world_y, bucket)
        ↓
fresh UnitSpatialRecord on every refresh
```

Boundedness contract:

```text
max retained geometry entries <= board hex count captured at rebuild
world without MapData -> cache disabled
board-external coordinate -> compute but do not retain
rebuild -> clear geometry cache + rebind board snapshot
```

No change to:

```text
HexPosition authority
UnitSpatialRecord frozen layout
fresh record identity
Cull algorithm
by_entity/by_bucket/by_cell containers
movement legality
Vision/Fog semantics
```

## Premeasurement validation

All required validation completed before performance points:

```text
bounded geometry contract:       5 passed
control targeted regressions:   25 passed
treatment targeted regressions: 30 passed
source diff guard:              PASS
scenario/workload guards:       PASS
```

## Formal A/B result

### 50% moving

```text
controlled avg: 25.633 -> 25.417 ms (-0.84%)
controlled p99: 26.767 -> 26.564 ms
Cull avg:       2.140 -> 1.909 ms  saving 0.231 ms
UnitRender avg: 9.394 -> 9.224 ms  saving 0.170 ms
Animation avg:  3.474 -> 3.513 ms  +1.12%
position rate:  +0.013%
Vision rate:    +0.021%
Fog delta:      +0.121%
checks:         PASS
```

### 100% moving

```text
controlled avg: 32.567 -> 32.115 ms (-1.39%)
controlled p99: 37.262 -> 33.677 ms
Cull avg:       2.406 -> 1.983 ms  saving 0.423 ms
UnitRender avg: 10.277 -> 9.910 ms saving 0.367 ms
Animation avg:  7.217 -> 7.258 ms  +0.57%
position rate:  -0.015%
Vision rate:    -0.008%
Fog delta:      -0.035%
checks:         PASS
```

Preregistered production decision:

```text
KEEP_BOUNDED_DERIVED_WORLD_GEOMETRY_REUSE
```

The small Animation-side regressions are visible rather than hidden, but remain below the frozen 2% rejection threshold. Cull, UnitRender, and controlled-work improve while workload rates remain effectively identical.

## New retained production state

The Phase-5 retained chain is now:

```text
A + B + C1 + C2a + D1 + E6-1
```

with source state:

```text
e7ba18b31870577110b591104ef8fa7b4713e43c
```

Do not continue future causal profiling from `17ced8d2...`; that SHA remains the E6-1 control/history baseline.

## Canonical 30 Hz result remains strict FAIL

At 10K / 100% moving:

```text
treatment controlled_work_frame_ms.p99 = 33.677126 ms
gate                                      = 33.33 ms
margin                                    = +0.347126 ms
```

Therefore:

```text
30Hz canonical @100% = FAIL
FRONTIER UPDATE CANDIDATE = false
```

Do not round this into a PASS and do not move the threshold.

The candidate did reduce paired-control p99 by ~3.584 ms, so the boundary is now very close. Continue attribution from the **new retained production state** rather than reopening CLOSED UnitRender hypotheses.

## Artifact policy / formal evidence

Compact Evidence Package:

```text
20260907-213322-compact.zip
size:   10616 bytes
SHA256: 0c9db01f29a04dcefc7ba896ab7ab533ec313c31a9e3d974d790b22893cb45a9
```

Raw Forensic Package:

```text
20260907-213322-raw.zip
size:   128760 bytes
SHA256: 4322905154b69ec25688fa0775b0efdd62a7a60bf1366aead9d5e8f73d661c07
```

Compact was independently inspected and is sufficient for normal decision-grade review: all package checksums verified, all four formal points and guards are present, and Raw/profile SHA256 provenance is retained.

Raw remains the authoritative forensic substrate. STAR Lab case is validated but not yet CLOSED because a stable canonical Raw mirror/storage locator is pending.

## Reporting formatter correction

The formal terminal line printed:

```text
FAIL (33.677 ms <= 33.33 ms)
```

because the human-readable formatter used `<=` unconditionally. The machine-readable summary correctly recorded `pass: false`; no measurement or decision was affected.

Formatter-only fix:

```text
2db4fa41753012df5c8f61f0184ef5c96e4f1546
```

Future output prints `>` on a FAIL.

## STAR Lab case

```text
experiments/2026-09-10k-unitrender-e6-1-bounded-geometry-ownership/
```

Current case state:

```text
VALIDATED / KEEP — raw forensic mirror pending
```

## Next Phase-5 question

The production candidate is no longer the question. E6-1 is retained.

The strict 30 Hz boundary remains short by only `0.347 ms` at 100% moving. Next work must profile the **new retained state `e7ba18b3...`** and attribute the remaining tail. Do not start ECS parallelism or reopen rejected UnitRender branches without a matching causal signature.
