# 10K / 100% moving / 30 Hz — recovery entrypoint

Updated: 2026-09-08. Owner: active Codex task. Branch: `codex/10k-30hz-volume`.

## Objective and invariants

Complete controlled-work P99 <=33.33 ms validation at 10,000 resident, 100% moving,
Fog ON, staggered seed/phase seed 42, preplanned 12-step routes, execution
pathfinding OFF, production animation + position commits + Vision ON,
realtime_defer, uncapped rendering, dynamic MiniMap units OFF, input blocked.
Do not change semantics, round gates, or count attribution-only results as release.
60 Hz is stress only. No architecture rewrite without evidence.

## Read in order

1. This file.
2. `docs/dev/10k-online-e8-volume-progress.md` (live experiment and next actions).
3. `/Users/liyang/Developer/star-lab/experiments/2026-09-10k-e8-volume/` (durable evidence).
4. E6-1/E6-2/E7 progress notes and the main roadmap for history.

## Baseline and evidence

Inherited retained runtime: `e7ba18b31870577110b591104ef8fa7b4713e43c`.
Validated sustained runtime: `9581084835633e10d80aac849925939bc59b9138` (E8-1/2/3/4).
Each local change has positive subsystem A/B/B/A evidence. Full regression: 505 passed.
Milestone: `scale-10k-100pct-30hz-sustained-e8` (local; no push/merge performed).
300s tooling: `bed4e479859c65e23bf9ce403e381fa03e596d30`.
Repeat tooling: `4ccdc4972ded1bbc2d2125f214770d27865792d0`.

| Run | Admitted seconds | Frames | Controlled avg ms | P99 ms |
| --- | ---: | ---: | ---: | ---: |
| Continuous | 305.447501 | 10240 | 28.220838 | 32.430227 |
| Repeat 1 | 65.285074 | 2389 | 25.784004 | 28.984507 |
| Repeat 2 | 65.301032 | 2342 | 26.310417 | 30.026299 |
| Repeat 3 | 65.271297 | 2336 | 26.370550 | 29.162605 |

All workload/trace guards and all 16 full 30s blocks PASS. Position and Vision
rates remain ~20000/s. Raw runs: `results/phase5-e8/20260908-083745-e8-4-gate300`
and `results/phase5-e8/20260908-143157-e8-4-gate60`. All preceding negative results,
including E8-3 300s P99 34.520ms and mixed E8-4 short tails, are archived in Lab.

Scope: PASS is for these complete sustained traces. It is not an every-frame or
every-5s-window guarantee: the 300s run's final rolling5s P99 was 34.745ms, and
repeat2's was 37.231ms. Continuous frame-body P99 is 34.033ms; the specified gate
is controlled work. Chrome remained open; no presumed interference was filtered.
No full interactive/10K online-Agent/60Hz release claim follows from this result.
Inherited tooling: `8f79795f1cfc9a843db5091f1672940614e2d0a0`.
E7 results: `results/phase5-tail-composition/chibi-144k-scale-10000/20260908-001411/`.
E7: stable UnitRender/Vision/Animation tail contributors; 311-312 samples per run;
P99 33.209/33.169/33.190 ms diagnostic only. One 36.347 ms low-command outlier.
Render batch runs=6, blit batches=4, layers=1 constant; action text misses=0.
Render count correlations are aliases, not independent corroboration.
Self-time accounting closure does not exclude scheduler/frequency effects.

## Work sequence

Completed: business-volume + dt/commit attribution -> targeted candidates ->
semantic contracts -> interleaved A/B -> sustained gate -> Lab archive.
The retained changes reduce repeated texture preparation, UI roster queries,
component-row queries and movement reference queries. Animation, commits and Fog
are not deferred. Single-thread Core ENV remains the production architecture.
Existing untracked maps, results and helper scripts must be preserved.

Next scope is the separately specified Agent data-plane phase, or a new explicit
short-window/every-frame latency requirement. Do not re-open the closed Cull or
slots hypotheses without new evidence. Do not count this as 10K online Agents.

## Resume rule

Check git status and the latest E8 note before running anything. Do not launch
concurrent performance jobs. Diagnostic instrumentation must be disabled in
production gate runs. Keep wall/CPU measurement attribution separate from
unmodified timing, and check workload rates per simulation second as well as frame.
