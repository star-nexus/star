# STARBench game rules

STARBench is a hex-grid strategy game with Wei (`wei`), Shu (`shu`) and Wu
(`wu`) factions. A match can use two or three factions. Each faction controls
units, moves across terrain and attacks opponents under fog of war.

For installation, launch commands and Agent connections, see
[using STAR and connecting Agents](integration.md).

## Winning and losing

The last faction with living units wins. A unit is eliminated when its troop
count reaches zero. If all factions are eliminated, the match is a draw.
Reaching the time limit also produces a draw, rather than ranking surviving
troops: the default limits are more than 100 turns in turn-based mode and
3600 simulation seconds in real-time mode.

Territory and home-base coordinates do not replace this elimination victory
condition. The selected scenario determines the map and starting formation.

## Turn-based and real-time play

In **turn-based** mode, factions act in turn. Units start with two action
points (AP); their AP and movement points (MP) reset when their faction's next
turn starts. Press **Space** or click **End Turn** to finish a human turn.
An Agent finishes with `end_turn`. Thinking time does not advance the board.

In **real-time** mode, factions act while the simulation continues. Units
start with one AP and recover resources over simulation time. Movement and
opponents continue while an Agent waits for a model or network response.
There is no `end_turn` action in this mode.

## Units and resources

These are the standard starting unit statistics. Terrain, troop count and
unit status can affect current combat or movement values; use the current
unit panel or Agent observation when choosing an action.

| Unit | Starting troops | Base MP | Base attack | Base defense | Attack range | Vision range |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Infantry | 100 | 4 | 10 | 10 | 1 | 2 |
| Cavalry | 100 | 6 | 14 | 6 | 1 | 3 |
| Archer | 100 | 4 | 12 | 6 | 3 | 4 |

Moving spends MP for the terrain path and does not spend AP. Attacking spends
AP and targets a living enemy within attack range. Attacks reduce troop count;
the current target and action must still be legal when the order is processed.

The default skirmish Agent actions are `move`, `attack` and `get_faction_state`,
plus `end_turn` in turn-based mode. Other actions are available to an Agent
only if the match's registration reply lists them. Human action buttons show
the actions currently available for the selected unit.

## Movement and terrain

Coordinates are hex-grid `col` / `row` values, which may be negative. Movement
cost is charged when entering each hex; the starting hex is not charged.

| Common terrain | MP to enter | Walkable | Vision bonus |
| --- | ---: | --- | ---: |
| Plain | 1 | Yes | 0 |
| Forest | 2 | Yes | 0 |
| Hill | 2 | Yes | +1 |
| Urban | 2 | Yes | 0 |
| Mountain | 3 | Yes | +2 |
| Water | — | No | 0 |

Mountains also block line of sight. Terrain can modify attack and defense.
For maps with additional terrain types, Agent observations report each visible
tile's movement cost and whether it is passable.

A destination must be on the map, passable, within the unit's current movement
budget and unoccupied when the order is accepted. Routes can pass through
friendly units at the underlying terrain cost; enemy-held hexes block routes.
Moving to the unit's current hex is not a legal move.

An accepted route is not rechecked during travel, and a move does not reserve
its destination. Two units can therefore arrive at the same hex if both orders
were accepted while it was empty. A preview describes the current state, rather
than guaranteeing that a later order will succeed.

## Fog and range previews

Faction vision is the union of its units' vision. Agents receive their own
units' details and currently visible enemies, rather than hidden enemy resources
or actions. Enemy units disappear from the current observation when they leave
vision. The desktop **Shift+1** fog toggle changes visibility for humans and
Agents together; changing it also changes the observation conditions of a match.

Blue highlights show movement previews. Gold/orange outlines show geometric
attack range; visible target markers help identify enemies in range. Unknown
blockers, remaining resources, ownership and turn permissions can still prevent
an order. For Agents, `reachable` and `attackable` describe current action
availability; see [the observation reference](observation-affordance.md).

## Controls

Click a human-controlled unit to select it. Use **M** to choose a movement target
or **A** to choose an attack target, then click the destination or enemy.

| Key | Action |
| --- | --- |
| 1 / 2 | Select infantry / cavalry |
| 3 / 4 / 5 | Select the three archer slots |
| M / A | Choose a movement / attack target |
| W / G / C / F | Desktop Wait / Garrison / Capture / Fortify |
| Space / End Turn | Finish the human turn |
| Esc | Close a modal or cancel targeting/selection |

On desktop, scroll over the map to zoom, use arrows to pan, **F1** for help and
**Tab** for statistics. Scroll over the sidebar to reach its lower controls.
In the browser, scroll to zoom, drag to pan and press **F** to fit the map;
the action buttons provide Wait, Garrison, Capture and Fortify. A spectator or
AI-slot browser link is read-only.

Offline AI slots remain static until a controller connects. The optional local
BOT is available with the Python backend; launching an offline Rust match does
not start an automated opponent.
