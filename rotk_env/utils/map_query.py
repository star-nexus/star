"""World-aware hex queries: the board, movement blockers, occupancy, A* wrappers.

Movement invariants. This module is the single definition; `MovementSystem`,
the wire affordance (`get_faction_state.units[].reachable`), the observation
channel and the UI range overlay all read the rules from here.

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
   Occupancy follows committed `HexPosition` only. Several units, including
   opposing ones, may be in flight toward the same empty hex and end up
   co-located on it.

Consequence of 3 and 4: `reachable` and `move` are equivalent only when both
are evaluated against the same world state. A mask read from an older world
revision is a statement about that revision, not a promise about this one.
"""

from typing import Dict, List, Optional, Set, Tuple

from ..components import HexPosition, MapData, Terrain, Unit
from ..components.terrain import effect_for, movement_cost_at
from ..prefabs.config import Faction
from .hex_utils import PathFinding

Hex = Tuple[int, int]


def board_hexes(world) -> Optional[Set[Hex]]:
    """Map tile keys, or None when the world has no MapData (unbounded tests)."""
    map_data = world.get_singleton_component(MapData)
    if not map_data:
        return None
    return set(map_data.tiles)


def faction_of(world, entity: Optional[int]) -> Optional[Faction]:
    """The mover's faction, for the faction-relative blocker set.

    ``None`` means "could not be resolved", which `path_blockers` reads as
    "treat every unit as an enemy" -- the conservative fallback.
    """
    if entity is None:
        return None
    unit = world.get_component(entity, Unit)
    return unit.faction if unit else None


def unit_cells(world, *, exclude_entity: Optional[int] = None) -> Dict[Hex, Set[Faction]]:
    """Hex -> the factions standing on it, mover excluded.

    A hex may carry more than one faction: moves do not reserve their
    destination (invariant 4), so co-location is legal. Both derived sets
    (`path_blockers`, `occupied_cells`) come from this one pass, so they cannot
    disagree about where the units are.
    """
    cells: Dict[Hex, Set[Faction]] = {}
    for entity in world.query().with_all(HexPosition, Unit).entities():
        if exclude_entity is not None and entity == exclude_entity:
            continue
        pos = world.get_component(entity, HexPosition)
        if pos is None:
            continue
        unit = world.get_component(entity, Unit)
        cells.setdefault((pos.col, pos.row), set()).add(unit.faction if unit else None)
    return cells


def impassable_terrain(world) -> Set[Hex]:
    """Hexes no unit may enter: enter-cost >= 999 (water on the eval maps)."""
    blocked: Set[Hex] = set()
    map_data = world.get_singleton_component(MapData)
    if not map_data:
        return blocked
    for cell, tile_entity in map_data.tiles.items():
        terrain = world.get_component(tile_entity, Terrain)
        if terrain and effect_for(terrain.terrain_type).movement_cost >= 999:
            blocked.add(cell)
    return blocked


def _held_by_other(cells: Dict[Hex, Set[Faction]], faction: Optional[Faction]) -> Set[Hex]:
    """Hexes whose occupants are not all ``faction``. ``faction=None`` is nobody."""
    return {
        cell
        for cell, factions in cells.items()
        if any(other != faction for other in factions)
    }


def path_blockers(
    world,
    faction: Optional[Faction] = None,
    *,
    exclude_entity: Optional[int] = None,
) -> Set[Hex]:
    """Hexes the mover may not traverse: impassable terrain + enemy-held hexes.

    Friendly-held hexes are absent on purpose (invariant 2). ``faction=None``
    blocks on every unit.
    """
    return impassable_terrain(world) | _held_by_other(
        unit_cells(world, exclude_entity=exclude_entity), faction
    )


def occupied_cells(world, *, exclude_entity: Optional[int] = None) -> Set[Hex]:
    """Hexes holding at least one unit: the destination constraint, invariant 1."""
    return set(unit_cells(world, exclude_entity=exclude_entity))


def plan_hex_path(
    world,
    start: Hex,
    goal: Hex,
    *,
    mover: Optional[int] = None,
    max_cost: Optional[int] = None,
) -> List[Hex]:
    """Cheapest route ``mover`` can walk on the current board (invariant 2).

    Pure traversal: the goal only has to be reachable, not unoccupied.
    Destination legality is the caller's separate `occupied_cells` check, so a
    caller can tell "no route exists" from "someone is standing there".
    """
    return PathFinding.find_path(
        start,
        goal,
        path_blockers(world, faction_of(world, mover), exclude_entity=mover),
        max_cost,
        walkable=board_hexes(world),
        step_cost=lambda pos: movement_cost_at(world, pos),
    )


def reachable_hexes(
    world,
    start: Hex,
    movement_points: int,
    *,
    mover: Optional[int] = None,
) -> Set[Hex]:
    """Legal ``move`` destinations for ``mover``: both invariants at once.

    Path cost within budget (friendly hexes traversable at terrain cost), minus
    every hex that currently holds a unit. Occupancy and enemy cells come from
    one `unit_cells` pass so the two sets cannot disagree about where units are.
    """
    cells = unit_cells(world, exclude_entity=mover)
    blocked = impassable_terrain(world) | _held_by_other(
        cells, faction_of(world, mover)
    )
    within_budget = PathFinding.get_movement_range(
        start,
        movement_points,
        blocked,
        walkable=board_hexes(world),
        step_cost=lambda pos: movement_cost_at(world, pos),
    )
    return within_budget - set(cells)
