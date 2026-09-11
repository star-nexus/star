# Native runtime migration

The default game remains Python. R0 normalizes its replay ordering; R1 provides
an owned Rust scene, lifecycle/clock and CPython-compatible random streams.
**The Rust backend is not yet playable.** R2 is in progress: native movement,
resource recovery, combat, Fog and statistics have differential contract tests.
The complete permissions/Agent observation loop and the window handoff are still
pending. There is no silent backend fallback.

The Cargo workspace has three crates:

- `native/core`: generic ECS ownership, stable external IDs, simulation clock, RNG.
- `native/rotk`: RoTK scene/rules and native runtime.
- `native/python`: PyO3 binding and the standalone `star-native` Python package.

Rust 1.98.1, bevy_ecs 0.19.1, PyO3 0.29.2 and maturin 1.15.0 are pinned.
`Cargo.lock` records the complete Rust dependency resolution. Bevy rendering is
not included. Build/install for development from the repository root:

```sh
# Requires the pinned Rust toolchain on PATH for local source builds.
uv sync --extra native
cargo test -p star-core -p star-rotk --locked
cargo clippy --workspace --all-targets --locked -- -D warnings
uv run --extra native pytest -q
```

After editing Rust files, rebuild explicitly with
`uv sync --extra native --reinstall-package star-native` to avoid an old extension
in the active interpreter. Start a fresh Python process after rebuilding.
Performance measurements must use a release wheel, with its hash recorded in Lab.
Users of eventual published wheels will not need a Rust compiler. Cross-platform
wheel release/install acceptance remains R5 work.

R1 initialization can be exercised without changing the game entry point:

```python
from rotk_env.runtime.bootstrap import prepare_scene
from rotk_env.runtime.native import RustRuntime

initial = prepare_scene(mode="real_time", scenario="chibi-small", seed=42)
with RustRuntime(initial, threads=1) as runtime:
    assert not runtime.diagnostics()["gameplay_ready"]
    runtime.step(1 / 30, wall_time=1720000000.0)
    print(runtime.diagnostics())
```

`prepare_scene` uses the current Python loader once, returns detached data and
cleans up the temporary world. Hub/BOT startup is prohibited there; subscriptions
are isolated and restored. The native world never retains Python component
references. Imported component columns currently preserve cold initial state;
typed gameplay computation is added in R2/R3. `export_state` is a diagnostic
operation, not a per-frame synchronization mechanism.

The R2 intermediate implementation includes dynamic unit occupancy and stable
A* ties, instantaneous rule-mode movement and animated dummy/window movement,
and the existing severe-headcount-loss MP rule. Movement advances only active
units. AP/MP/skill cooldowns use versioned deadline buckets; an imported scene
preserves the scheduler ledger, including superseded tasks and pending MP spends.
Paused simulation time never advances recovery. Repeated AP spends preserve the
active cadence; MP recovery restarts at the next advancing recovery boundary.

Private `_movement_probe_json`, `_resource_probe_json`, `_combat_probe_json`
and `_vision_probe_json`
methods exist only for differential tests. They are **not Agent action APIs**:
they have no registration/claim authorization boundary. The combat probe currently
supports rule mode with normal or fallback statistics; presentation combat entities
remain pending. Do not route Agents through
these probes or use them for a capacity claim. `gameplay_ready` remains false.

Native Fog preserves line of sight, terrain bonuses, overlapping faction vision,
exploration and geometry-cache ordering. Death invalidation is consumed at the
next vision update, matching Python. Statistics retain ordinary periodic sampling
and the window's bounded multi-frame cycle, including reset partway through a
cycle. Their historical wall timestamps are injected metadata; resource cooldowns
still advance only from simulation time. The bootstrap codec also preserves
public runtime attributes attached to dataclasses, including Agent registration
metadata. Fog presentation deltas and the actual window integration are pending.

The initialization codec preserves the difference between `UnitState` enum values
and historical raw status strings, since Python's coefficient lookup distinguishes
them. It does not normalize or rebalance those rules during migration.

`step(dt)` advances the simulation clock from dt. Its optional wall timestamp is
external metadata, never the source of CD/recovery elapsed time. Clock changes
have an explicit command boundary. Invalid reset leaves the existing world intact;
valid reset starts a new epoch. Returned data belongs to Python and remains usable
after reset/close; its epoch identifies the old lifecycle. Close is idempotent and
subsequent computation on the closed instance fails.

All native operations detach from Python before acquiring the world mutex.
The mutex serializes writes and diagnostics; it is not a claim of parallel ECS
execution. Worker scheduling is R4 work. A poisoned instance fails visibly and
never resumes by constructing another world. RNG compatibility includes BLAKE2b
64-bit domain seeds, CPython integer seeding, MT state, random/getrandbits,
randbelow/randint, choice via randbelow, uniform and shuffle. The bounded
getrandbits probe supports the 0–64-bit range used by the kernel; it is not a
replacement for Python's unrestricted `random` module.

See [ordering contract](runtime-determinism.md),
[PyO3 detachment](https://pyo3.rs/v0.29.2/parallelism) and
[Bevy ECS](https://docs.rs/bevy_ecs/0.19.1/bevy_ecs/).
