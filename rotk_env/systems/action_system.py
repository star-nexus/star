"""
Action system - handles various unit actions (per rulebook v1.2)
"""

from framework import System, World
from ..components import (
    HexPosition,
    MovementPoints,
    UnitCount,
    UnitStatus,
    Unit,
    ActionPoints,
    MapData,
    Terrain,
    Player,
)
from ..prefabs.config import GameConfig, ActionType, UnitState, TerrainType
from ..utils.hex_utils import HexMath


class ActionSystem(System):
    """Action system - handles various unit actions"""

    def __init__(self):
        super().__init__(priority=250)

    def initialize(self, world: World) -> None:
        self.world = world

    def subscribe_events(self):
        pass

    def update(self, delta_time: float) -> None:
        pass

    def perform_move(self, entity: int, target_pos: tuple) -> bool:
        """Execute a move action"""
        action_points = self.world.get_component(entity, ActionPoints)
        movement = self.world.get_component(entity, MovementPoints)
        position = self.world.get_component(entity, HexPosition)
        unit_count = self.world.get_component(entity, UnitCount)

        if not all([action_points, movement, position, unit_count]):
            return False

        # Calculate movement cost
        movement_cost = self._calculate_movement_cost(
            (position.col, position.row), target_pos
        )

        # Check action points and movement points
        effective_movement = movement.get_effective_movement(unit_count)
        if (
            not action_points.can_perform_action(ActionType.MOVE)
            or movement_cost > effective_movement
        ):
            return False

        # Consume movement and action points
        movement.current_movement -= movement_cost
        # movement.has_moved = True  # Single-move restriction removed

        # Action point cost for movement equals terrain cost
        terrain_cost = self._get_terrain_movement_cost(target_pos)
        action_points.current_ap -= terrain_cost

        # Update position
        position.col, position.row = target_pos

        return True

    def perform_garrison(self, entity: int) -> bool:
        """Execute a garrison action"""
        action_points = self.world.get_component(entity, ActionPoints)
        position = self.world.get_component(entity, HexPosition)
        unit_count = self.world.get_component(entity, UnitCount)
        unit_status = self.world.get_component(entity, UnitStatus)

        if not all([action_points, position, unit_count, unit_status]):
            return False

        # Check if garrisoning is allowed (urban/hill tiles only)
        terrain_type = self._get_terrain_at_position((position.col, position.row))
        if terrain_type not in [TerrainType.URBAN, TerrainType.HILL]:
            return False

        # Check action points
        if not action_points.can_perform_action(ActionType.GARRISON):
            return False

        # Consume action points
        action_points.consume_ap(ActionType.GARRISON)

        # Recover 10% of lost unit count (rounded up)
        lost_count = unit_count.max_count - unit_count.current_count
        recovery = max(1, int(lost_count * 0.1))
        unit_count.current_count = min(
            unit_count.max_count, unit_count.current_count + recovery
        )

        # Status becomes normal, defense +2
        unit_status.current_status = UnitState.NORMAL
        unit_status.status_duration = 0

        # Add the defense +2 bonus here; can be implemented via a temporary component
        self._add_garrison_bonus(entity)

        # Record the garrison action to the statistics system
        statistics_system = self._get_statistics_system()
        if statistics_system:
            statistics_system.record_garrison_action(entity)

        return True

    def perform_wait(self, entity: int) -> bool:
        """Execute a wait action"""
        action_points = self.world.get_component(entity, ActionPoints)
        unit_status = self.world.get_component(entity, UnitStatus)

        if not all([action_points, unit_status]):
            return False

        # Waiting does not consume action points
        unit_status.wait_turns += 1

        # If not hit this turn, the unit gains High Morale at the start of next turn
        # This logic should be handled in the turn system

        # Waiting for 2 consecutive turns can dispel Confusion
        if (
            unit_status.wait_turns >= 2
            and unit_status.current_status == UnitState.CONFUSION
        ):
            unit_status.current_status = UnitState.NORMAL
            unit_status.status_duration = 0

        # Record the wait action to the statistics system
        statistics_system = self._get_statistics_system()
        if statistics_system:
            statistics_system.record_wait_action(entity)

        return True

    def _calculate_movement_cost(self, from_pos: tuple, to_pos: tuple) -> int:
        """Calculate movement cost"""
        # Simplified: use the movement cost of the target terrain
        return self._get_terrain_movement_cost(to_pos)

    def _get_terrain_movement_cost(self, position: tuple) -> int:
        """Get the movement cost for a terrain tile"""
        terrain_type = self._get_terrain_at_position(position)
        terrain_effect = GameConfig.TERRAIN_EFFECTS.get(terrain_type)
        return terrain_effect.movement_cost if terrain_effect else 1

    def _get_terrain_at_position(self, position: tuple) -> TerrainType:
        """Get the terrain type at a position"""
        map_data = self.world.get_singleton_component(MapData)
        if not map_data:
            return TerrainType.PLAIN

        tile_entity = map_data.tiles.get(position)
        if not tile_entity:
            return TerrainType.PLAIN

        terrain = self.world.get_component(tile_entity, Terrain)
        return terrain.terrain_type if terrain else TerrainType.PLAIN

    def _add_garrison_bonus(self, entity: int):
        """Add garrison defense bonus"""
        # A temporary defense bonus component can be added here
        # Skipped for simplicity
        pass

    def reset_turn_actions(self, faction=None):
        """Reset turn actions (called at the start of each turn)"""
        query = self.world.query().with_all(ActionPoints, MovementPoints, UnitStatus)

        for entity in query.entities():
            # If a faction is specified, only reset units belonging to that faction
            if faction is not None:
                unit = self.world.get_component(entity, Unit)
                if not unit or unit.faction != faction:
                    continue

            action_points = self.world.get_component(entity, ActionPoints)
            movement = self.world.get_component(entity, MovementPoints)
            unit_status = self.world.get_component(entity, UnitStatus)
            unit_count = self.world.get_component(entity, UnitCount)

            # Reset action points
            action_points.reset()

            # Reset movement points (accounting for unit count impact)
            if unit_count:
                movement.current_mp = movement.get_effective_movement(unit_count)
            else:
                movement.current_mp = movement.base_mp
            # movement.has_moved = False  # Single-move restriction removed

            # Handle status duration
            if unit_status.status_duration > 0:
                unit_status.status_duration -= 1
                if unit_status.status_duration <= 0:
                    unit_status.current_status = UnitState.NORMAL

            # Handle High Morale after waiting
            if unit_status.wait_turns > 0:
                # If the unit waited last turn and was not hit, grant High Morale
                # Simplified: assume waiting always grants High Morale
                unit_status.current_status = UnitState.HIGH_MORALE
                unit_status.status_duration = 1
                unit_status.wait_turns = 0

    def _get_statistics_system(self):
        """Get the statistics system"""
        for system in self.world.systems:
            if system.__class__.__name__ == "StatisticsSystem":
                return system
        return None
