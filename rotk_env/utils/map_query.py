"""World-aware hex queries: board set, obstacles, and A* wrappers."""

from typing import List, Optional, Set, Tuple

from ..components import HexPosition, MapData, Terrain, Unit
from ..components.terrain import effect_for, movement_cost_at
from .hex_utils import PathFinding


def board_hexes(world) -> Optional[Set[Tuple[int, int]]]:
    """Map tile keys, or None when the world has no MapData (unbounded tests)."""
    map_data = world.get_singleton_component(MapData)
    if not map_data:
        return None
    return set(map_data.tiles)


def movement_obstacles(
    world, exclude_entity: Optional[int] = None
) -> Set[Tuple[int, int]]:
    """Other units and impassable terrain (enter-cost >= 999)."""
    obstacles = set()

    for entity in world.query().with_all(HexPosition, Unit).entities():
        if exclude_entity is not None and entity == exclude_entity:
            continue
        pos = world.get_component(entity, HexPosition)
        if pos:
            obstacles.add((pos.col, pos.row))

    map_data = world.get_singleton_component(MapData)
    if map_data:
        for (q, r), tile_entity in map_data.tiles.items():
            terrain = world.get_component(tile_entity, Terrain)
            if (
                terrain
                and effect_for(terrain.terrain_type).movement_cost >= 999
            ):
                obstacles.add((q, r))

    return obstacles


def plan_hex_path(
    world,
    start: Tuple[int, int],
    goal: Tuple[int, int],
    *,
    exclude_entity: Optional[int] = None,
    max_cost: Optional[int] = None,
) -> List[Tuple[int, int]]:
    """A* on the current board: clipped, cost-aware, mover excluded."""
    return PathFinding.find_path(
        start,
        goal,
        movement_obstacles(world, exclude_entity),
        max_cost,
        walkable=board_hexes(world),
        step_cost=lambda pos: movement_cost_at(world, pos),
    )


def reachable_hexes(
    world,
    start: Tuple[int, int],
    movement_points: int,
    *,
    exclude_entity: Optional[int] = None,
) -> Set[Tuple[int, int]]:
    """Hexes enterable from ``start`` within ``movement_points``."""
    return PathFinding.get_movement_range(
        start,
        movement_points,
        movement_obstacles(world, exclude_entity),
        walkable=board_hexes(world),
        step_cost=lambda pos: movement_cost_at(world, pos),
    )
