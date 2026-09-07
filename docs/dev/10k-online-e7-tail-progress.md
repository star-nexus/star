# Phase 5 Live Progress — E7 100% Moving P99 Tail Composition

> Temporary active-work supplement to `docs/dev/10k-online-roadmap.md`. Durable evidence belongs in STAR Lab.

**Date:** 2026-09-07  
**Status:** ACTIVE / PREREGISTERED — formal three-repeat attribution pending

## Retained production

```text
e7ba18b31870577110b591104ef8fa7b4713e43c
A + B + C1 + C2a + D1 + E6-1
```

E6-2 slotted composition is CLOSED / NOT MATERIAL and does not modify production.

## E7 question

> In current 10K / 100%-moving production, which controlled-work sections rise on the same tail frames and create the repeatable uplift from ordinary frames toward the 33.33 ms boundary?

## Isolation

E7 runs exact retained production in a detached worktree. No `rotk_env/` runtime code changes.

The existing profiler already stores aligned per-frame controlled work, section self/inclusive times and frame metrics. The experiment-only launcher extends retention to 10 seconds and computes conditional-tail diagnostics only when `get_stats()` is queried.

## Formal design

```text
3 identical independent repeats
10000 resident
100% moving
Fog ON
staggered
seed / phase seed 42 / 42
route steps 12
realtime_defer
uncapped render
MiniMap dynamic units OFF
input blocked
execution pathfinding OFF
20 s run
snapshot at 19 s
10 s profiler horizon
>=250 aligned frames required per repeat
```

Primary attribution:

```text
tail      = controlled_work >= p95
reference = p25 <= controlled_work <= p75
section uplift = mean(self_ms | tail) - mean(self_ms | reference)
```

Use self time for additive contribution accounting. Inclusive time is diagnostic only.

## Frozen stability rule

```text
positive top-3 contributor in >=2/3 repeats
median tail uplift >=0.15 ms
```

Possible decisions:

```text
STABLE_TAIL_CONTRIBUTORS_FOUND
NO_ACTIONABLE_STABLE_TAIL_CONTRIBUTOR
INVALID_GUARDS
```

P99 and frames above 33.33 ms remain diagnostic; E7 cannot update the Performance Frontier.

## Tooling

Experiment branch:

```text
experiment/phase5-tail-composition-attribution
```

Frozen measurement tooling commit:

```text
86bd5ead19243f7731e8af40f16cb2cb0cbd5bc7
```

Canonical command:

```bash
bash tools/run_phase5_tail_composition.sh
```

Artifacts follow the two-tier Compact + Raw standard.

## STAR Lab

```text
experiments/2026-09-10k-phase5-e7-tail-composition/
```
