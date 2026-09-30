# E2 — Statistics current-batch internal parallelism

2026-10-01. Progress: `serial split █ | attribution █ | scoped compute █ | equivalence █ | net/crossover █ | live capacity █ | raw re-audit █`.
Target5000 Units/1000 Agents;5000 Agents paused. Default Python/native threads=1.

Statistics observations now gather narrow borrowed facts for only the scheduled
batch, compute owned history records, then commit every component insertion,
observation patch and history append in original ID/ordinal order. No world
snapshot or prior-history copy enters workers. Existing instance ReadPool is
shared with observation work under the same admission mutex; no extra global pool
or workers are created. Scope joins before any write, step return, reset or close.

With configured native2/4workers, batches with at least128 actual candidate rows
use bounded chunks. Empty/tiny/tail batches stay inline. Statistics window batch
size/cycle/sampling/history limits are unchanged. Missing/stale IDs are skipped;
imported duplicate IDs retain serial patch semantics. Gathering stops at the first
zero-max-count row; ordered Result commits preserve the exact successful prefix,
clock/global-time writes, missing-component insertion and cycle/error state. Later
Systems still stop at the same first error. RNG, observations and action order do
not depend on worker completion. Visibility/faction phases and trim remain serial.

## Evidence and limits

Serial checkpoint44c3696814b82d7c9d92a83ef7d160ef462168af; experimental dispatch
checkpoint7ab0ac1d97f5d68b8d81c505fa505a1cb234a56c. Independent P0 binary remains
c058d75c0ad67a7c340c2a6ac74a9d5bc2888adf / extension
a73c477263d792cd0c4f71e3ab6001a36223cf0afd7136f8e8975f16b584731f.
Selected runtime checkpoint **2bc57d5f2241a578f61d71bb5774e7063a03ec25**;
selected extension **23dc7e4f5425e855a780a802d889f13bd28f300577688e66378ab574b7712d55**.
Old/candidate1/2/4 agree on all40994 recorded requests/9880ticks/9880full deltas,
complete response stream and final state.36synthetic scenarios/174steps also agree
in full state, errors, one-shot deltas and resets with the independent old binary.
Twenty complete trace runs and eight complete contract variants were re-audited
from the canonical raw archive. Normal selected step1/2/4 also passes;2291Python
tests,4Rust contracts,fmt/Clippy/release pass, including concurrent mixed instances.

In serial diagnostic nonempty observation ticks,125rows average: health arithmetic
0.151µs, JSON construction154.005µs, gather22.220µs, ordered commit21.301µs,
trim107.958µs. Recorded warmup is included; these are paired headless diagnostic
times, not live or isolated CPU speedup. JSON building is the parallel leaf.

Three independent same-binary/same-thread complete-step inline-vs128 controls show
mean gains4.18–16.76% at2workers and7.58–10.36% at4, with lower P99 in each pair.
All slow samples are retained; no max-latency guarantee follows. Synthetic
alternating complete-step controls with259resident entities/steady10000history
show1–32row losses, small64row gains and more128row headroom.64 is the measured
mean-positive point on this one machine;128 is the conservative operational cutoff.
Neither number promises a universal crossover across hardware/payloads. Product
does not change batch size or scan all residents to fill workers.

Three actual Cocoa2480×1239 windows, each30s warmup+300s measurement, pass the
canonical5000Units/1000Agents/30Hz frame/queue/load/clock gates with native4.
Frame P99:28.283/28.643/28.631ms; world Hz:29.997/29.993/30.000.
Observation response P99:43.347/45.531/44.518ms; action queue P99:33.508/35.489/34.070ms.
All slow frames remain: max91.923/102.449/32.239ms, worst rolling5s P99
39.837/76.037/31.794ms. Whole300s gates do not guarantee every frame/short window.
Alive minimum5000; peak movers180/173/173. Fixed-trace step gains do not imply
whole-frame causation or a larger capacity Frontier. R4e native1 evidence remains
valid; native4 is explicit configuration. Hub/realLLM/high-density and5000Agents
are unvalidated. G008/G009 remain OPEN; R001/R002 remain RISK; no new confirmed
gameplay GAP. No forced worker-panic fault-injection claim follows.

## Diagnostics / language boundary

Private `_step_profile_json` adds a per-call `statistics` breakdown. Ordinary step
has no diagnostic timer reads. Worker compute/record durations are sums across
chunks; `kernel_wall_ns` is caller wall time. `dispatch_residual_ns` subtracts the
largest chunk duration and also includes join/merge/timer bookkeeping; it is not
pure scheduling cost. Pool batch/job/observed-worker counts prove execution only.

Private advancing `_statistics_step_json(dt,wall_time,min_rows,profile=True)`
overrides dispatch for that call only; False returns JSON null and avoids profiling.
It is not a dry run and its timing/threshold never persists into authoritative
state. API18/schema5/oracle unchanged; use exact source/wheel hash to identify
additive diagnostic bindings. Python SDK/config/UI/network/strategies remain Python.

Lab package: `/Users/liyang/Developer/star-lab/experiments/2026-09-rust-statistics-compute/`.
E1 [dependency/design roadmap](native-ecs-parallel-design.md) remains the next-route
reference. No between-System scheduler was introduced by E2.
