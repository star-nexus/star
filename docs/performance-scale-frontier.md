# System-Scale Frontier / Resource Trade-off

Phase 4 asks two questions on the current production runtime:

- **C — System-scale frontier:** where does STAR-controlled runtime cost lose 60 Hz capacity as the world scales?
- **D — Resource trade-off:** is that frontier driven primarily by resident population, moving density, or temporal concentration of movement?

The experiment reuses Phase-3 measurement semantics. It does not restore historical `scale_*` runtime forks.

## Measurement boundary

The explicit `--scale-harness-socket` flag mounts a test-only UDS controller after the normal world has been assembled. The production Window Animation, Movement commit, spatial index, Vision/Fog and render systems remain unchanged.

Route preparation is outside steady-state timing. During sustained execution the harness does not pathfind, spend MP, recover resources or record normal move actions. It starts long deterministic movement animations once, then the production `AnimationSystem` performs every subsequent segment and `HexPosition` commit.

This is intentionally a **pure dynamic-world execution workload**, not a game-legality benchmark. Occupancy/resources are excluded so destination conflicts and planning cost cannot hide the runtime frontier being measured.

Gameplay key/mouse events are blocked while the harness is mounted; SDL event pumping and display presentation remain active.

### Realtime cyclic-GC condition

The historical Realtime-GC case established that automatic CPython generation-2 collection can create rare latency cliffs while `UnitRenderSystem` happens to be the active timed scope. Formal latency-critical scale points therefore use the accepted bounded `realtime_defer` policy:

```text
kickoff allocations complete
-> full Gen2 collection at the scale-control safe point
-> automatic cyclic GC disabled for the bounded sustained window
-> ordinary CPython reference counting remains active
-> original automatic-GC state restored on stop/clear/cleanup/deadline
```

This is a measurement condition, not a new rendering optimization. Normal STAR runtime remains unchanged unless the explicit scale harness is mounted. The formal `density-point` driver defaults to `realtime_defer`; manual `start` remains `auto` unless explicitly requested otherwise.

## Canonical point

Unless a specific ablation changes one field, record:

```text
mode             real_time
display          visible production window
Hub              offline
mock AI          off
Fog              on
seed             42
route seed       42
route steps      12
phase seed       42
gc policy        realtime_defer
warmup           5 s
sustained        20 s
sample after     7 s
profile horizon  final ~5 s wall-clock window
```

Every formal point uses a fresh STAR process. A full deterministic route pool is prepared first; execution density activates a nested prefix of that same shuffled pool.

## Capacity definition

The primary frontier signal is:

```text
controlled_work_frame_ms.p99
```

Interpret the 60 Hz STAR-controlled budget as:

```text
p99 <= 16.67 ms   within controlled 60 Hz capacity
p99 >  16.67 ms   beyond controlled 60 Hz capacity
```

This is explicitly a STAR-controlled CPU/runtime boundary, not a claim about end-to-end visible-window FPS. `display_present`, platform input and raw/window FPS stay observable for attribution but do not define the frontier by themselves.

For synchronized burst experiments also inspect controlled `max` and the `>16.67 ms` tail rate; a short burst can be important without dominating the five-second p99 distribution.

## Experiment order

### 0. Harness smoke

Use the normal 15-unit default scenario. Require all driver guards to pass and confirm production position/Vision/Fog metrics change while movement is active.

### 1. 5K production replay

Run the current production runtime on a reproducibly identified 5K map/workload. This establishes the new Phase-4 reference point. Historical 5K evidence remains context only because it used older source cohorts and a 300-frame profiler window.

Do not proceed to larger N until the 5K workload identity and causal profile are validated.

### 2. Current-production density frontier calibration

Do not repeat the archived full historical density curve. Hold resident population and map fixed and use the minimum current-production points needed to locate the 60 Hz boundary.

Current search rule:

```text
0% clear PASS
50% clear FAIL
25% requires clean classification under realtime_defer
```

After the clean 25% point:

```text
25% PASS -> next 37.5%
25% FAIL -> next 12.5%
```

Continue only until the boundary interval is decision-useful; do not chase false precision below ordinary runtime variance.

### 3. Temporal concentration

Once the highest clear-PASS staggered density is known, compare that same density and route pool under:

```text
staggered vs synchronized
```

This isolates temporal concentration of the same total dynamic workload.

Only after the density and concentration effects are understood should resident population N be increased. Keep map/workload identity explicit; do not compare different map footprints as if N were the only changed variable.

## Formal driver

Terminal A:

```bash
uv run python -m rotk_env.main \
  --skip-start \
  --mode real_time \
  --scenario <scenario> \
  --players human_vs_two_ai \
  --no-hub \
  --seed 42 \
  --uncapped \
  --scale-harness-socket /tmp/star-scale.sock
```

Terminal B:

```bash
uv run python tools/scale_driver.py \
  --socket /tmp/star-scale.sock \
  density-point \
  --density 0.25 \
  --phase staggered \
  --seed 42 \
  --phase-seed 42 \
  --route-steps 12 \
  --duration 20 \
  --warmup 5 \
  --sample-after 7 \
  --profile /tmp/scale-profile.json \
  --output /tmp/scale-point.json
```

`density-point` defaults to `--gc-policy realtime_defer`. The driver verifies that the requested policy is present in metadata and frame metrics, that bounded deferral remains active throughout the saved rolling window, and that automatic cyclic GC is disabled during that window. If those guards fail, the point is invalid rather than silently accepted.

The driver snapshots the profiler before running its O(N) status validation, so the validation scan cannot contaminate the saved window.

## Required evidence per point

Record at minimum:

```text
exact STAR SHA
map/scenario identity and dimensions
resident units
requested and achieved moving density
phase
route/phase seed
GC policy and policy guards
Fog state
controlled avg/p95/p99/max
controlled >16.67 ms tail
key subsystem timings
window throughput and present time as attribution-only context
all driver guards
```

Formal frontier records belong in STAR Lab only after workload identity and guards are validated.
