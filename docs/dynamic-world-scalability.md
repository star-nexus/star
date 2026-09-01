# Dynamic World Scalability

This document records STAR's large-world execution methodology. It deliberately
separates resident world size, active movement density, discrete state-transition
rate, temporal burstiness, visibility work, and rendering work instead of calling
all of them simply "number of units".

## Why this benchmark exists

A world with 5000 resident units can still be cheap if almost nothing changes.
Conversely, 5000 units crossing a discrete hex boundary in the same frame can be
far more expensive than 5000 continuously moving units whose boundary crossings
are distributed over time.

For scale experiments, keep these dimensions distinct:

```text
resident scale
  N_resident

continuous activity
  N_moving

state-transition load
  N_hex_commits / frame

subsystem activity
  N_vision_dirty / frame
  N_minimap_dirty / frame
  N_render_visible / frame

temporal burstiness
  synchronized vs staggered transitions
```

The central measurement rule is therefore:

> `5000 moving` and `5000 state transitions in one frame` are different loads.

Both are important and both are retained.

---

## Validated 5000-unit findings before Curve v1

Scenario and workload:

```text
scenario       TestMap-8K-scale-5000
map            91 x 91 = 8281 hexes
resident       5000 living units
seed           42
target radius  12
motion speed   ~2 hex/s
FPS cap        60
```

### Planning plane

Two independent 5000-unit preparations with the same seed produced essentially
identical results:

```text
prepared                5000 / 5000
budget-corrected         4275
unreachable-corrected      81
failed                      0
batch planning          ~0.99-1.00 s
plan P50                ~0.033 ms
plan P95                ~0.094 ms
plan P99                ~9.8 ms
```

This establishes deterministic workload generation and also exposes a separate
long-tail pathfinding problem. Planning is not part of the Dynamic World execution
curve; it is measured in its own epoch.

### 100% synchronized execution

All 5000 units were active, with identical phase. Approximately every 31 frames,
5000 units crossed a hex boundary together.

Representative synchronized transition bursts:

```text
vision_dirty_units            5000
vision_units_changed           5000
vision_tile_updates           95000
VisionSystem             ~28.6-53.6 ms
AnimationSystem                ~19.1 ms
burst frame                    ~64-86 ms
```

Geometry-cache hit rates were about 97-98%, so the remaining burst cost is
primarily the cost of maintaining thousands of simultaneous state deltas rather
than repeating LOS geometry.

This is not treated as a generator artifact to hide. It is a formal worst-case
benchmark:

> **5000 Simultaneous State-Transition Burst** — if 5000 entities really cross a
> discrete world-state boundary at the same time, how resilient is the ENV?

### 100% staggered execution

The same 5000 prepared motions were given deterministic temporal phase offsets.
Speed and route semantics remained unchanged.

At 5000 moving units and ~2 hex/s:

```text
expected transitions/frame = 5000 * 2 / 60 ~= 166.7
observed vision dirty/frame ~= 151-164 in representative frames
VisionSystem                ~= 1.1-1.5 ms in representative steady frames
```

This validates that the staggered workload models steady Dynamic World activity
rather than synchronized bursts, and that incremental Vision cost is now driven
primarily by `N_vision_dirty`, not `N_resident`.

---

# Benchmark A — Dynamic World Density Curve v1

Purpose:

> Measure steady-state execution cost as the fraction of continuously moving
> entities increases while resident world size stays fixed at 5000.

## Fixed experiment conditions

Every curve point uses a **fresh ENV process** and keeps all non-density variables
fixed:

```text
scenario       TestMap-8K-scale-5000
resident       5000
mode           real_time
players        human_vs_two_ai
Hub            disabled
seed           42
target radius  12
phase          staggered
phase seed     42
sustained      20 s
snapshot       t = 10 s after kickoff
FogOfWar       ON
camera         unchanged during measurement
zoom           unchanged during measurement
keyboard/mouse no manual interaction during measurement
FPS cap        60
```

Density points:

```text
0.10  -> nominal  500 moving units
0.25  -> nominal 1250 moving units
0.50  -> nominal 2500 moving units
0.75  -> nominal 3750 moving units
1.00  -> nominal 5000 moving units
```

Actual values must always be reported from:

```text
prepared_units
accepted_units
active_moving_units
actual_density
```

Do not substitute requested density for achieved density.

## Measurement epochs

A formal point has three separate phases:

```text
Planning epoch
    target generation
    planning snapshot
    N x planning/correction

Kickoff frame
    construct/start sustained animations

Execution measurement epoch
    begins at the next frame boundary
    profiler statistics reset here
```

The deferred boundary reset means the execution P50/P95/P99/max do **not** include:

- the ~1 s planning burst;
- target generation;
- planning snapshot construction;
- the one-time sustained kickoff frame.

The execution epoch is the only epoch used for the density curve.

## Primary curve metrics

For each density point record:

```text
avg_frame_ms
P50 frame ms
P95 frame ms
P99 frame ms
max frame ms
avg FPS
min FPS
active work ms
slow-frame count
```

Subsystem metrics:

```text
AnimationSystem
VisionSystem
MapRenderSystem
UnitRenderSystem
MiniMapSystem
render_engine
unit_visible_cull
unit_batch_prepare
minimap_unit_refresh
input_event_pump
```

Experiment guards:

```text
Fog remained ON
camera unchanged
zoom unchanged
active_moving_units at snapshot
actual_density at snapshot
rolling profiler window full
```

A point with a failed guard is not a valid curve point and should be rerun.

## One-command point runner

After starting a fresh ENV with the Scale Harness, run for example:

```bash
uv run tools/scale_driver.py \
  --socket /tmp/star-scale.sock \
  density-point \
  --density 0.50 \
  --seed 42 \
  --target-radius 12 \
  --duration 20 \
  --phase staggered \
  --phase-seed 42 \
  --require-fog on \
  --sample-after 10 \
  --output results/dynamic-world-v1/density-050.json
```

The driver performs:

```text
prepare
  -> start-sustained
  -> wait to steady state
  -> profile-snapshot
  -> combined JSON
```

Restart the ENV before the next density point.

---

# Benchmark B — Burst Resilience v1

Purpose:

> Measure worst-case response to a highly correlated state-transition burst.

Fixed conditions are the same as Density Curve v1 except:

```text
density = 1.00
phase   = synchronized
```

Command:

```bash
uv run tools/scale_driver.py \
  --socket /tmp/star-scale.sock \
  density-point \
  --density 1.00 \
  --seed 42 \
  --target-radius 12 \
  --duration 20 \
  --phase synchronized \
  --require-fog on \
  --sample-after 10 \
  --output results/dynamic-world-v1/burst-100-synchronized.json
```

The key result is not average FPS alone. Preserve:

```text
maximum burst frame
P99 / slow-frame distribution
N state transitions in burst frame
vision_dirty_units in burst frame
AnimationSystem burst cost
VisionSystem burst cost
render/minimap costs in the same frame
```

A synchronized result must not be merged into the steady density curve, and the
steady staggered curve must not be used to claim that simultaneous 5000-entity
state transitions are cheap. They answer different questions.

---

## Current next-bottleneck interpretation

After incremental Vision optimization, representative staggered 5000-unit frames
put Vision around ~1-1.5 ms while rendering-related work became more prominent:

```text
render_engine
MapRenderSystem / FoW presentation
MiniMap refresh
Unit render preparation/culling
AnimationSystem
```

Curve v1 should be collected before optimizing these further. That gives a clean
baseline showing where the next bottleneck emerges as dynamic density increases.
