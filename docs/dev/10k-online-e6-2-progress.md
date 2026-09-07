# Phase 5 Live Progress — E6-2 Slotted Spatial Record Composition

> Temporary active-work supplement to `docs/dev/10k-online-roadmap.md`.
> Durable evidence and final decisions belong in STAR Lab.

**Date:** 2026-09-07  
**Status:** VALIDATED NEGATIVE / INVESTIGATION CLOSED — Raw mirror pending in STAR Lab

## Retained production

Production remains the E6-1 KEEP state:

```text
e7ba18b31870577110b591104ef8fa7b4713e43c
```

KEEP chain:

```text
A + B + C1 + C2a + D1 + E6-1
```

No `slots=True` production candidate is created.

## E6-2 question

E5-1 previously measured a small positive Cull signal from `UnitSpatialRecord slots=True`:

```text
~0.090 ms @50%
~0.113 ms @100%
```

E6-2 tested whether that representation signal remained independently useful after E6-1 removed the dominant world-coordinate payload first-touch mechanism.

This was a composition validation, not a reopening of E5 root-cause attribution.

## Formal run

```text
run_id: 20260907-231532
control/treatment runtime: e7ba18b31870577110b591104ef8fa7b4713e43c
order: A50 -> B50 -> B100 -> A100
contract: 4 passed
control targeted regressions: 30 passed
treatment targeted regressions: 30 passed
all workload guards: PASS
```

## Result

```text
50% moving
  controlled avg: 24.923 -> 25.245 ms (+1.29%)
  controlled p99: 30.921 -> 26.466 ms
  Cull avg:       1.848 -> 1.774 ms  saving=0.074
  UnitRender avg: 9.005 -> 9.000 ms (-0.05%)
  Animation avg:  3.397 -> 3.452 ms (+1.64%)
  FAIL: controlled avg exceeded preregistered +1% ceiling

100% moving
  controlled avg: 31.930 -> 32.199 ms (+0.84%)
  controlled p99: 33.506 -> 34.365 ms
  Cull avg:       1.942 -> 1.889 ms  saving=0.053
  UnitRender avg: 9.783 -> 9.714 ms (-0.70%)
  Animation avg:  7.211 -> 7.298 ms (+1.21%)
  FAIL: Cull saving below preregistered 0.07 ms floor
```

Decision:

```text
SLOTTED_RECORD_COMPOSITION_NOT_MATERIAL
```

## Interpretation

The old E5-1 signal was real but its engineering value is now partially subsumed by E6-1.

Approximate retained Cull signal:

```text
50%:  0.074 / 0.090 ~= 82%
100%: 0.053 / 0.113 ~= 47%
```

The relevant frontier workload is 100% moving, where the remaining signal is too small and P99 moved in the wrong direction.

The large 50% control->treatment P99 decrease is not considered causal: control p50/p95 were lower than treatment and only a few control tail frames raised p99. Local metrics and preregistered average gates take precedence.

## Canonical 30 Hz diagnostic

```text
100% treatment controlled p99 = 34.364929 ms
canonical gate                 = 33.33 ms
classification                 = FAIL
```

Performance Frontier remains unchanged.

## Production consequence

```text
retain e7ba18b31870577110b591104ef8fa7b4713e43c
do not add slots=True
do not bundle other rejected UnitSpatialRecord representation tweaks
```

The next Phase-5 step should start from retained E6-1 production and inspect the current 100%-moving system/tail composition rather than continue the slotted-record path.

## Artifacts

Compact:

```text
20260907-231532-compact.zip
SHA256 682a02741be2c4002fe815418254f5ac056c06c27e1e8f4dd10130aa40c74bbc
```

Raw:

```text
20260907-231532-raw.zip
SHA256 e6aeee218bd21332819b881f904524ca15c3b3942c5eb4dd0bf867b42023e2c4
```

STAR Lab case:

```text
experiments/2026-09-10k-unitrender-e6-2-slotted-record-composition/
```
