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
Current candidate: `9581084835633e10d80aac849925939bc59b9138` (E8-1/2/3/4).
Each local change has positive subsystem A/B/B/A evidence. Full regression: 505 passed.
Sustained tooling: `94f8986280ca7c391fa45a854a62c7975cab1658`.
Three >=60s traces passed P99 32.433 / 32.442 / 32.015ms; all 30s blocks passed.
That E8-3 runtime FAILED >=300s: P99 34.520ms; no-trace late-window control also
fails. E8-4 reduces Animation ~2.1-2.6ms, but short tails are mixed. Its continuous
>=300s trace is in progress under results/phase5-e8/20260908-083745-e8-4-gate300.
If it passes, run three >=60s traces at the same SHA and fixed conditions. All
earlier evidence is packaged in STAR Lab. Final integrity/frontier remain pending.
Inherited tooling: `8f79795f1cfc9a843db5091f1672940614e2d0a0`.
E7 results: `results/phase5-tail-composition/chibi-144k-scale-10000/20260908-001411/`.
E7: stable UnitRender/Vision/Animation tail contributors; 311-312 samples per run;
P99 33.209/33.169/33.190 ms diagnostic only. One 36.347 ms low-command outlier.
Render batch runs=6, blit batches=4, layers=1 constant; action text misses=0.
Render count correlations are aliases, not independent corroboration.
Self-time accounting closure does not exclude scheduler/frequency effects.

## Work sequence

E8 business-volume + dt/commit attribution -> evidence-selected candidate ->
semantic contracts -> controlled A/B -> sustained canonical gate -> archive.
Persist source commits, commands, raw aligned series, checksums, negative findings.
No sustained milestone until long-run validation and archive complete. Existing untracked maps,
results and helper scripts predate this task and must be preserved.

## Resume rule

Check git status and the latest E8 note before running anything. Do not launch
concurrent performance jobs. Diagnostic instrumentation must be disabled in
production gate runs. Keep wall/CPU measurement attribution separate from
unmodified timing, and check workload rates per simulation second as well as frame.
