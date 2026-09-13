# Python oracle ordering (R0)

The Rust migration uses the normalized Python runtime as its oracle. Historical
experiments before this change remain reproducible at their original tags; they
are not promised to produce the same ordered trajectories as this oracle.

`QueryBuilder.entities()` still returns a set. Use `ordered_entities()` for
simulation, observations and presentation traversal. It returns an immutable
tuple of ascending external entity IDs, cached until relevant membership changes
or explicit cache invalidation. Field writes reuse the tuple. `first()`, query
callbacks and component iterators use this order. A retained query sees updated
membership when its ordered view is requested again.

Default own-unit/enemy lists use ascending external IDs. Explicit observation
`unit_ids` retain first-occurrence request order after deduplication. Releasing
all owned units returns ascending IDs; explicit release order is preserved.
Coordinate lists use `(col, row)` order. Faction sets exposed as lists use faction
value order. Team members retain registration order and messages retain FIFO.
Available skill names use lexical order. This was a discovered omission in the
first R0 oracle: populated multi-skill sets otherwise exposed Python hash order.
The R0b follow-up fixes only this list ordering; old oracle tags remain immutable.
The R0c follow-up also sorts the legacy `observation.visible_environment` and
named `unit_observation.visible_terrain` lists by coordinates. Their contents and
the Python `visible_area` set are unchanged; old tags retain their original order.

Systems run by priority, with installation order breaking equal-priority ties.
Event listeners run in subscription order, synchronously and depth first for
nested publishes. Actions retain acceptance order. Vision dirty units and MP
spends detected at one recovery boundary use ascending IDs, sorting only active
entries. Recovery deadlines retain time order and existing bucket append order.

Pathfinding retains its existing fixed hex-neighbor order. Its heap compares
`(priority, (col, row))`; an equal-cost rediscovery does not replace the predecessor.
No movement, occupancy, combat, recovery or troop-loss rule changes here.

A reproducible run must record scenario/rules, mode/display configuration, seed,
accepted actions, each tick's dt, and external wall-time inputs. The ENV clock
advances with dt; Agent thinking uses wall time. Replays compare authoritative
state, ordered events and complete decoded responses. JSON object key order and
visual pixels are not the equality boundary. The Lab owns replay drivers and
archived evidence. Python remains the default backend during migration.
