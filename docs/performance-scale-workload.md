# Production-path scale workload

The optional scale harness measures resident-unit movement through STAR's real
Animation, position-commit and Vision/Fog paths. It is a capacity workload, not a
normal match or an online-Agent benchmark: routes are prepared before measurement,
and execution pathfinding, movement-point accounting and gameplay input are excluded.
It is enabled only with `--scale-harness-socket`; normal startup is unchanged.

## Run a workload

From the repository root, start a visible, uncapped real-time environment:

```bash
uv run --frozen python -m rotk_env.main --skip-start --mode real_time --scenario default --players human_vs_two_ai --no-hub --seed 42 --uncapped --scale-harness-socket /tmp/star-scale.sock
```

In another terminal, prepare routes and measure a movement-density point:

```bash
uv run --frozen python tools/scale_driver.py --socket /tmp/star-scale.sock density-point --density 1.0 --phase staggered --seed 42 --phase-seed 42 --route-steps 12 --duration 20 --warmup 5 --sample-after 7 --profile /tmp/star-scale-profile.json --output /tmp/star-scale-point.json
```

`default` uses the ordinary shipped scenario, not a 10K fixture. Use a scenario
with the required resident count for a capacity experiment. The driver reports
workload guards and progress; verify them before interpreting timings. See
`tools/scale_driver.py --help` and `density-point --help` for available controls.
The socket is a local test-control interface, not the Agent protocol.

## Measurement contract

- `controlled_work_frame_ms` covers instrumented controlled work. Platform event
  handling, display presentation, pacing and full frame-body timing are separate.
- Production profiler snapshots use a rolling window of approximately 5 seconds
  with a 4096-sample cap. A snapshot taken after a long run is not that run's full
  latency distribution. Record the sample count, coverage and truncation status.
- `density-point` defaults to `realtime_defer`: a full GC safe point precedes the
  bounded critical window, automatic GC is deferred, and the previous policy is
  restored at stop, cleanup or deadline. This is not a global runtime default.
- Record exact code revision, dependency lock, hardware, scenario hash, seeds,
  window/viewport, Fog, MiniMap setting, GC policy and background load. Retain all
  admitted samples and failures. Do not run concurrent performance jobs.
- General snapshot output contains runtime profiler data. Experiment-specific
  crossing-cost correlation is now an offline STAR Lab analysis; the old
  `crossing_cost_correlation` and reply availability fields are no longer emitted.

## Regression and published evidence

Run `uv run --frozen python tools/run_performance_contracts.py` for portable
structural contracts. See [measurement and regression](performance-measurement-and-regression.md)
for metric definitions and machine-specific timing gates.

Fixtures, exploratory scripts, full traces, controlled A/B results and experiment
recovery notes live in [STAR Lab](https://github.com/star-nexus/star-lab).
The [10K E8 case](https://github.com/star-nexus/star-lab/tree/main/experiments/2026-09-10k-e8-volume)
binds results to immutable source revisions and records their scope. Its complete
sustained-trace controlled-work P99 gate is 33.33 ms; it does not establish that
all rolling 5-second windows, every frame, or 10K online Agents meet that deadline.
