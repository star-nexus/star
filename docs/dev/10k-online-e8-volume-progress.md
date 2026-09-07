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

## Checkpoint 00:59 — smoke passed, formal diagnostics running

Tooling: `0838ce6` (launcher+contracts initially `b3a250f`). 27 targeted tests pass.
Smoke (diagnostic/disposable, not release): `results/phase5-e8/20260908-005643-smoke/`.
Every visible unit animated; static/group zero; exactly one unit command per
animated unit. Visible first/last quarter ~3129/3829. Unit inclusive cost versus
visible count R2=.929; first-difference controlled/count r=.043. Commit rate
19999.8/s simulation. Classification ~4.125ms and animated draw ~3.308ms are both
volume-dependent. Instrumentation overhead/timing not admitted as production.

Active formal command:
`uv run --frozen python tools/run_phase5_e8.py --window 30 --repeats 3 --label volume`
Results: `results/phase5-e8/20260908-005838-volume/`.
Next: analyze all repeats, select precise render-path candidate, test equivalence,
freeze candidate SHA and interleave off-mode A/B. No production candidate yet.

## Candidate selection criteria

If the three longer repeats confirm one textured blit per visible animated unit,
first candidate: frame-scoped reuse of immutable fast-render texture/size metadata.
Retain per-unit position, health, painter order, missing-component behavior, and
rich-path behavior. Clear cache in finally; lifetime <= one synchronous batch;
no entity/history cache. Compare exact command payload and raster output at
negative/fractional coordinates, odd/even texture dimensions, multiple zooms,
health/fallback paths, and across resource changes between frames. This targets
~3.3ms animated draw setup measured by the smoke; no claim of savings yet.

## E8 attribution result and E8-1 candidate — 01:05

Formal diagnostic run 20260908-005838-volume, three 30s windows, all guards PASS.
All 2,510 frames reconcile visible=animated=unit_commands, static/group=0.
Visible range approximately 2873..3903. No command amplification or static group
fragmentation. Full-series visible/control r=.651/.821/.602 (lower than E7 short
window); first differences .046/.093/-.026. Thus E7 is partly phase/trend selected,
not proof that independent movement bursts explain all tails.
Commit/simulation-second: 19999.59/19999.75/20000.06. dt/commit r=.728/.689/.667;
normalizing by dt leaves ~1.6-2% conditional uplift. CPU vs wall gaps at three
systems are small; residual CPU-cost tails remain, not proven allocator/cache root.
Unit inclusive cost vs visible R2=.79/.90/.80. Classification ~1.2-1.3us/visible,
animated draw ~0.92-1.02us/unit. No release/frontier conclusion from diagnostics.

E8-1 candidate implemented in optimized_render_systems.py: one synchronous batch
owns a texture/half-size lookup, cleared in finally. Per-unit current position,
health, fallback, missing components and command order remain unchanged. No
cross-frame stale-state cache or authoritative work deferral. Initial 39 targeted
contracts passed including exact RGBA raster equality (odd/even dimensions,
negative/fractional positions, health bars, fallback), exception cleanup and
resource replacement between frames. Candidate is NOT YET RETAINED.

Next experiment: instrumentation-off A/B/B/A, 30s complete windows, same scene,
seed/density/routes. Primary candidate signal: reduced UnitRender cost at matched
render count. Keep only with controlled-work improvement, unchanged rates/guards,
no material local regression, followed by longer canonical validation.
