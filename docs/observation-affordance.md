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
| `visible_terrain` | observation | visible tiles | type and movement cost. Why a legal hex is good, not whether it is walkable |

Fog on: vision is the union of that faction’s unit vision. Fog off (key 1): the
whole map. Human, BOT, and agents share the switch.

Enemy units do **not** carry `reachable` or `attackable`. That would be a
threat map (a strategy hint). Agents may infer enemy next-step from visible
positions and terrain.

---

## `reachable`

Not “hexes within the MP radius”. The set of `target_position` values ENV
would accept for `move` right now:

- on the board (`MapData.tiles`)
- a real path exists (`map_query.plan_hex_path` / `reachable_hexes`)
- enter-cost (terrain table) fits remaining MP
- not occupied, not impassable water
- unit is not confused / already moving / out of MP

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
- hex distance ≤ attacker `attack_range`
- `CombatSystem.can_attack(attacker, target)` is true

Shape: `[int, ...]`, sorted.

Visibility is applied by iterating the same visible-enemy set as observation.
`execute_attack` currently does not re-check fog; an agent cannot obtain a
fogged id from this payload.

---

## Snapshot only

Masks describe **now**, not after a hypothetical move. Move-then-attack is
consequence reasoning: issue `move`, then pull `get_faction_state` again, or
estimate from `attack_range` plus the new coordinate (attack range is hex
distance). ENV does not return a reachable×enemy table; that would be a 1-ply
planner.

Two friendly units may pick the same hex. The second `move` is rejected.
Sequencing is an agent problem.

---

## Invariants

1. **Mask ≡ board execute.** `reachable` is computed with `map_query.reachable_hexes`
   (the same walkable / obstacles / step-cost as `MovementSystem.move_unit`).
   `attackable` is computed with `CombatSystem.can_attack`. Do not ship a
   second pathfinder or a hex-ring “in range” flag.
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

How an agent compresses this payload (drop plains, row-encode, cache terrain)
is agent design and is scored as such. The reference client may filter; the
wire payload stays complete.
