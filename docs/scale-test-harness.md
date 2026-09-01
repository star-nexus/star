# Scale Test Harness

`Scale Test Harness` is STAR's local control plane for dynamic-world scale tests.
It deliberately does **not** use the Hub, WebSocket protocol, observations, or an
LLM. The harness only orchestrates existing ENV domain APIs on the main thread so
simulation/rendering scalability can be measured independently from serving and
protocol scalability.

## Enable

The harness is mounted only by the window-scale movement adapter and only when
`STAR_SCALE_HARNESS_SOCKET` is set.

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

`STAR_SCALE_HARNESS_SOCKET=1` uses `/tmp/star-scale.sock`.

The UDS server is non-blocking and polled on the ENV main thread. No ECS worker
thread is created.

## Orthogonal movement API

Normal benchmark/gameplay still calls:

```text
move_unit
  -> plan_move(policy=NORMAL)
  -> execute_move_plan
       -> MP / recovery / statistics
       -> prepared motion
```

Scale/debug tooling can compose lower-level phases independently:

```text
generate targets
  -> build_planning_snapshot
  -> N x plan_move
  -> PreparedMoveBatch

PreparedMoveBatch
  -> execute_move_plan          # normal one-shot side effects
or
  -> start_prepared_motion      # pure motion; no MP/recovery/stats
```

`STRESS_STACK_ENDPOINT` changes only endpoint legality:

```text
NORMAL:                occupied endpoint = reject; enemy traversal = blocked
STRESS_STACK_ENDPOINT: occupied endpoint = allow;  enemy traversal = blocked
```

The stress policy is an explicit planner policy. Normal movement code never
reads a global "stress mode" boolean.

## Separable experiments

### 1. Target generation

The harness generates all requested targets from static board geometry first.
No occupancy snapshot and no pathfinding occurs in this phase.

Profiler section:

```text
scale_target_generation
```

### 2. Planning / correction

One `MovementPlanningSnapshot` captures shared board costs and occupancy. Every
selected unit then runs pathfinding against that same snapshot.

Two correction types are reported separately:

```text
budget
  requested route exists, but exceeds current spendable MP
  -> trim to the farthest affordable endpoint on that route

unreachable
  requested target has no route under the planning snapshot
  -> choose the budget-reachable endpoint nearest to the requested target
```

`prepare` enables unreachable correction by default. Use
`--no-correct-unreachable` when the goal is to measure raw no-path tail cost.

Profiler sections:

```text
scale_planning_snapshot
scale_batch_planning
move_pathfinding
move_unreachable_correction
```

`scale_batch_planning` is total per-unit planning/admission/correction work.
`move_pathfinding` isolates the original requested-target A* work.
`move_unreachable_correction` isolates the optional nearest-reachable recovery.
Planning remains pure: it does not spend MP, move HexPosition, start animation,
or record movement statistics.

The response reports:

```text
corrected_units
budget_corrected_units
unreachable_corrected_units
failure_reasons
plan_p50_ms / p95 / p99
```

### 3A. One-shot prepared execution

```bash
uv run tools/scale_driver.py --socket /tmp/star-scale.sock start
```

This calls `execute_move_plan` for the prepared plans without re-running
pathfinding. It intentionally keeps normal move side effects:

```text
MP spend
ResourceRecovery scheduling
movement statistics
motion/animation
```

Profiler sections:

```text
scale_batch_execute
scale_active_moving_count
```

Use this for a mass action-admission / one-shot movement burst.

### 3B. Sustained Dynamic World execution

For a stable active-density interval, start the same prepared batch as pure
motion:

```bash
uv run tools/scale_driver.py \
  --socket /tmp/star-scale.sock \
  start-sustained \
  --duration 20
```

The harness expands each short prepared path into a repeated forward/backward
route (`A -> B -> ... -> B -> A -> ...`) long enough for the requested duration,
then starts that route **once** through `start_prepared_motion`.

During sustained execution there is:

```text
NO pathfinding
NO MP spend
NO ResourceRecovery scheduling
NO normal movement-action statistics
NO per-frame harness restart loop
```

The runtime work is therefore dominated by the Dynamic World data plane:

```text
MovementAnimation
HexPosition commits
UnitSpatialIndex churn
Vision/minimap invalidation
viewport culling
unit rendering
```

Profiler section for the one-time kickoff:

```text
scale_sustained_start
```

Live density continues to be sampled by:

```text
scale_active_density_sample
scale_active_moving_units
scale_actual_density
```

The low-rate density observer records its own cost so measurement overhead is
visible.

Cancel a sustained run manually with:

```bash
uv run tools/scale_driver.py \
  --socket /tmp/star-scale.sock \
  stop-sustained
```

## Driver examples

Prepare a 100% movement-density batch:

```bash
uv run tools/scale_driver.py \
  --socket /tmp/star-scale.sock \
  prepare \
  --density 1.0 \
  --seed 42 \
  --target-radius 12
```

To preserve raw `no_path` failures instead of correcting them:

```bash
uv run tools/scale_driver.py \
  --socket /tmp/star-scale.sock \
  prepare \
  --density 1.0 \
  --seed 42 \
  --target-radius 12 \
  --no-correct-unreachable
```

Run a normal one-shot execution:

```bash
uv run tools/scale_driver.py \
  --socket /tmp/star-scale.sock \
  start
```

Run a 20-second sustained Dynamic World workload:

```bash
uv run tools/scale_driver.py \
  --socket /tmp/star-scale.sock \
  start-sustained \
  --duration 20
```

Inspect actual moving density:

```bash
uv run tools/scale_driver.py \
  --socket /tmp/star-scale.sock \
  status
```

Stop sustained motion and discard the prepared batch:

```bash
uv run tools/scale_driver.py --socket /tmp/star-scale.sock clear
```

For normal endpoint legality during a planning experiment:

```bash
uv run tools/scale_driver.py --socket /tmp/star-scale.sock prepare \
  --density 1.0 --policy normal
```

## Recommended density matrix

Use a fresh world (or an equivalent deterministic reset) for each measured run:

```text
10%   density=0.10
25%   density=0.25
50%   density=0.50
75%   density=0.75
100%  density=1.00
```

For the Dynamic World curve, keep `seed`, map, target radius, sustained duration,
viewport/camera state, FPS cap, and Fog setting fixed. A practical first pass is
20 seconds per density.

## Interpretation

Do not call a run "5000 active units" merely because 5000 commands were
requested. Use the returned/profiler values:

```text
requested_units
prepared_units
accepted_units
active_moving_units
actual_density
failure_reasons / rejection_reasons
```

Planning and execution are intentionally separate. A large
`scale_batch_planning` value is a Planning Plane result. Frame costs during
`start-sustained` are Execution Plane / Dynamic World results.
