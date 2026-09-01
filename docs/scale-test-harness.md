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
```

The harness can call the phases independently:

```text
generate targets
  -> build_planning_snapshot
  -> 5k x plan_move
  -> PreparedMoveBatch

PreparedMoveBatch
  -> 5k x execute_move_plan
  -> no pathfinding
```

`STRESS_STACK_ENDPOINT` changes only endpoint legality:

```text
NORMAL:                occupied endpoint = reject; enemy traversal = blocked
STRESS_STACK_ENDPOINT: occupied endpoint = allow;  enemy traversal = blocked
```

The stress policy is an explicit planner policy. Normal movement code never
reads a global "stress mode" boolean.

## Three separable experiments

### 1. Target generation

The harness generates all requested targets from static board geometry first.
No occupancy snapshot and no pathfinding occurs in this phase.

Profiler section:

```text
scale_target_generation
```

### 2. Planning / correction

One `MovementPlanningSnapshot` captures shared board costs and occupancy. Every
selected unit then runs pathfinding against that same snapshot. If the requested
route exists but exceeds the current MP budget, the batch planner can resolve the
plan to the farthest legal endpoint on that route within budget.

Profiler sections:

```text
scale_planning_snapshot
scale_batch_pathfinding
move_pathfinding
```

The UDS response reports total planning time and per-plan P50/P95/P99 timing.
Planning is pure: it does not spend MP, move HexPosition, start animation, or
record movement statistics.

### 3. Prepared execution

The prepared plans can later be started without re-running pathfinding:

```text
scale_batch_execute
scale_active_moving_count
```

This is the primary dynamic-world test for simultaneous movement, animation,
HexPosition commits, UnitSpatialIndex churn, Vision invalidation, minimap and
rendering.

## Driver

Prepare a 100% movement-density batch:

```bash
uv run tools/scale_driver.py \
  --socket /tmp/star-scale.sock \
  prepare \
  --density 1.0 \
  --seed 42 \
  --target-radius 12
```

Start the already-prepared batch:

```bash
uv run tools/scale_driver.py \
  --socket /tmp/star-scale.sock \
  start
```

Inspect actual moving density:

```bash
uv run tools/scale_driver.py \
  --socket /tmp/star-scale.sock \
  status
```

Discard the prepared batch:

```bash
uv run tools/scale_driver.py \
  --socket /tmp/star-scale.sock \
  clear
```

For normal endpoint legality during a planning experiment:

```bash
uv run tools/scale_driver.py --socket /tmp/star-scale.sock prepare \
  --density 1.0 --policy normal
```

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
`scale_batch_pathfinding` value is a Planning Plane result; movement-frame costs
after `start` are Execution Plane / Dynamic World results.
