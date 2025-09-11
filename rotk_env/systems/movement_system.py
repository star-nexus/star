"""
Movement System - Handles unit movement end-to-end:
- pathfinding and terrain-aware cost calculation
- resource spending (action points, movement points)
- animation kickoff and fallback instant move
- tile occupancy bookkeeping
- terrain-triggered events on arrival

Designed to be deterministic and side-effect scoped to movement concerns.
"""

from typing import Set, Tuple
from framework import System, World
from ..components import (
    HexPosition,
    MovementPoints,  # 使用新的多层次资源组件
    Unit,
    UnitCount,
    ActionPoints,
    MapData,
    Terrain,
    Tile,
    MovementAnimation,
    UnitStatus,
)
from ..prefabs.config import TerrainType, ActionType
from ..utils.hex_utils import HexMath, PathFinding


class MovementSystem(System):
    """System responsible for executing unit movement."""

    def __init__(self):
        super().__init__(required_components={HexPosition, MovementPoints, Unit})

    def initialize(self, world: World) -> None:
        self.world = world

    def subscribe_events(self):
        pass

    def update(self, delta_time: float) -> None:
        """Update movement system (no-op; movement is event/command driven)."""
        pass

    def move_unit(self, entity: int, target_pos: Tuple[int, int]) -> bool:
        """Move a unit to target position (q, r)."""
        position = self.world.get_component(entity, HexPosition)
        movement_points = self.world.get_component(entity, MovementPoints)
        unit_count = self.world.get_component(entity, UnitCount)
        action_points = self.world.get_component(entity, ActionPoints)

        if not all([position, movement_points, unit_count, action_points]):
            return False

        # Prevent concurrent movement for this entity
        anim = self.world.get_component(entity, MovementAnimation)
        if anim and anim.is_moving:
            return False

        # Compute effective movement capacity (affected by unit count)
        effective_movement = movement_points.get_effective_movement(unit_count)

        # Find a valid path within movement capacity
        obstacles = self._get_obstacles()
        path = PathFinding.find_path(
            (position.col, position.row),
            target_pos,
            obstacles,
            effective_movement,
        )

        if not path or len(path) < 2:
            return False

        # Calculate total movement cost along path (terrain-aware)
        total_cost = self._calculate_total_movement_cost(path)

        if total_cost > effective_movement:
            return False

        # Check action points
        if not action_points.can_perform_action(ActionType.MOVE):
            return False

        print(f"✓ Unit {entity} moves to {target_pos}")

        # === Spend resources (multi-layer model) ===
        # 1) Spend action point (decision layer): fixed 1 AP to initiate movement
        action_points.current_ap -= 1

        # 2) Spend movement points (execution layer): terrain-based path cost
        # allow multiple moves per turn if MP/AP remain
        movement_points.current_mp -= total_cost
        # movement_points.has_moved = True  # 移除单次移动限制

        # Record movement to statistics system
        statistics_system = self._get_statistics_system()
        if statistics_system:
            from_pos = (position.col, position.row)
            statistics_system.record_movement_action(entity, from_pos, target_pos)

        # Start movement animation if available
        animation_system = self._get_animation_system()
        if animation_system:
            animation_system.start_unit_movement(entity, path)
        else:
            # No animation system: instantly move to target
            position.col, position.row = target_pos

        # Update tile occupation info
        self._update_tile_occupation(entity, target_pos)

        # Trigger terrain events on arrival
        self._trigger_terrain_events(entity, "move_end")

        return True

    def _calculate_total_movement_cost(self, path: list) -> int:
        """Sum terrain movement costs along the path."""
        total_cost = 0
        for i in range(1, len(path)):
            terrain_cost = self._get_terrain_movement_cost(path[i])
            total_cost += terrain_cost
        return total_cost

    def _get_terrain_movement_cost(self, position: Tuple[int, int]) -> int:
        """Get movement cost for the terrain at position (q, r)."""
        from ..prefabs.config import GameConfig

        terrain_type = self._get_terrain_at_position(position)
        terrain_effect = GameConfig.TERRAIN_EFFECTS.get(terrain_type)
        return terrain_effect.movement_cost if terrain_effect else 1

    def _get_terrain_at_position(self, position: Tuple[int, int]) -> TerrainType:
        """Get terrain type at position (q, r)."""
        map_data = self.world.get_singleton_component(MapData)
        if not map_data:
            return TerrainType.PLAIN

        tile_entity = map_data.tiles.get(position)
        if not tile_entity:
            return TerrainType.PLAIN

        terrain = self.world.get_component(tile_entity, Terrain)
        return terrain.terrain_type if terrain else TerrainType.PLAIN

    def _get_obstacles(self) -> Set[Tuple[int, int]]:
        """Collect coordinates that are currently blocked (units, impassable terrain)."""
        obstacles = set()

        # Add positions of other units
        for entity in self.world.query().with_all(HexPosition, Unit).entities():
            pos = self.world.get_component(entity, HexPosition)
            if pos:
                obstacles.add((pos.col, pos.row))

        # Add impassable terrain
        map_data = self.world.get_singleton_component(MapData)
        if map_data:
            for (q, r), tile_entity in map_data.tiles.items():
                terrain = self.world.get_component(tile_entity, Terrain)
                if terrain and terrain.terrain_type == TerrainType.WATER:
                    obstacles.add((q, r))

        return obstacles

    def _trigger_terrain_events(self, entity: int, action: str):
        """Trigger terrain events in RandomEventSystem for a given action."""
        # Retrieve random event system
        for system in self.world.systems:
            if system.__class__.__name__ == "RandomEventSystem":
                system.trigger_terrain_event(entity, action)
                break

    def _get_statistics_system(self):
        """Get StatisticsSystem instance if present."""
        for system in self.world.systems:
            if system.__class__.__name__ == "StatisticsSystem":
                return system
        return None

    def _get_animation_system(self):
        """Get AnimationSystem instance if present."""
        for system in self.world.systems:
            if system.__class__.__name__ == "AnimationSystem":
                return system
        return None

    def _update_tile_occupation(self, entity: int, position: Tuple[int, int]):
        """Update tile occupancy to reflect the unit's new location."""
        map_data = self.world.get_singleton_component(MapData)
        if not map_data:
            return

        # Clear previous occupancy by this entity
        for tile_entity in map_data.tiles.values():
            tile = self.world.get_component(tile_entity, Tile)
            if tile and tile.occupied_by == entity:
                tile.occupied_by = None

        # Set new occupancy
        tile_entity = map_data.tiles.get(position)
        if tile_entity:
            tile = self.world.get_component(tile_entity, Tile)
            if tile:
                tile.occupied_by = entity
