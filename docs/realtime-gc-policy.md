# Realtime GC Policy

## Trigger condition

In the 5000-unit Dynamic World stress test (`density=1.0`, staggered motion, Fog ON, 20 s sustained realtime phase), CPython's automatic cyclic GC occasionally triggered a generation-2 collection while `UnitRenderSystem` was building the render-command queue.

This created rare but severe latency spikes even though the actual render workload stayed normal.

## Observed problem

With the default Python GC policy:

- normal `unit_animated_draw`: ~2 ms;
- worst `unit_animated_draw`: ~29–33 ms;
- worst GC pause inside that section: ~25–31 ms;
- generation-2 GC accounted for almost all of the pause;
- the collection reclaimed 0 objects in the observed worst frames;
- P99 frame time rose to ~49 ms and worst frames reached ~53–58 ms.

The spike was therefore not caused by texture misses, render-command amplification, Fog rebuilding, or `RenderEngine` blits. It was a stop-the-world Gen2 GC pause occurring inside the latency-critical realtime loop.

## Reproduction

Run a fresh 5000-unit environment with the default GC policy, then execute the formal 100% staggered density point with Fog ON. Inspect the slow-frame diagnostics for:

- `unit_gc_gen2_collections > 0`;
- `unit_gc_gen2_pause_ms` in the tens of milliseconds;
- `unit_gc_animated_draw_pause_ms` approximately matching the `unit_animated_draw` spike.

## Solution

STAR now supports `realtime_defer` for bounded realtime phases:

1. complete sustained-motion kickoff;
2. run one explicit full GC before the measurement epoch;
3. disable automatic cyclic GC during the realtime phase;
4. keep normal Python reference counting active;
5. restore the previous GC state at the deadline, stop, clear, or cleanup.

Enable it for a formal run with:

```bash
STAR_SCALE_GC_POLICY=realtime_defer
```

The profiler records the requested/effective policy and rejects runs where the policy did not actually take effect.

## Result and conclusion

In the same 5000-unit workload, `realtime_defer` reduced P99 from ~48.8 ms to ~25.5 ms, reduced rolling max from ~52.7 ms to ~26.6 ms, reduced max `unit_animated_draw` from ~29.4 ms to ~1.6 ms, and eliminated recorded slow frames in the measurement window.

Conclusion:

> Expensive and unpredictable maintenance work should not occur randomly inside the latency-critical realtime hot loop. Move it to explicit safe points instead.

Before making this the default runtime policy, validate long-duration memory stability with a sustained memory-soak test.
