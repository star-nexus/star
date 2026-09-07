# Phase 5 Live Progress — E6-2 Slotted Spatial Record Composition

> Temporary active-work supplement to `docs/dev/10k-online-roadmap.md`.
> Durable evidence and final decisions belong in STAR Lab.

**Date:** 2026-09-07  
**Status:** ACTIVE / PREREGISTERED — formal composition A/B pending

## Current retained production

E6-1 is KEEP and is the new retained Phase-5 production state:

```text
e7ba18b31870577110b591104ef8fa7b4713e43c
```

KEEP chain:

```text
A + B + C1 + C2a + D1 + E6-1
```

Formal E6-1 100%-moving result:

```text
controlled p99 = 33.677126 ms
30 Hz gate     = 33.33 ms
classification = FAIL by 0.347126 ms
```

Performance Frontier remains unchanged.

## Why revisit E5-1 now

E5-1 previously measured a real but partial positive signal from
`UnitSpatialRecord slots=True`:

```text
Cull saving ~0.090 ms @50%
Cull saving ~0.113 ms @100%
```

It was correctly rejected as the main root solution because the dominant
first-touch cause was still unknown. E5-3 -> E6 -> E6-1 later established and
removed the dominant world-coordinate payload mechanism.

The current question is therefore new:

> Does the old slotted-record representation benefit remain independently useful
> after composing it with retained E6-1 bounded geometry reuse?

This does not reopen E5 root-cause attribution.

## E6-2 isolation

Control and treatment both run exact retained E6-1 source:

```text
e7ba18b31870577110b591104ef8fa7b4713e43c
```

Treatment only changes the record representation before world construction:

```python
@dataclass(frozen=True, slots=True)
class UnitSpatialRecord:
    ...same fields...
```

Preserved:

```text
E6-1 bounded geometry ownership
fresh record identity
record fields / values
Cull
spatial containers
HexPosition authority
movement / Vision / Fog semantics
```

## Frozen tooling

Experiment branch:

```text
experiment/phase5-unitrender-e6-2-slotted-composition
```

Frozen formal tooling commit:

```text
a524e610bdfce7eab37fee3fcf4cff69dac89ab5
```

Canonical command:

```bash
bash tools/run_phase5_unitrender_e6_2.sh
```

Order:

```text
A50 -> B50 -> B100 -> A100
```

## Preregistered gates

```text
position commits/s within ±2%
Vision changed/s within ±2%
Fog delta/s within ±2%
Cull saving >= 0.05 ms @50%
Cull saving >= 0.07 ms @100%
UnitRender avg regression <= 1%
controlled avg regression <= 1%
Animation avg regression <= 2%
```

Possible attribution decisions:

```text
SLOTTED_RECORD_COMPOSITION_CANDIDATE_JUSTIFIED
SLOTTED_RECORD_COMPOSITION_NOT_MATERIAL
```

Positive attribution is not production KEEP. If positive, next step is the exact
one-line source candidate (`slots=True`) followed by source-vs-source validation.

## Canonical gate remains separate

At 10K / 100% moving:

```text
controlled_work_frame_ms.p99 <= 33.33 ms
```

is reported as a diagnostic during composition attribution. Frontier movement
requires validated production source, not an attribution treatment.

## Artifact policy

Canonical runner emits:

```text
<run-id>-compact.zip
<run-id>-raw.zip
```

Compact is the default review / Agent / LLM artifact. Raw remains authoritative
for forensic re-audit.

## STAR Lab case

```text
experiments/2026-09-10k-unitrender-e6-2-slotted-record-composition/
```
