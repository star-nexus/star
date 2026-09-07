# Phase 5 Live Progress — E6-1 Bounded Geometry Ownership

> Temporary active-work supplement to `docs/dev/10k-online-roadmap.md`.
> Durable evidence and final decisions belong in STAR Lab. Fold the closed result
> back into the main roadmap ledger when E6-1 formal A/B is complete.

**Date:** 2026-09-07  
**Status:** ACTIVE / PREREGISTERED — formal production A/B pending

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

## E6-1 question

> Can the validated per-hex geometry reuse mechanism be made production-safe with hard board-bounded ownership while retaining material Cull/UnitRender benefit and no compensating runtime regression?

## Frozen source states

Control / retained production:

```text
17ced8d2ba1725b4d0c1a5458e6c61c06c1e206a
```

Candidate:

```text
e7ba18b31870577110b591104ef8fa7b4713e43c
```

Active branch:

```text
experiment/phase5-unitrender-e6-bounded-geometry-ownership
```

E6-1 tooling commit:

```text
1855f34c14463a6c165d85b11403e4cc2e7938b4
```

Non-test `rotk_env` runtime diff between control and candidate:

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

## Formal A/B

Canonical command:

```bash
bash tools/run_phase5_unitrender_e6_1.sh
```

Order:

```text
A50 -> B50 -> B100 -> A100
```

The runner requires, before any density point:

```text
exact SHA/source-diff guard
scenario SHA256 guard
bounded geometry contract tests
control targeted regressions
treatment targeted regressions
```

## Preregistered KEEP gates

```text
position commits/s within ±2%
Vision changed/s within ±2%
Fog delta/s within ±2%
Cull saving >= 0.10 ms @50%
Cull saving >= 0.20 ms @100%
UnitRender avg improves at both densities
Animation avg regression <= 2%
controlled avg regression <= 2%
```

Possible decision:

```text
KEEP_BOUNDED_DERIVED_WORLD_GEOMETRY_REUSE
DO_NOT_KEEP_BOUNDED_DERIVED_WORLD_GEOMETRY_REUSE
```

## Canonical capacity gate remains unchanged

KEEP is separate from the Phase-5 release frontier.

At 10K / 100% moving:

```text
controlled_work_frame_ms.p99 <= 33.33 ms
```

remains the canonical 30 Hz gate.

Do not update `records/performance-frontier.md` until formal evidence satisfies ordinary STAR Lab frontier admission requirements.

## Artifact policy

The canonical runner emits both:

```text
<run-id>-compact.zip
<run-id>-raw.zip
```

Compact is the default review / Agent / LLM artifact. Raw remains the authoritative forensic substrate and is never replaced by Compact.

## STAR Lab case

```text
experiments/2026-09-10k-unitrender-e6-1-bounded-geometry-ownership/
```

Current case state:

```text
DRAFT / PREREGISTERED / measurement pending
```
