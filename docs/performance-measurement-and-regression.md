# Performance Measurement & Regression

STAR performance checks follow one rule:

> Gate STAR-controlled work and deterministic complexity invariants; keep platform presentation/input visible but non-blocking.

## Measurement semantics

The profiler keeps the last ~5 seconds of complete frames by wall clock, not a fixed frame count. It reports target/coverage, sample count, and whether the 4096-frame hard capacity truncated the horizon.

Frame time is separated into:

```text
STAR-controlled work
  work + update + render + vision + STAR input dispatch

platform input
  SDL/Pygame event pump + queue retrieval

present
  pygame.display.flip / compositor boundary

wait
  intentional FPS limiter wait

uninstrumented
  frame-body work not covered by profiler sections
```

`active_ms` remains a compatibility field and may include platform-input stalls. Regression timing should use `controlled_work_frame_ms`.

`avg_fps` / `frame_body_fps` are the inverse of mean measured frame-body duration. `window_throughput_fps` includes inter-frame gaps across the rolling window. Raw FPS and `display_present` are not generic STAR regression gates.

Slow-frame history is epoch-scoped (`slow_frame_scope = gameplay_epoch`), while frame distributions are rolling-window scoped.

## Portable structural contracts

Run:

```bash
uv run python tools/run_performance_contracts.py
```

These deterministic tests protect validated fast paths rather than milliseconds, including profiler measurement semantics, render blit batching, one-dirty-unit Vision recomputation, incremental Fog presentation, spatial Unit culling, map overscan reuse, and opaque Terrain presentation.

## Profile contracts

Run:

```bash
uv run python tools/performance_gate.py \
  --profile /tmp/profile.json \
  --contract path/to/contract.yaml
```

Exit codes are `0` pass, `1` regression, `2` malformed profile/contract.

STAR keeps two deterministic visible-window workloads; see `docs/performance-static-window-workload.md`.

### `static-window-v1`

Protects steady-state workload shape and timing.

```text
tools/performance_contract_static_window.yaml
tools/performance_contract_static_window_reference.yaml
```

Reference timing gates:

```text
controlled_work p99       <= 3.6 ms
render_engine avg          <= 2.0 ms
render_scalar_execute avg  <= 1.6 ms
uninstrumented p99         <= 0.2 ms
```

### `one-mover-v1`

Issues one real production move at the start of the measured window to exercise Animation, HexPosition commits, Vision invalidation and Fog deltas.

```text
tools/performance_contract_one_mover.yaml
```

Three validated reference runs established:

```text
controlled_work max  3.086-3.192 ms
uninstrumented p99    0.024-0.026 ms
```

The reference gates are therefore:

```text
controlled_work max  <= 4.0 ms
uninstrumented p99    <= 0.2 ms
```

`max` is intentional for this workload: only about six movement commits occur in roughly 1100 measured frames, so the dynamic frames occupy less than one percent of the sample population and can fall outside p99.

## Interpretation rules

1. Prove workload integrity before interpreting timing.
2. Prefer work-count/complexity invariants over milliseconds when possible.
3. Use `controlled_work` for STAR timing regression.
4. Do not fail STAR regression solely because `display_present`, `platform_input`, raw FPS or visible-window throughput changed.
5. Keep pinned-host timing contracts small; add a subsystem threshold only when that subsystem is a demonstrated bottleneck.

## Validation

```bash
uv run python tools/run_performance_contracts.py
uv run pytest -q
uv run python -m compileall -q \
  framework protocol rotk_agent rotk_env performance_profiler.py tools
```
