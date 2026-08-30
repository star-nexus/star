# Observation + Affordance

This is the STARBench contract for `get_faction_state`. ENV is a **mechanics
oracle**. Agents reason over **consequences**, not deterministic legality.

Data flow:

```
ENV snapshot → get_faction_state (observation + current affordances)
            → agent-side filter (optional compression)
            → agent chooses among legal actions
            → ENV execute (same oracle)
```

`rotk_agent/core/filters.py` is one agent’s compressor. It is not part of this
contract and must not recompute legality.

---

## Principle

ENV provides complete facts plus legality checks. It does not provide
strategy-level results (who to focus, where to stand, attack-first vs
move-first).

Agents should decide:

- which unit acts
- which `reachable` hex to occupy, and why
- which `attackable` `target_id` to fire
- focus fire vs maneuver, split vs concentrate
- action order

Agents should not rediscover:

- whether water is walkable
- whether a hex is off the board
- whether a BFS path exists
- whether path cost exceeds remaining MP
- whether the current target is legal

Those are environment mechanics, not tactical intelligence.

---

## Payload

`get_faction_state` returns **observation + current action affordance**.

| Field | Kind | Whose | Meaning |
| :--- | :--- | :--- | :--- |
| `units` | observation | own Units | Full command panel (id, type, position, AP, MP, range, …) |
| `units[].reachable` | affordance | own unit | Positions where `move(unit_id, target)` succeeds on this snapshot |
| `units[].attackable` | affordance | own unit | `target_id`s where `attack(unit_id, target_id)` succeeds on this snapshot |
| `visible_enemy_units` | observation | visible enemies | id, type, position, count. No MP/AP, no masks |
| `visible_terrain` | observation | visible tiles | Every currently visible hex, **including plains**. `type`, enter-cost, `passable`. |

Fog on: vision is the union of that faction’s unit vision. Fog off (key 1): the
whole map. Human, BOT, and agents share the switch.

Own-unit AP/MP on the wire are **remaining** points this snapshot
(`remaining_action_points` / `remaining_movement_points`), not the unit’s caps.
Manpower is `unit_status.current_count` vs `max_count`.

Enemy units do **not** carry `reachable` or `attackable`. That would be a
threat map (a strategy hint). Agents may infer enemy next-step from visible
positions and terrain.

---

## Movement invariants

`move` is two orthogonal checks, not one. The definition lives in
`rotk_env/utils/map_query.py`; `MovementSystem`, this payload, the `observation`
channel and the UI range overlay all read it from there.

```text
1. Destination legality is occupancy-based.
   A move destination must be unoccupied in the world state at the moment the
   order is processed. Faction does not matter: friendly-held and enemy-held
   hexes are both illegal destinations.

2. Path traversal is faction-relative.
   Enemy-held hexes are impassable. Friendly-held hexes stay traversable at the
   enter-cost of the terrain underneath -- a friendly unit is transparent to
   pathfinding and does not change the cost of the hex it stands on.

3. Legality is checked exactly once, when the order is processed.
   An accepted move is never revalidated. The route is not re-checked while the
   unit travels, so the unit may pass through a hex another unit stepped into
   after acceptance, and may arrive at a hex that became occupied after
   acceptance.

4. Moves do not reserve their destination.
   Occupancy follows committed positions only. Several units, including
   opposing ones, may be in flight toward the same empty hex and end up
   co-located on it.
```

So a unit is never boxed in by its own line: own units cost their terrain to
walk through but cannot be stood on. Enemy units are the only dynamic
obstacle, which makes screening a real tactic and body-blocking a friendly one
impossible.

---

## `reachable`

Not “hexes within the MP radius”. The set of `target_position` values ENV
would accept for `move` at the revision this snapshot was taken:

- on the board (`MapData.tiles`)
- a route exists under invariant 2 (`map_query.plan_hex_path` / `reachable_hexes`)
- enter-cost (terrain table) of that route fits the move budget
- the hex itself holds no unit, of either faction (invariant 1)
- not impassable (`passable: false`, eval maps: `water`)
- unit is not confused / already moving / out of MP

The move budget is `MovementPoints.spendable` — `min(effective_movement,
remaining_MP)` — and is the same number the executor spends.

Standing still is **not** a legal `move` (path length &lt; 2). The unit’s
current hex is omitted.

Shape: `[{"col": int, "row": int}, ...]`, sorted, matching `move`’s
`target_position`.

Turn permission and `commandable` still apply at execute time. They are not
per-hex facts; the agent already knows whose turn it is and which units it
owns.

---

## `attackable`

`attack` takes `target_id`, not a tile. The mask is a list of unit ids, not
attack hexes.

A target is listed iff, on this snapshot:

- attacker has AP for `ATTACK`
- target is a living enemy
- target is in current vision (`visible_enemy_units`)
- hex distance ≤ attacker `attack_range` (same hex is distance 0, and is in range)
- `CombatSystem.can_attack(attacker, target)` is true

Shape: `[int, ...]`, sorted.

Visibility is applied by iterating the same visible-enemy set as observation.
`execute_attack` currently does not re-check fog; an agent cannot obtain a
fogged id from this payload.

---

## Terrain enter-cost

`visible_terrain[]` shape: `{col, row, type, movement_cost, passable}`.
`movement_cost` is the MP charged when **entering** that hex (the hex you leave
is not charged). `passable` is `false` iff the hex is an obstacle: `water` is
not a walkable “999 MP” tile.

Eval-map table (`GameConfig.TERRAIN_EFFECTS`; codes match `type` on the wire):

| `type` | Enter-cost | Passable |
| :--- | ---: | :--- |
| `plain` | 1 | yes |
| `forest` / `hill` / `urban` | 2 | yes |
| `mountain` | 3 | yes |
| `water` | — | **no** (`no_path`) |

The cost is a property of the hex, never of who is standing on it: walking
through a friendly unit parked on `forest` still costs 2, not 0 and not
impassable (invariant 2).

This table is static mechanics, the same class of fact as hex distance. An agent
that sees a `water` label and still steps there is missing the rules, not
discovering a path. Combat / vision bonuses are not on this payload and are not
move-legality facts.

---

## Snapshot only

Masks describe **now**, not after a hypothetical move. Move-then-attack is
consequence reasoning: issue `move`, then pull `get_faction_state` again, or
estimate from `attack_range` plus the new coordinate (attack range is hex
distance). ENV does not return a reachable×enemy table; that would be a 1-ply
planner.

Two units may pick the same hex. Whether the second `move` is accepted depends
only on whether that hex still holds a unit when the second order is processed
(invariant 1), and moves do not reserve their destination (invariant 4): if the
first mover has not committed the hex yet, both orders are legal and both units
end up standing on it. `reachable` is a statement about the revision it was
computed at, not a promise about the revision your order lands in. Sequencing
is an agent problem.

---

## Invariants

1. **Mask ≡ board execute, at one revision.** `reachable` is computed with
   `map_query.reachable_hexes`, `attackable` with `CombatSystem.can_attack`.
   The mask and the executor share `path_blockers`, `occupied_cells` and
   `MovementPoints.spendable`, so they cannot disagree about the same world
   state. They can disagree *across* states, because legality is judged once
   when the order is processed (invariant 3). Do not ship a second pathfinder
   or a hex-ring “in range” flag.
2. **Own units only.** No enemy masks.
3. **Do not duplicate shapes.** Per-tile `reachable` / `attackable` on
   `observation` is the old annotated-map form. The skirmish contract is
   per-own-unit lists on `get_faction_state`.

---

## What ENV will not add

| Temptation | Why not |
| :--- | :--- |
| Attackable as tiles | `attack` takes `target_id` |
| Attack-after-move for every reachable hex | 1-ply search, not an oracle |
| Enemy reachable / attackable | Threat map / strategy hint |
| Suggested hex on move failure | Mini-policy; failure *reason* is enough |

---

## Agent layer

How an agent compresses this payload is agent design and is scored as such.
The wire payload stays complete. `rotk_agent/core/filters.py` is one compressor;
it must not recompute legality.

The reference client (`--state-filter {A–F}`, default `F`) ablates channels
after ENV, not on the wire:

| Pack | `reachable` | `attackable` | `terrain` | What it tests |
| :--- | :---: | :---: | :---: | :--- |
| A | | | | Census only. Model infers legality. |
| B | ✓ | | | Move mask without attack mask or terrain. |
| C | | ✓ | | Attack mask without move mask or terrain. |
| D | ✓ | ✓ | | Both masks, no terrain. |
| E | | | ✓ | Terrain observation, no masks. Can the model apply the enter-cost table? |
| F | ✓ | ✓ | ✓ | Full observation + current affordance. |

Compact rows (not the wire):

- Own units are 12 positional columns: `id,type,col,row,current_manpower,
  max_manpower,current_AP,current_MP,attack_range,attack_power,vision,defense`.
  The decoder lives on `get_faction_state`, not in the system prompt. Packs
  with masks append `{reachable:...}` and/or `{attackable:...}`.
- Packs with terrain (E, F) keep visible **non-plain** hexes as
  `{type: [[col,row],...]}` and drop per-tile `movement_cost`. An absent
  coordinate does **not** mean the terrain changed or became plain; it may be a
  visible plain or currently unobserved.
- Because E/F drop the numeric cost, the reference system prompts include the
  enter-cost table above. Without it, Filter E asks the model to guess whether
  `water` is walkable — that is not the ablation.
- Use the latest `get_faction_state` result. Packs with both masks (D, F):
  `Move only to reachable; attack only attackable.` Packs with one mask keep
  only that half.
