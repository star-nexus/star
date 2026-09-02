# Vision Geometry Cache Working-Set Ablation

This note records the geometry-cache capacity experiment used to choose the
large-window VisionSystem default for dynamic-world scale runs.

The cache key is:

```text
(center_hex, effective_range, terrain_revision)
```

The important consequence is that cache working set is driven by the number of
distinct geometry states visited, not directly by resident unit count. Multiple
units at the same center/effective-range pair share one cached geometry.

## Why this experiment was needed

The original geometry cache was unbounded. Long-running random-motion soak tests
showed continuously growing live GC-tracked objects even though full Gen2 GC
collected zero objects. The cache was retaining every geometry ever visited.

Bounding the cache at 4096 fixed the memory-growth mode, but a later 5000-unit
steady Dynamic World run showed VisionSystem self time regressing from roughly
1.2 ms to roughly 2.9 ms. This suggested that 4096 was below the active geometry
working set and caused LRU thrashing.

The goal of the ablation was therefore not to maximize cache size. It was to find
an operational capacity large enough to cover the steady working set while
remaining explicitly bounded.

## Fixed experiment conditions

Each point used a fresh ENV process and identical workload conditions:

```text
scenario       TestMap-8K-scale-5000
map            91 x 91 = 8281 hexes
resident       5000 living units
moving         5000
execution      density 1.0
mode           real_time
phase          staggered
seed           42
target radius  12
FogOfWar       ON
camera         unchanged
zoom           0.15
GC policy      realtime_defer
warmup         5 wall-clock seconds
measurement    10 wall-clock seconds after kickoff
```

The only changed variable was:

```text
STAR_SCALE_VISION_GEOMETRY_CACHE_MAX_ENTRIES
```

with values 4096, 8192, 16384, and 32768.

The measurement adapter recorded cache counters at the execution-epoch boundary
and reported hit/miss/eviction deltas only for the formal measurement window.

## Results

| Capacity | Vision self ms | Epoch hit rate | Epoch misses | Epoch evictions | Start size | Final size | Avg frame ms | P99 frame ms |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 4096 | 2.925 | 72.39% | 19010 | 19010 | 4096 | 4096 | 22.322 | 27.117 |
| 8192 | 1.226 | 99.14% | 639 | 0 | 5000 | 5639 | 20.507 | 25.296 |
| 16384 | 1.224 | 99.14% | 639 | 0 | 5000 | 5639 | 20.453 | 24.290 |
| 32768 | 1.350 | 99.04% | 639 | 0 | 5000 | 5639 | 22.673 | 27.587 |

### 4096: below the working set

During the measurement epoch:

```text
lookups    68854
hits       49844
misses     19010
evictions  19010
hit rate   72.39%
```

With the cache already full at 4096, every epoch miss forced an eviction. This is
the expected signature of capacity thrashing:

```text
miss -> recompute LOS geometry -> insert -> evict -> later miss again
```

VisionSystem self time was approximately 2.925 ms.

### 8192: working-set threshold crossed

During the measurement epoch:

```text
lookups    74697
hits       74058
misses       639
evictions      0
hit rate   99.14%
size       5000 -> 5639
```

The cache never reached its 8192 bound. The measured steady working set for this
5000-unit run was approximately 5639 geometry entries. VisionSystem self time
returned to approximately 1.226 ms.

### 16384: headroom with no measured Vision penalty

The 16384 point produced the same cache behavior as 8192:

```text
misses       639
evictions      0
hit rate   99.14%
final size  5639
```

VisionSystem self time was approximately 1.224 ms, effectively identical to the
8192 point. This means 16384 provides additional bounded headroom without
preallocating or touching unused geometry entries.

### 32768: no cache-level benefit

The 32768 run also retained only 5639 entries and had zero evictions. Its worse
aggregate frame time coincided with several unrelated subsystems also becoming
slower in that fresh process, so the run does not support a causal claim that a
larger cache bound itself reduces performance.

The relevant cache conclusion is simply that 32768 provided no additional hit
rate or miss-rate benefit for the measured workload.

## Capacity decision

Two different values are useful to distinguish:

```text
8192  = measured minimum sufficient capacity for the current 5000-unit workload
16384 = large-window operational default with 2x headroom over that threshold
```

The scale/window default is therefore **16384**.

The shared canonical/headless VisionSystem constructor keeps its smaller default
unchanged. Scale experiments can override the window value per fresh process:

```bash
STAR_SCALE_VISION_GEOMETRY_CACHE_MAX_ENTRIES=8192
STAR_SCALE_VISION_GEOMETRY_CACHE_MAX_ENTRIES=16384
STAR_SCALE_VISION_GEOMETRY_CACHE_MAX_ENTRIES=32768
```

The capacity is an upper bound, not a preallocation. Setting the bound to 16384
does not allocate 16384 geometry entries at startup; in the 5000-unit experiment
only 5639 entries were actually retained.

## Scaling to 10K / 20K units

Do not scale this cache by resident unit count alone.

The key cardinality is controlled by:

```text
number of distinct visited centers
x
number of effective-range variants
x
active terrain revision
```

Therefore:

- more units on the same map can share the same geometry entries;
- doubling resident units does not imply doubling cache working set;
- a larger map, broader exploration, or more effective-range variants can grow
  the working set even if resident unit count stays fixed;
- terrain revision changes invalidate the cache rather than multiplying retained
  revisions indefinitely.

For future 10K and 20K scenarios, keep the cache bounded and use measured pressure
rather than a fixed unit-count multiplier. Re-run the same ablation whenever map
scale or workload distribution changes materially.

The operational signals are:

```text
geometry_cache_size / geometry_cache_capacity
geometry_hit_rate
geometry_cache_misses
evictions per measurement epoch
VisionSystem self/inclusive time
```

Interpretation:

```text
size well below capacity + zero evictions
    -> capacity is sufficient

size approaches capacity + zero/few evictions
    -> monitor; working-set headroom is shrinking

sustained evictions + falling hit rate + rising Vision latency
    -> capacity is below the workload working set
```

A practical escalation rule for larger-world experiments is:

```text
16384 default
  -> if measured steady-state evictions become non-zero and persistent,
     test 32768 in a fresh-process A/B
  -> if larger maps continue to push the bound, consider a map/workload-aware
     capacity policy rather than repeatedly hard-coding unit-count multipliers
```

This keeps the primary invariant intact:

> Vision geometry memory remains explicitly bounded, while the bound is chosen
> from measured working-set behavior rather than from resident unit count alone.
