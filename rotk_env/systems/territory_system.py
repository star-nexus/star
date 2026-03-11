"""
Territory control system - handles tile capture, fortification construction, and territory control.
"""

import time
from typing import Optional, Tuple
from framework import System, World
from ..components import (
    HexPosition,
    Unit,
    MapData,
    Tile,
    Terrain,
    TerritoryControl,
    CaptureAction,
    ActionPoints,
    ConstructionPoints,
    GameState,
    GameModeComponent,
    GameTime,
)
from ..prefabs.config import GameConfig, Faction, TerrainType, ActionType, GameMode


class TerritorySystem(System):
    """Territory control system."""

    def __init__(self):
        super().__init__(priority=250)  # runs after movement and combat

    def initialize(self, world: World) -> None:
        self.world = world
        self._initialize_territory_controls()

    def subscribe_events(self):
        """Subscribe to events."""
        pass

    def update(self, delta_time: float) -> None:
        """Update territory control system."""
        self._update_capture_actions(delta_time)
        self._check_territory_conflicts()

    def _initialize_territory_controls(self):
        """Initialize TerritoryControl components for all tiles."""
        map_data = self.world.get_singleton_component(MapData)
        if not map_data:
            return

        for position, tile_entity in map_data.tiles.items():
            if not self.world.has_component(tile_entity, TerritoryControl):
                # Get terrain info to determine capture difficulty
                terrain = self.world.get_component(tile_entity, Terrain)
                is_city = terrain and terrain.terrain_type == TerrainType.CITY

                # Cities require longer capture time
                capture_time = 10.0 if is_city else 5.0

                territory_control = TerritoryControl(
                    controlling_faction=None,
                    being_captured=False,
                    capturing_unit=None,
                    capture_progress=0.0,
                    capture_time_required=capture_time,
                    fortified=False,
                    fortification_level=0,
                    captured_time=0.0,
                    is_city=is_city,
                )

                self.world.add_component(tile_entity, territory_control)

    def _update_capture_actions(self, delta_time: float):
        """Update capture actions."""
        entities_to_remove = []

        for entity in self.world.query().with_all(CaptureAction).entities():
            capture_action = self.world.get_component(entity, CaptureAction)
            if not capture_action or capture_action.completed:
                continue

            # Check that the capturing unit still exists and is at the correct position
            capturing_unit = capture_action.capturing_unit
            if not self.world.has_entity(capturing_unit):
                entities_to_remove.append(entity)
                continue

            unit_pos = self.world.get_component(capturing_unit, HexPosition)
            if (
                not unit_pos
                or (unit_pos.col, unit_pos.row) != capture_action.target_position
            ):
                # Unit left the target position; cancel capture
                self._cancel_capture(capture_action.target_position)
                entities_to_remove.append(entity)
                continue

            # Get the target tile
            map_data = self.world.get_singleton_component(MapData)
            if not map_data:
                continue

            tile_entity = map_data.tiles.get(capture_action.target_position)
            if not tile_entity:
                entities_to_remove.append(entity)
                continue

            territory_control = self.world.get_component(tile_entity, TerritoryControl)
            if not territory_control:
                entities_to_remove.append(entity)
                continue

            # Check game mode
            game_mode_comp = self.world.get_singleton_component(GameModeComponent)
            game_mode = game_mode_comp.mode if game_mode_comp else GameMode.TURN_BASED

            if game_mode == GameMode.TURN_BASED:
                # Turn-based: capture completes immediately (AP already spent)
                if capture_action.uses_action_points:
                    self._complete_capture(
                        capture_action.target_position, capturing_unit
                    )
                    capture_action.completed = True
                    entities_to_remove.append(entity)
            else:
                # Real-time mode: capture requires time
                game_time = self.world.get_singleton_component(GameTime)
                current_time = game_time.game_elapsed_time if game_time else time.time()

                if capture_action.start_time == 0.0:
                    capture_action.start_time = current_time

                elapsed_time = current_time - capture_action.start_time
                territory_control.capture_progress = min(
                    1.0, elapsed_time / territory_control.capture_time_required
                )

                if territory_control.capture_progress >= 1.0:
                    # Capture complete
                    self._complete_capture(
                        capture_action.target_position, capturing_unit
                    )
                    capture_action.completed = True
                    entities_to_remove.append(entity)

        # Remove completed capture actions
        for entity in entities_to_remove:
            self.world.destroy_entity(entity)

    def _check_territory_conflicts(self):
        """Check territory conflicts (multiple units contesting the same tile)."""
        # More complex conflict resolution logic can be added here
        pass

    def start_capture(self, unit_entity: int, target_position: Tuple[int, int]) -> bool:
        """Begin capturing a tile."""
        unit_pos = self.world.get_component(unit_entity, HexPosition)
        unit = self.world.get_component(unit_entity, Unit)
        action_points = self.world.get_component(unit_entity, ActionPoints)

        if not unit_pos or not unit:
            return False

        # Check unit is at the target position
        if (unit_pos.col, unit_pos.row) != target_position:
            return False

        # Get target tile
        map_data = self.world.get_singleton_component(MapData)
        if not map_data:
            return False

        tile_entity = map_data.tiles.get(target_position)
        if not tile_entity:
            return False

        territory_control = self.world.get_component(tile_entity, TerritoryControl)
        if not territory_control:
            return False

        # Already controlled by own faction
        if territory_control.controlling_faction == unit.faction:
            return False

        # Already being captured
        if territory_control.being_captured:
            return False

        # Check game mode and action points
        game_mode_comp = self.world.get_singleton_component(GameModeComponent)
        game_mode = game_mode_comp.mode if game_mode_comp else GameMode.TURN_BASED

        if game_mode == GameMode.TURN_BASED:
            # Turn-based mode: check action points
            if not action_points or not action_points.can_perform_action(
                ActionType.OCCUPY
            ):
                return False

        # Create capture action
        capture_entity = self.world.create_entity()

        # AP cost (cities cost more)
        ap_cost = 2 if territory_control.is_city else 1

        capture_action = CaptureAction(
            capturing_unit=unit_entity,
            target_position=target_position,
            start_time=0.0,
            uses_action_points=(game_mode == GameMode.TURN_BASED),
            action_points_cost=ap_cost,
            completed=False,
        )

        self.world.add_component(capture_entity, capture_action)

        # Mark tile as being captured
        territory_control.being_captured = True
        territory_control.capturing_unit = unit_entity
        territory_control.capture_progress = 0.0

        # Consume action points in turn-based mode
        if game_mode == GameMode.TURN_BASED and action_points:
            action_points.consume_ap(ActionType.OCCUPY)

        print(f"🏴 {unit.faction.value} begins capturing tile {target_position}")
        return True

    def _complete_capture(self, position: Tuple[int, int], capturing_unit: int):
        """Complete tile capture."""
        map_data = self.world.get_singleton_component(MapData)
        if not map_data:
            return

        tile_entity = map_data.tiles.get(position)
        if not tile_entity:
            return

        territory_control = self.world.get_component(tile_entity, TerritoryControl)
        unit = self.world.get_component(capturing_unit, Unit)

        if not territory_control or not unit:
            return

        # Set control
        territory_control.controlling_faction = unit.faction
        territory_control.being_captured = False
        territory_control.capturing_unit = None
        territory_control.capture_progress = 1.0

        # Record capture timestamp
        game_time = self.world.get_singleton_component(GameTime)
        territory_control.captured_time = (
            game_time.game_elapsed_time if game_time else time.time()
        )

        print(f"🏁 {unit.faction.value} successfully captured tile {position}")

    def _cancel_capture(self, position: Tuple[int, int]):
        """Cancel tile capture."""
        map_data = self.world.get_singleton_component(MapData)
        if not map_data:
            return

        tile_entity = map_data.tiles.get(position)
        if not tile_entity:
            return

        territory_control = self.world.get_component(tile_entity, TerritoryControl)
        if not territory_control:
            return

        territory_control.being_captured = False
        territory_control.capturing_unit = None
        territory_control.capture_progress = 0.0

        print(f"❌ Capture of tile {position} cancelled")

    def build_fortification(
        self, unit_entity: int, target_position: Tuple[int, int]
    ) -> bool:
        """Build a fortification on a controlled tile."""
        unit = self.world.get_component(unit_entity, Unit)
        action_points = self.world.get_component(unit_entity, ActionPoints)
        construction_points = self.world.get_component(unit_entity, ConstructionPoints)

        if not unit:
            return False

        # Get target tile
        map_data = self.world.get_singleton_component(MapData)
        if not map_data:
            return False

        tile_entity = map_data.tiles.get(target_position)
        if not tile_entity:
            return False

        territory_control = self.world.get_component(tile_entity, TerritoryControl)
        if not territory_control:
            return False

        # Must be controlled by own faction
        if territory_control.controlling_faction != unit.faction:
            return False

        # Already fortified
        if territory_control.fortified:
            return False

        # Check action points and construction points
        game_mode_comp = self.world.get_singleton_component(GameModeComponent)
        game_mode = game_mode_comp.mode if game_mode_comp else GameMode.TURN_BASED

        if game_mode == GameMode.TURN_BASED:
            # Check action points (decision layer)
            if not action_points or not action_points.can_perform_action(
                ActionType.FORTIFY
            ):
                return False

            # Check construction points (execution layer)
            if not construction_points or not construction_points.can_build(1):
                return False

            # Consume resources
            action_points.consume_ap(ActionType.FORTIFY)
            construction_points.consume_construction(1)

        # Build fortification
        territory_control.fortified = True
        territory_control.fortification_level = 1  # base fortification level

        print(f"🏰 {unit.faction.value} built a fortification at {target_position}")
        return True

    def can_unit_enter_tile(
        self, unit_entity: int, target_position: Tuple[int, int]
    ) -> bool:
        """Check whether a unit can enter the target tile."""
        unit = self.world.get_component(unit_entity, Unit)
        if not unit:
            return True

        # Get target tile
        map_data = self.world.get_singleton_component(MapData)
        if not map_data:
            return True

        tile_entity = map_data.tiles.get(target_position)
        if not tile_entity:
            return True

        territory_control = self.world.get_component(tile_entity, TerritoryControl)
        if not territory_control:
            return True

        # Enemy-controlled tiles cannot be entered
        if (
            territory_control.controlling_faction
            and territory_control.controlling_faction != unit.faction
        ):
            return False

        return True

    def get_territory_defense_bonus(
        self, position: Tuple[int, int], faction: Faction
    ) -> int:
        """Get territory defense bonus."""
        map_data = self.world.get_singleton_component(MapData)
        if not map_data:
            return 0

        tile_entity = map_data.tiles.get(position)
        if not tile_entity:
            return 0

        territory_control = self.world.get_component(tile_entity, TerritoryControl)
        if not territory_control:
            return 0

        # Defense bonus only applies on own-faction territory
        if territory_control.controlling_faction != faction:
            return 0

        base_bonus = 1  # base territory defense bonus

        # Fortification bonus
        if territory_control.fortified:
            base_bonus += territory_control.fortification_level * 2

        # City bonus
        if territory_control.is_city:
            base_bonus += 2

        return base_bonus

    def get_territory_attack_bonus(
        self, position: Tuple[int, int], faction: Faction
    ) -> int:
        """Get territory attack bonus."""
        map_data = self.world.get_singleton_component(MapData)
        if not map_data:
            return 0

        tile_entity = map_data.tiles.get(position)
        if not tile_entity:
            return 0

        territory_control = self.world.get_component(tile_entity, TerritoryControl)
        if not territory_control:
            return 0

        # Attack bonus only applies on own-faction territory
        if territory_control.controlling_faction != faction:
            return 0

        base_bonus = 0

        # Fortification attack bonus
        if territory_control.fortified:
            base_bonus += territory_control.fortification_level

        # City attack bonus
        if territory_control.is_city:
            base_bonus += 1

        return base_bonus

    def get_territory_control(self, position: Tuple[int, int]) -> Optional[Faction]:
        """Get the controlling faction at the specified position."""
        map_data = self.world.get_singleton_component(MapData)
        if not map_data:
            return None

        tile_entity = map_data.tiles.get(position)
        if not tile_entity:
            return None

        territory_control = self.world.get_component(tile_entity, TerritoryControl)
        if not territory_control:
            return None

        return territory_control.controlling_faction

    def occupy_territory(
        self, unit_entity: int, target_position: Tuple[int, int]
    ) -> bool:
        """Occupy the specified tile immediately (simplified version)."""
        unit = self.world.get_component(unit_entity, Unit)
        if not unit:
            return False

        # Get target tile
        map_data = self.world.get_singleton_component(MapData)
        if not map_data:
            return False

        tile_entity = map_data.tiles.get(target_position)
        if not tile_entity:
            return False

        territory_control = self.world.get_component(tile_entity, TerritoryControl)
        if not territory_control:
            return False

        # Already controlled by own faction
        if territory_control.controlling_faction == unit.faction:
            return False

        # Directly set control (simplified)
        territory_control.controlling_faction = unit.faction
        territory_control.being_captured = False
        territory_control.capturing_unit = None
        territory_control.capture_progress = 1.0

        # Record capture timestamp
        game_time = self.world.get_singleton_component(GameTime)
        territory_control.captured_time = (
            game_time.game_elapsed_time if game_time else time.time()
        )

        print(f"🏁 {unit.faction.value} instantly occupied tile {target_position}")
        return True
