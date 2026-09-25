# Native authoritative state and scoped read boundaries

R4a audit (2026-09-25), runtime source `ddb084e42e07fdb359c511b8727f888ff3a5a38b`.
This is an audit of the currently implemented command/step/import paths, not a
promise that every future component mutation is covered. See the
[benchmark GAP ledger](native-benchmark-gaps.md), especially R002.

## Ownership and consumers

| Data | Current writer | Consumers and projection responsibility |
| --- | --- | --- |
| Position, movement progress, MP/AP/SP, headcount, status, construction | Rust typed components, command/step paths | Rust rules/observations; dirty Unit columns feed Python presentation |
| Occupancy, live Unit membership, activity sets | Rust movement/death/import/removal paths | Rust movement, attack candidates and observations; no Python writes to native authority |
| Combat base attack/defense/range | Scene import; no dynamic setter in current native ingress | Rust typed `CombatStats`; Python's imported panel attributes remain valid under these ingress paths. Effective attack/defense read dynamic count/status/terrain without changing these bases |
| UnitSkills | Imported cold component; current terrain-skill handler does not mutate it | Preserve historical `success`/`result` mismatch and failed skill response; do not fix rules incidentally during migration |
| Player membership | Imported cold data plus death removal | Rust observation/turn state; explicit Player removal delta updates Python presentation |
| UnitStatistics | Rust statistics mutations in cold component | Rust statistics/settlement/observation; Python's ECS copy is not an authoritative statistics source |
| Vision/exploration | Rust typed vision and Fog updates | Rust gameplay/observations; Python renderer receives derived Fog changes, not every Unit's full Vision component |
| CombatRoll / random streams | Rust accepted combat action, in accepted action order | Rust rules/export; read-panel workers do not draw random numbers; no per-frame Python RNG/component mirror |
| Owner/commandable | Rust membership/permission commands and ordered dispatcher | Captured separately for each response on caller after read workers join |

`InitialComponents` does not mean all its data is immutable: current notable
writes include Player membership in `combat.rs` and UnitStatistics in
`statistics.rs`. Typed data overrides imported snapshots during authoritative
export. Python `WorldPresentation` is a purpose-built display cache, not a full
mutable ECS facade. Missing mirrored fields alone do not establish a gameplay
GAP: trace the actual consumer first. New writers to Combat/UnitSkills, or a new
Python consumer of authority-only fields, require explicit projection/invalidation
and differential tests. R002 therefore remains a bounded-audit risk.

## R4a read phase

`ObservationBatch::prepare_panels` reads a stable `&Runtime`, selected IDs and a
faction's immutable visible-enemy set. Each worker computes `reachable`,
`attackable`, `detailed_unit_info` and encoded Unit facts with local counters.
Those paths read components/spatial data; they do not advance clock, consume RNG,
write events or submit commands. Public faction data and authorization stay on
the caller. The existing native instance mutex serializes external operations,
and PyO3 releases the GIL during the native call.

The instance owns zero workers at threads=1 or a fixed pool at threads=2/4.
Each query with more than one uncached panel submits at most N chunks. Workers
borrow the read phase; the scope joins before returning. Results are merged in
input-chunk order, then caches and counters are updated on the caller. The caller
waits without executing worker jobs. One or zero missing panels run inline.
Different Agents are not concurrently admitted, and world systems are not
parallelized by this change.

A write ends the shared observation segment. No worker survives that segment,
reset or close. Reset builds a replacement using the existing pool and swaps
only after successful validation; bad reset retains the old world. Close drops
the pool. Encoded response facts have independent ownership, so later writes
cannot alter earlier responses.

Worker utilization can vary with scheduling. Only `parallel_panel_batches`,
`panel_tasks`, `panel_worker_threads` are scheduling diagnostics; exclude those
from cross-thread diagnostic equality, never from Agent payload comparisons.
Tests compare full Agent results, original work counts and authoritative state,
and a barrier-based core test proves simultaneous distinct worker execution.
This does not establish whole-world 30Hz capacity or justify a default change.


## R4b public facts / timing addendum (2026-09-25)

Runtime encoding source `290de0a` replaces the temporary public JSON-tree cache
with owned encoded facts created from typed enemy/terrain fields. Borrowed strings
exist only while serde encodes a fact; the cache and responses own their bytes.
Cross-faction projections therefore share base facts without retaining live
component references. Public visibility selection and all writers remain as in
the R4a audit. Tests query three factions, compare Python responses and reset to
changed headcount/terrain while retaining the earlier encoded result.

The opt-in profiler reads wall time for diagnostics only. Normal handlers create
no timer, and neither mode changes simulation time, RNG, component state or
revisions. Faction and panel phases are timed on the caller; worker scheduling
and join are included in panel elapsed time, not individually attributed. R002
remains open for future or unaudited writers/consumers.
