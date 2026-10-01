# E5: Movement ∥ owned Visuals compute (private research)

The research entry `_movement_visuals_step_json(dt, wall_time, mode,
min_damage_rows=8, profile=False)` never changes ordinary step policy, API18,
schema5, Agent action order, game rules or default native1. The target remains
5000 Units + 1000 Agents; 5000 Agents is deferred.

## Dependency proof

| Stage | Reads | Writes | Boundary |
|---|---|---|---|
| Clock | dt, time configuration | clock, singleton, revision | Before Statistics |
| Statistics | old Position/MP/Fog, observation cycle | histories, visibility, counts | Complete before preparation; error stops E5 |
| Movement | Movement animation, Position, map | Position values, animation, spatial index, dirty sets, moving membership | No Position insertion/removal, entity allocation/deletion |
| Visuals compute | owned maps, raw dt, attack IDs' Position existence, next external ID | owned maps, dirty/removed rows, ordered Spawn/Remove journal | No ECS/World borrow, no spatial coordinates read |
| Visuals publish | successful journal prefix | world structure, InitialComponents, unit membership, Visuals ownership | After Movement; before Recovery |
| Recovery/Lifecycle/Vision/Capture | existing complete world | existing fields/events | Original serial order and errors |

Presence facts remain valid during Movement because Movement only updates existing
Position values. IDs predicted with checked addition remain valid because neither
Movement nor another ingress can allocate an ID in this region. Instance admission
holds the existing Mutex for the entire step. No global pool, cross-request shared
mutable state, nested Statistics tasks, World clone, or complete Visuals clone is
introduced. The existing instance ReadPool has one worker plus caller in this
region even when configured with four workers.

The immediate and planned paths monomorphize the same `Visuals::advance` algorithm
through `VisualAccess`. Phase order remains attack → new projectiles → projectile
advance → effects → floating damage. Newly spawned arrows receive the full raw dt
in this tick. `forget` still removes all visual maps for a hybrid entity. Actual
World spawn and `remove_entity` occur in original journal order. No opportunistic
spatial/moving cleanup is added to legacy removal.

## Errors and lifecycle

An expected visual error returns the original message after publishing only the
successful journal prefix and returning partially updated maps. A failed ID spawn
never increments the planned counter or records an operation. Effect duration
zero returns before pending removals of that effect phase; earlier projectile
removals stay committed. Capture errors preserve all prior commits. Statistics
errors happen before taking any Visuals ownership.

The root owns `VisualWork`; scoped worker borrows it. ReadPool joins both sides
before resuming a panic. An outer catch publishes the retained work, returns maps,
then resumes the original panic into the existing poisoned-native boundary.
This promises ownership/lifetime closure, not rollback of panic state. Rust tests
exercise worker/caller faults and pool reuse. No job outlives step/reset/close.

## Modes and measurement

* baseline: original ordered Movement → Visuals.
* empty_fork: empty worker overlaps actual Movement; serial Visuals after join.
* split_serial: narrow preparation → Movement → planned Visuals → publish.
* parallel: narrow preparation → worker Visuals ∥ caller Movement → join → publish.

Eligibility requires window, present/enabled AnimationSystem, nonempty moving set,
and damage row threshold. empty_fork/parallel additionally need an instance pool;
1-thread and other configurations use the original path. split_serial can test the
ownership adapter at native1. Invalid modes are rejected before clock writes.
Thresholds are per call, never persisted into exports or resets.

PROFILE=false specializes out all timers and diagnostic counter writes. Ordinary
step specializes out the E5 eligibility predicate and ownership/dispatch paths.
PROFILE=true records preparation, compute, publish and inclusive region timing;
region and Movement/compute overlap, so they must not be summed.

E3's diagnostic optimistic budget excluding structure is 8.1–8.2µs/all ticks.
Threshold8 selects 3772/9880 recorded ticks, with about13µs conditional ideal budget.
These are upper bounds before preparation, publication or scheduling; they are
not speedups. E4 scheduling cost is not an E5 break-even measurement because a
longer caller Movement may hide worker wake/join costs.

Final measured decision and raw evidence are owned by STAR Lab's
`experiments/2026-10-rust-movement-visuals-parallel/` package. Ordinary step remains
unmodified by the decision; this research does not claim live capacity or Frontier.

## Unprofiled primary decision

| Threads / round | Mean improvement | CI95 improvement (µs) | P99 control → parallel (µs) | Gate |
|---|---:|---:|---:|---|
| 2 / 1 | 0.593% | [0.553, 2.109] | 629.208 → 618.709 | pass |
| 2 / 2 | 0.688% | [-0.473, 3.991] | 763.083 → 736.167 | fail |
| 2 / 3 | -0.023% | [-1.512, 1.210] | 655.166 → 690.583 | fail |
| 4 / 1 | -0.747% | [-5.423, 1.041] | 673.209 → 681.625 | fail |
| 4 / 2 | -0.273% | [-4.884, 2.474] | 753.666 → 738.208 | fail |
| 4 / 3 | 0.742% | [0.899, 2.339] | 604.583 → 582.250 | pass |

Both configurations pass only one of three rounds, so neither is enabled in ordinary step. The private per-call research modes remain available.
Single-instance confirmation and live windows are not entered because native4
fails the prerequisite gate. Diagnostic overlap and sensitivity are explanatory
research, not a replacement winning threshold or new capacity result.
