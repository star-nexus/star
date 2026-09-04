# Deterministic Visible-Window Performance Workloads

STAR keeps two small visible-window workloads for regression measurement. Both reuse the production engine/scene stack, use `default / river_split`, seed `42`, real-time mode, 15 units, Fog enabled, Hub offline, rule BOT disabled, and blocked local gameplay input. SDL event pumping and `display_present` remain active but are not STAR timing gates.

The runner uses 12 seconds total by default: 7 seconds warm-up plus a final 5-second measurement window.

## 1. `static-window-v1`

The world remains unchanged during measurement. It protects steady-state render cost and workload shape.

```bash
uv run python tools/run_static_window_benchmark.py \
  --uncapped \
  --summary-json /tmp/static-summary.json \
  --profile-json /tmp/static-profile.json

uv run python tools/performance_gate.py \
  --profile /tmp/static-profile.json \
  --contract tools/performance_contract_static_window.yaml

uv run python tools/performance_gate.py \
  --profile /tmp/static-profile.json \
  --contract tools/performance_contract_static_window_reference.yaml
```

The reference timing contract is for the validated macOS reference environment, not portable CI. It intentionally gates only:

```text
controlled_work p99       <= 3.6 ms
render_engine avg          <= 2.0 ms
render_scalar_execute avg  <= 1.6 ms
uninstrumented p99         <= 0.2 ms
```

`uninstrumented` is a measurement-coverage guard: substantial new frame work must not appear outside profiler attribution.

## 2. `one-mover-v1`

During warm-up the harness uses production movement rules to preselect the longest legal Wei move. At the start of the measurement window it sends exactly one real `MovementSystem.move_unit()` order. The measured path therefore exercises movement order handling, Animation, committed HexPosition changes, Vision invalidation and incremental Fog updates without human timing noise.

```bash
uv run python tools/run_static_window_benchmark.py \
  --workload one-mover-v1 \
  --uncapped \
  --summary-json /tmp/one-mover-summary.json \
  --profile-json /tmp/one-mover-profile.json

uv run python tools/performance_gate.py \
  --profile /tmp/one-mover-profile.json \
  --contract tools/performance_contract_one_mover.yaml
```

The first version deliberately has no one-mover timing threshold. Run three validated profiles first; then set one reference budget only:

```text
controlled_work_frame_ms.p99 <= baseline + conservative headroom
```

No per-subsystem dynamic timing thresholds are needed unless a subsystem later becomes a demonstrated bottleneck.

## Interpretation

Use structural/integrity rules to prove the same work is being measured. Use `controlled_work` for STAR regression timing. Keep `display_present`, `platform_input`, raw FPS and visible-window throughput as attribution data only; current macOS/SDL presentation can change pacing state without a corresponding change in STAR-controlled work.
