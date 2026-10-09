# Terrain fact encoding reuse (E11 adopted)

Default Rust instances reuse unchanged, instance-local terrain fact encodings.
The private native `_set_observation_terrain_mode("baseline")` control disables
reuse for internal regression/rollback; `"terrain_fact_reuse"` re-enables it. Invalid modes are
rejected before the native ingress invalidates any read segment. Successful
configuration clears the derived cache without changing authority revision.

Every request still performs its current authorization, Fog/map intersection,
Hex ordering, enemy scan and panel preparation. A cached fact can be used only
after reading an existing current TileInfo and comparing its coordinate, entity,
Terrain presence, terrain string and movement cost. ID zero and missing Terrain
retain the original skip behavior. Output bytes are produced by the same serde
TerrainFact encoding; passability remains `cost < 999`.

The cache holds owned strings and immutable Arc<RawValue> fragments, not live
World/Fog references or complete responses. A short Mutex preserves Runtime's
Sync contract and is released before dispatching or joining panel work. Retained
entry count is bounded by the current map size. Size changes discard the old
allocation; a new key at full capacity clears the entries. Same-size synthetic
map replacement may leave unqueried old keys until bounded replacement, but a
removed tile can never be served without a current map lookup. The current native
gameplay writes only Spatial.cells; Spatial.tiles is rebuilt at scene creation
or successful reset. This cache is not a new dynamic terrain mutation API.

Mode changes discard derived cache state. Successful reset creates a fresh,
default reuse Runtime with an empty cache; failed reset leaves the old owner unchanged. Close releases
the cache. Already returned facts/responses remain independently owned. The
cache and mode are excluded from authority export and API18/schema5.

The existing private observation profiler adds enemy/terrain phase timings,
terrain build/hit counters and encoded backing-byte summaries. These are
diagnostics, not public protocol fields. Terrain build/hit timings nest within
the terrain loop and include helper work; per-fact timers add diagnostic
overhead. Cache backing-byte aggregation is outside the loop timer, but inside
the enclosing faction timer. Normal calls have no timer reads or byte summaries.

This change does not alter star-protocol or participant Agent decoding. Formal
research evidence and adoption decisions belong to STAR Lab. The resource-valid
fixed-input native1 screen measured 11.75% less observation service time and
8.37% less request + step + presentation-extraction work. These are observation
service results, not a step, full-frame, multiround or capacity claim. See the
[adoption and evidence record](../../star-lab/experiments/2026-10-rust-observation-algorithm/README.md).
