# Scale Test Harness

`Scale Test Harness` is STAR's local control plane for orthogonal large-world
experiments. It deliberately bypasses Hub/WebSocket/observations/LLMs and only
orchestrates ENV domain APIs on the main thread, so simulation, planning,
visibility and rendering can be measured independently from serving load.

## Enable

```bash
STAR_SCALE_HARNESS_SOCKET=/tmp/star-scale.sock \
uv run rotk_env/main.py \
  --skip-start \
  --scenario TestMap-8K-scale-5000 \
  --mode real_time \
  --players human_vs_two_ai \
  --seed 42 \
  --no-hub \
  --profile
```

`STAR_SCALE_HARNESS_SOCKET=1` uses `/tmp/star-scale.sock`. The UDS server is
non-blocking and polled on the ENV main thread; no extra ECS worker thread is
created.

## Orthogonal movement API

Normal benchmark/gameplay remains:

```text
move_unit
  -> plan_move(policy=NORMAL)
  -> execute_move_plan
       -> MP / recovery / statistics
       -> prepared motion
```

Scale/debug tooling composes the lower-level capabilities directly:

```text
generate targets
  -> build_planning_snapshot
  -> N x plan_move
  -> PreparedMoveBatch

PreparedMoveBatch
  -> execute_move_plan          # one-shot, normal side effects
or
  -> start_prepared_motion      # pure motion, no MP/recovery/stats
```

`STRESS_STACK_ENDPOINT` changes endpoint legality only:

```text
NORMAL:                occupied endpoint = reject; enemy traversal = blocked
STRESS_STACK_ENDPOINT: occupied endpoint = allow;  enemy traversal = blocked
```

Normal movement never reads a global stress flag.

## Phase 1: target generation

Target generation uses static board geometry only. It performs neither an
occupancy snapshot nor pathfinding.

```text
scale_target_generation
```

## Phase 2: planning / correction

One `MovementPlanningSnapshot` is shared by the whole batch. Each selected unit
then plans against that same snapshot.

Two correction types are reported separately:

```text
budget
  route exists but exceeds spendable MP
  -> trim to farthest affordable endpoint on that route

unreachable
  requested target has no route under the planning snapshot
  -> choose the budget-reachable endpoint nearest requested target
```

`prepare` enables unreachable correction by default. Use
`--no-correct-unreachable` to preserve raw no-path failures and measure the
pathfinding tail directly.

Profiler sections:

```text
scale_planning_snapshot
scale_batch_planning
move_pathfinding
move_unreachable_correction
```

Response fields include:

```text
corrected_units
budget_corrected_units
unreachable_corrected_units
failure_reasons
plan_p50_ms / plan_p95_ms / plan_p99_ms
```

Planning is pure: no MP spend, HexPosition mutation, animation start or normal
movement statistics.

## Phase 3A: one-shot prepared execution

```bash
uv run tools/scale_driver.py --socket /tmp/star-scale.sock start
```

This executes the prepared plans without re-running pathfinding, while preserving
normal move side effects:

```text
MP spend
ResourceRecovery scheduling
movement statistics
motion / animation
```

Use this for mass action admission / one-shot move bursts.

```text
scale_batch_execute
scale_active_moving_count
```

## Phase 3B: sustained Dynamic World execution

Sustained mode turns each short prepared route into a repeated forward/backward
route long enough for a fixed measurement interval, then starts it once through
`start_prepared_motion`.

During the interval there is:

```text
NO pathfinding
NO MP spend
NO ResourceRecovery scheduling
NO normal movement-action statistics
NO per-frame harness restart loop
```

The measured data plane is therefore primarily:

```text
MovementAnimation
HexPosition commits
UnitSpatialIndex churn
Vision/FoW invalidation
minimap invalidation
viewport culling
unit rendering
```

### Temporal phase is an independent workload dimension

All Units started with identical animation progress are phase-locked. With the
current 2 hex/s speed, a synchronized 5000-Unit run can make all 5000 Units cross
a hex boundary at nearly the same time every ~0.5 seconds. That is a valid worst
case, but it is not the same experiment as a steady dynamic world.

The harness therefore exposes two explicit modes.

#### Synchronized: burst resilience

```bash
uv run tools/scale_driver.py \
  --socket /tmp/star-scale.sock \
  start-sustained \
  --duration 20 \
  --phase synchronized
```

All Units start at phase zero. Use this to measure simultaneous update bursts,
including worst-case Vision/FoW invalidation.

#### Staggered: steady-state scalability

```bash
uv run tools/scale_driver.py \
  --socket /tmp/star-scale.sock \
  start-sustained \
  --duration 20 \
  --phase staggered \
  --phase-seed 42
```

Staggered mode keeps every Unit's route and speed unchanged. It inserts exactly
one zero-distance initial hold segment and assigns a deterministic progress offset
inside that hold. After the hold, Units follow the same prepared routes at the
same speed, but their hex-boundary commits are spread across the segment period.

This isolates **temporal burstiness** as the only intended workload difference.
The response reports:

```text
motion_phase
phase_seed
phase_progress_p50
phase_progress_p95
segments_total                  # real motion segments
animation_segments_total        # includes stagger hold segment
```

Profiler metadata records:

```text
scale_sustained_phase
scale_sustained_phase_seed
scale_sustained_segments_total
scale_sustained_animation_segments_total
```

One-time kickoff:

```text
scale_sustained_start
```

Live density:

```text
scale_active_density_sample
scale_active_moving_units
scale_actual_density
```

Cancel a sustained run:

```bash
uv run tools/scale_driver.py --socket /tmp/star-scale.sock stop-sustained
```

## Incremental Vision / Fog-of-War instrumentation

Large dynamic worlds use an incremental visibility pipeline:

```text
HexPosition commit
  -> mark_vision_dirty(unit)
  -> recompute only dirty Unit geometry
  -> diff old/new tiles
  -> faction tile reference counts
  -> incrementally update FogOfWar.faction_vision
```

The old per-frame `clear faction_vision -> union every Unit` path is no longer
used in indexed scale worlds.

Visibility geometry is cached by:

```text
(center_hex, effective_range, terrain_revision)
```

`invalidate_all()` is retained for LOS-affecting terrain changes; it bumps the
terrain revision and invalidates the geometry cache.

Profiler frame metrics:

```text
fog_enabled
fog_toggle_this_frame
vision_mode                       # dirty_refcount
vision_dirty_units
vision_units_changed
vision_units_scanned              # actual recompute work, not resident N
vision_tile_updates
vision_unit_tiles_added
vision_unit_tiles_removed
vision_faction_tiles_added
vision_faction_tiles_removed
vision_geometry_cache_hits
vision_geometry_cache_misses
vision_geometry_cache_size
vision_audit_scanned
```

A low-rate `vision_audit_scan` remains as a correctness safety net in indexed
scale worlds. Legacy/base worlds without `UnitSpatialIndex` audit every tick so
direct HexPosition writes retain the previous immediate semantics.

`FogOfWar.enabled` is still only the global consumer-side switch. Visibility and
explored sets continue to update while fog is off, so turning fog back on does
not require a visibility rebuild. `fog_toggle_this_frame` lets slow-frame logs
distinguish an actual toggle frame from a coincident movement/vision burst.

## Driver examples

Prepare a 100% batch:

```bash
uv run tools/scale_driver.py \
  --socket /tmp/star-scale.sock \
  prepare \
  --density 1.0 \
  --seed 42 \
  --target-radius 12
```

Raw no-path planning measurement:

```bash
uv run tools/scale_driver.py \
  --socket /tmp/star-scale.sock \
  prepare \
  --density 1.0 \
  --seed 42 \
  --target-radius 12 \
  --no-correct-unreachable
```

Inspect status:

```bash
uv run tools/scale_driver.py --socket /tmp/star-scale.sock status
```

Stop motion and discard the batch:

```bash
uv run tools/scale_driver.py --socket /tmp/star-scale.sock clear
```

## Recommended experimental matrix

Use a fresh deterministic world for every measured run:

```text
10%   density=0.10
25%   density=0.25
50%   density=0.50
75%   density=0.75
100%  density=1.00
```

For each density, keep map, seed, target radius, duration, camera/viewport and FPS
cap fixed, and separate the following conditions:

```text
Steady-state scalability:
  Fog OFF × staggered
  Fog ON  × staggered

Burst resilience:
  Fog OFF × synchronized
  Fog ON  × synchronized
```

A practical first pass is 20 seconds per condition.

Do **not** reuse one PreparedMoveBatch after a sustained run has moved its Units
away from their planned starts. For synchronized-vs-staggered A/B, restart/reset
the ENV with the same seed and run `prepare` again before each condition.

## Interpretation

Do not call a run "5000 active" merely because 5000 commands were requested.
Use:

```text
requested_units
prepared_units
accepted_units
active_moving_units
actual_density
failure_reasons / rejection_reasons
```

Likewise, do not collapse temporal behavior into one FPS number:

```text
staggered sustained
  -> steady Dynamic World P50/P95/P99

synchronized sustained
  -> burst resilience, max/P99.9/slow-frame anatomy
```

Planning latency belongs to the Planning Plane. Frame costs after sustained start
belong to the Execution / Dynamic World plane. Fog/Vision should be compared by
actual dirty/recomputed Unit count, not resident Unit count alone.
