# Observations and action availability

Use `get_faction_state` to read your faction's current view. The ENV returns
facts and currently available moves/attacks; your Agent chooses the strategy.
See [Agent registration and actions](agent-protocol.md) and [game rules](game-rules.md).

## Read the current view

```python
state = await client.call("get_faction_state", {"faction": "wei"})
```

Query your registered faction. Reading another faction's view is rejected.
Read unit IDs from this match's response, rather than hard-coding them.

| Field | Meaning |
| --- | --- |
| `units` | Own units, including position, troop count, AP/MP, range and ownership |
| `units[].owner` / `commandable` | Ownership and whether the caller may command this unit |
| `units[].reachable` | Current movement destinations, as `{col, row}` objects |
| `units[].attackable` | Current attack targets, as unit IDs |
| `visible_enemy_units` | Living enemies in current vision: ID, type, position and troop count |
| `visible_terrain` | Visible hexes, including plains: type, movement cost and passability |

AP/MP values (`remaining_action_points`, `remaining_movement_points`) are the
points remaining now, rather than maximum values. Troop counts appear as
`unit_status.current_count` and `max_count`. Enemy observations do not include
private AP/MP or movement/attack availability.

With fog enabled, visibility is the union of your faction's units' vision.
The desktop **Shift+1** fog toggle changes the view for humans and Agents together.

## Select own-unit panels

The optional `unit_ids` parameter selects own-unit details and availability:

```python
state = await client.call("get_faction_state", {
    "faction": "wei", "unit_ids": controlled_unit_ids,
})
```

Omit `unit_ids` for all own units, or send `[]` for no own-unit panels.
Faction totals, visible enemies and terrain remain complete. Selection does not
change command permissions: reading a teammate's unit does not let you control it.
Invalid or cross-faction selections are rejected; dead selected units are omitted.

## Choose a movement destination

`reachable` contains sorted `{col, row}` values for destinations that meet the
current movement rules. Send one as `move.target_position`:

```python
result = await client.call("move", {
    "unit_id": unit_id, "target_position": {"col": col, "row": row},
})
```

The destination must be unoccupied, on the board and passable, and a route must
fit the remaining movement budget. Routes can traverse friendly-held hexes but
not enemy-held ones. Water is impassable. The unit's own hex is not a move.
Confusion, active movement or exhausted MP can prevent movement.

`visible_terrain[].movement_cost` is the cost to enter that hex; `passable`
indicates whether it can be entered. Common terrain costs and movement acceptance
rules are described in [game rules](game-rules.md#movement-and-terrain).

## Choose an attack target

`attackable` is a sorted list of living, currently visible enemy IDs that meet
the current attack checks, including AP and range. It contains unit IDs, not tiles:

```python
result = await client.call("attack", {
    "unit_id": attacker_id, "target_id": enemy_id,
})
```

Availability does not override ownership or turn permissions. The match's
registration reply determines which action names and parameters are allowed.

## Handle changes between observation and action

Use the latest observation and inspect every action outcome. In real-time mode,
the world continues during model/network latency. A target may have moved or a
previously empty destination may now be occupied when your order arrives.

After moving, read state again before choosing an attack. The response does not
include a strategy recommendation or an attack-after-move plan. In multi-Agent
matches, use ownership and coordinate actions with teammates.

## Image observations

The default skirmish action set does not expose `get_faction_state_vlm`.
Only call it if the match lists it as supported. An enabled image observation
contains structured state plus `frame_base64`, `frame_format` and any
`frame_error`; inspect these fields rather than assuming an image is present.

The desktop image provider returns PNG (`frame_format="png"`) using the current
global window view, rather than a separate per-Agent camera. Its current visual
version is `starbench-ui-v7`; earlier recordings may contain TGA bytes despite a
PNG label. Record visual version when comparing image-based runs.

Web currently provides structured Agent observations, without an Agent image
provider. An enabled VLM request without an image provider can return state with
null frame fields and a frame error. A browser screenshot is not an Agent
observation. The browser visual version is `starbench-web-v4`.
