# E8 — render work volume and dt/commit attribution

Date: 2026-09-08. Status: DESIGN / IMPLEMENTING. Retained runtime: e7ba18b31870577110b591104ef8fa7b4713e43c.
Recovery entrypoint: `docs/dev/10k-online-resume.md`.

## Preregistered questions

1. Is command uplift explained by visible count, animated/static split, groups,
   or commands per object? Count command provenance by branch, preserve ordering.
2. Does dt explain commits and Vision dirty counts? Inspect timeline and lagged
   relationships after accounting for simulation phase/trend, not just Pearson.
3. At matched volume, is the residual CPU cost elevated or is there off-CPU delay?
4. Which exact path is worth an equivalent production optimization?

## Instrumentation boundary

Reuse PerformanceProfiler aligned deques. Experiment-only launcher/patch; aggregate
inside existing loops, no per-entity timer. Export full aligned series at snapshot,
never write traces inside timed loops. Record visible, animated/static, groups,
unit-command attribution, animation updates/completions/commits, dt, simulation
clock, existing Vision metrics, and coarse wall/thread CPU timers. Counters are
not used to alter scheduling, visibility, state or rendering. Compare diagnostics
with instrumentation-off runs; diagnostic timings cannot establish a frontier.

## Experimental stages

- Short smoke and contract tests first.
- Three original-workload diagnostic repeats; 30+ seconds retained series with
  sufficient capacity; separate sustained gate runs after candidate selection.
- Counts must reconcile with emitted commands and actual committed positions.
- Report full-series trend and phase behavior, volume-conditioned cost, cross-repeat
  model residuals, and low-volume slow frames separately.
- Select a narrow candidate only with measured attribution. Keep/reject via
  interleaved A/B and exact semantic regression, not headline P99 alone.

## Current source findings (not measured root cause)

Animation `_update_movement_animations` consumes speed*dt with a while loop for
all complete segments. `window_render_systems_base._render_units_batch` classifies
visible entities: any animation displacement gets individual fast drawing; other
entities are grouped by committed hex. Actual draw-path counts remain to measure.

## Next action

Implement experiment-only instrumentation and tests, freeze a tooling commit,
run smoke, then diagnostic repeats. Keep durable notes synchronized in STAR Lab.
