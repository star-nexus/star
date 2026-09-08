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

## E8-1 interleaved A/B/B/A — retained local improvement, gate still FAIL

A1 20260908-011343: controlled avg 33.514 / p99 36.932; UnitRender@3450cmd 9.720ms.
B1 20260908-011448: controlled avg 32.757 / p99 36.300; UnitRender@3450cmd 8.998ms.
B2 20260908-011552: controlled avg 32.828 / p99 36.301; UnitRender@3450cmd 9.057ms.
A2 20260908-011656: controlled avg 34.082 / p99 37.419; UnitRender@3450cmd 9.871ms.
All guards pass; commits and Vision ~19998..20000/s, no lost world work. Retain
E8-1 as a local render-cost improvement (~0.77ms at matched count). No release
PASS: every candidate P99 >33.33. Current 30s baseline slower/more variable than
historic E7; do not combine those observations into a false pass.

Next narrow attribution: UIRender ~2.9ms; source reveals full Unit roster traversal
per frame to count faction indicators. `ui` launcher mode adds only coarse timers
around the existing UI calls. Measure before choosing any roster-cache approach;
preserve all-Unit semantics (including no-position/dead components) and ordering.

## E8-2 UI roster attribution and candidate

UI attribution `20260908-012059-ui-attribution` on E8-1: all guards PASS;
UIRender 2.947ms, faction indicators 2.908ms. Other UI costs negligible.

Candidate preserves the original all-Unit count and faction insertion order.
World exposes per-component reference versions (add/replace/remove/destroy/reset).
UI retains at most last roster's Unit references and faction sequence. Each frame
reads all current faction fields via C-level map; unchanged sequences reuse ordered
counts. Thus in-place faction updates remain immediate; no-position/zero-count
Units remain counted. It does NOT substitute spatial living_counts or suppress UI.
Initial attempted query-result identity token was rejected in tests because World
returns copies on cache hits; no measurements used that draft. Public reference
versions now have explicit lifecycle/reset contracts, independent of unrelated
component changes. Framework + render tests: 83 passed; extra version contracts 2.
Next: exact-SHA E8-1 vs E8-1+E8-2 off-mode A/B/B/A, then sustained gate.

## E8-2 interleaved result — local KEEP, narrow 30s passes

U-A1 20260908-012630: avg 32.634 / P99 35.650.
U-B1 20260908-012734: avg 30.235 / P99 33.270.
U-B2 20260908-012837: avg 30.142 / P99 33.275.
U-A2 20260908-012942: avg 33.380 / P99 38.075.
All guards PASS. Two candidate short windows pass but only ~0.06ms headroom.
Retain exact all-Unit roster reuse as E8-2; sustained validation remains required.

## E8-3 reference-row lookup candidate (not yet measured/retained)

8ms Animation still loops 10K units and individually resolves HexPosition and
MovementAnimation through repeated entity-row dictionary lookups. Candidate:
World.get_component removes duplicate membership+getitem row lookup; new
get_component_pair coalesces two current references; Animation uses it when
available, preserving adapter fallback and exact iteration/commit semantics.
This is a narrow API addition, not storage/ECS redesign. A tiny interleaved warm
lookup probe showed ~0.91 ->0.79ms per 20K get_component calls; that only justifies
live A/B, not any frame saving claim. Relevant framework/lifecycle/movement tests
must pass, then E8-2 vs E8-3 exact-SHA A/B/B/A decides retention.

## Sustained recorder design

Keep production profiler's 5s rolling window and 4096 capacity unchanged. A
bounded experiment-only recorder copies already-completed frame samples after
profiler finalization, with capacity 20,000 and overflow guard. No section/system
timers are added; no JSON writes during the run. Final snapshot exports all
samples. This avoids inflating the production profiler's per-frame percentile
sorting work to a multi-minute window. Gate analysis excludes startup warmup,
uses all admitted frames, and reports chronological blocks and breach runs.

## E8-3 interleaved result and sustained validation in progress

Exact A=cdd3788e29ff3856059d767e8e18dd3fdcf3098e;
B=88b19fe92957ee660f50cc366c5a737cb2dc8ca8.
R-A1 20260908-013438: avg 28.126 / P99 30.144 / Animation 7.305ms.
R-B1 20260908-013542: avg 27.739 / P99 32.498 / Animation 6.952ms.
R-B2 20260908-013645: avg 27.687 / P99 29.824 / Animation 6.950ms.
R-A2 20260908-013747: avg 28.530 / P99 30.736 / Animation 7.441ms.
All guards PASS, ~19996..19999 position changes/s. Local KEEP: Animation and
controlled average improve within the interleaved bracket; P99 is mixed (B1 max
53.950ms). The large earlier-to-later machine-wide speed change is not attributed
to this code. Full regression: 498 passed in 4.98s, log under
results/phase5-e8/validation/regression.log.

Next: freeze tooling, three 60s admitted traces and one 300s admitted trace on
88b19fe, diagnostic mode off, production profiler 5s/4096. Fixed first 10s of trace
excluded; all remaining samples included. Check per-frame invariants, full trace
coverage, aggregate P99, 30s chronological blocks, breach rates and world-work
rates. Do not treat the final rolling 5s snapshot as the sustained result.

## Three sustained repeats PASS; long run in progress

Tooling 94f8986280ca7c391fa45a854a62c7975cab1658, runtime 88b19fe.
Run: results/phase5-e8/20260908-081025-gate60. Fixed first 10s exclusion leaves
65.310 / 65.290 / 65.323 seconds (2152 / 2100 / 2121 samples); driver includes
its initial warmup in the trace, so admitted coverage exceeds the 60s minimum.
P99: 32.433365 / 32.441656 / 32.015066ms. All driver and admitted-frame guards
PASS; all complete 30s blocks PASS. Position/Vision rates ~20000/s.
Observed breach fractions .604% / .571% / .236%; P99 gate allows individual
misses. Frame-body P99 33.971 / 33.950 / 33.493ms is separately reported and
does not meet the controlled-work budget. Repeat 1 descriptive block-bootstrap
upper bound is 34.09ms, so this is repeated empirical passage, not a statistical
guarantee for all future windows. Next continuous 300s run is already started:
results/phase5-e8/20260908-081510-gate300, same runtime/tooling and conditions.

## Continuous 300s FAIL — do not close the gate

305.466s / 9459 samples, all workload guards PASS. Avg 30.694ms, P99 34.520437ms;
380 breaches (4.017%), longest 17 frames. Later 30s blocks progressively slower:
first avg29.499 / last31.395ms; commands alternate ~3523/~3444 each 30s throughout.
Animation7.776->8.646ms, Vision3.346->3.620ms, Unit9.001->9.397ms; UI~.384ms stable.
This is not explained by growing visible count. Position/Vision throughput remains
~20000/s; per-frame commits rise as frames slow. Causes of long-run drift are not
yet established. Next: no-history-recorder long-run control to check observer
effect; evaluate reuse of live movement component references using E8-2 version
contracts, with immediate invalidation after synchronous commit callbacks. Preserve
the failed sustained trace as formal negative evidence. No frontier promotion.

## Observer control and E8-4 candidate

20260908-082342-long-no-trace-control: same 88b19fe runtime, 310s before snapshot,
history recorder OFF. Final 5s avg32.406/P99 35.724ms, all guards PASS. This is
not a full-trace gate, but shows late slowdown also occurs without history
retention (trace-enabled final5s avg32.274/P99 34.308). No exclusive observer
explanation and no quantified randomization-based overhead claim.

E8-4 candidate caches (entity, HexPosition, MovementAnimation) references under
the public per-component reference versions, bounded by last movement roster.
Live fields remain authoritative; after every movement commit callback, version
changes force subsequent entries to resolve components live against the original
entity snapshot. Next frame rebuilds. Missing version API retains original query
and lookup path. No work is delayed. Differential remove/replace/destroy/add/reset
callback tests, in-place updates and world reuse covered. Full regression 505 PASS
in 3.02s. A test draft incorrectly indexed a set; corrected to list, no runtime
failure. Next exact-SHA E8-3 vs E8-4 off-mode 30s A/B/B/A before retention.

## E8-4 A/B/B/A — local KEEP, tail requires sustained validation

A=88b19fe92957ee660f50cc366c5a737cb2dc8ca8;
B=9581084835633e10d80aac849925939bc59b9138; tooling=9581084.
M-A1 20260908-083203: avg29.172/P99 32.884/Animation7.446ms.
M-B1 20260908-083307: avg26.800/P99 29.591/Animation5.111ms.
M-B2 20260908-083411: avg27.253/P99 35.789/Animation5.348ms.
M-A2 20260908-083515: avg29.810/P99 34.873/Animation7.676ms.
All guards PASS. Clear local Animation improvement ~2.1-2.6ms, same count/rate
contracts. B2 has 18 breaches in several clusters, jointly increased MapRender,
Animation, Vision and Unit self, not an isolated roster symptom; A2 also has 29.
Do not discard B2 or claim every short window passed. ab-analysis.json preserves
machine-readable local metrics and descriptive matched-command fits for all runs.
Next validate B with one complete >=300s trace first, then three >=60s repeats if
it passes. No threshold/warmup/slow-frame filtering changes. Exact driver/tooling
manifest and all negative traces remain archived.
