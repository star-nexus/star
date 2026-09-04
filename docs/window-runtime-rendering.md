# Window Runtime and Rendering

STAR's interactive window uses the same authoritative ECS components and game
rules as headless execution. Window-specific systems replace repeated global
scans and transient raster work with derived, bounded state.

## Frame clock modes

Normal interactive play keeps the production 60 FPS cap and the established
fixed timestep of `1/FPS` per frame.

For throughput measurement, `--uncapped` removes the production frame limiter
and drives the full game/update/render frame with measured wall-clock delta.
This exposes actual frame capacity instead of flattening faster workloads at
60 FPS, while avoiding the incorrect behavior of advancing `1/60` seconds on
every uncapped frame. Profiler metadata reports `fps_cap=uncapped` and
`clock_mode=uncapped_wall_clock` in this mode.

`--uncapped` is a measurement clock, not a change to the default runtime policy.
Normal user launches remain capped.

## Derived unit state

`UnitSpatialIndex` is rebuilt when a window world starts and then maintained
when units commit a new hex or die. Movement, vision, unit culling, effects,
recovery, and realtime victory checks use this index where available and retain
scan-based fallbacks for worlds that do not install it.

`VisionSystem` maintains faction visibility incrementally. Position commits
enqueue affected units, cached line-of-sight geometry is bounded by an LRU, and
semantic tile transitions are published through
`FogVisibilityChangeJournal`. Fog being disabled changes presentation only;
visibility and exploration continue to advance.

## Terrain presentation

`WindowMapRenderSystem` keeps an oversized terrain raster around the viewport.
Camera movement inside that region reuses the raster and changes only the source
rectangle. Rebuilds are prepared incrementally and installed atomically.

The semantic overscan surface uses per-pixel alpha while it is assembled.
`OpaqueTerrainPresentationMixin` creates a compact opaque copy when a completed
overscan raster becomes active, avoiding repeated alpha composition for opaque
terrain.

## Fog presentation

`IncrementalFogSurfacePresenter` owns a viewport-sized semantic Fog surface.
Camera, zoom, orientation, viewport, and view-faction changes cause a canonical
full rebuild. Visibility journal deltas patch only the affected hexes and their
one-ring raster neighbors while geometry is unchanged.

Full rebuilds use the following production path:

1. reuse camera-independent world corners cached per tile;
2. transform corners with the canonical `int(round(...))` mapping;
3. accumulate screen bounds in the same loop;
4. skip geometry entirely for tiles that currently contain no Fog;
5. draw fogged polygons and retain a conservative Fog-content presentation
   rectangle.

Incremental reveals do not shrink that rectangle. Newly fogged patch tiles expand
it immediately, and the next full rebuild tightens it. The submitted rectangle
therefore always contains every non-transparent Fog pixel without changing Fog
semantics.

## Render submission

`RenderEngine` preserves layer and command order. Consecutive plain blits are
submitted through `pygame.Surface.blits`; custom drawing commands and blits
with source areas or special flags remain ordering barriers.

The optional runtime profiler reports hierarchical inclusive/self timings and
separates active work, display presentation, and FPS-cap waiting. It is disabled
unless `--profile` or `--profile-json` is supplied.
