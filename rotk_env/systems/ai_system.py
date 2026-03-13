"""
AI system - handles AI player decisions (rules manual v1.2).
"""

import random
from typing import Set, List, Tuple, Optional
from framework import System, World
from ..components import (
    Player,
    AIControlled,
    Unit,
    HexPosition,
    MovementPoints,
    Combat,
    UnitCount,
    UnitStatus,
    GameState,
    MapData,
    Terrain,
    GameModeComponent,
    ActionPoints,
)
from ..prefabs.config import GameConfig, TerrainType, ActionType
from ..utils.hex_utils import HexMath, PathFinding


class AISystem(System):
    """AI system - handles AI player decisions."""

    def __init__(self):
        super().__init__(required_components={Player, AIControlled})
        self.decision_timer = 0.0
        self.decision_interval = 1.0  # AI decision interval (seconds)
        self.debug_timer = 0.0  # For debug output
        self.debug_interval = 5.0  # Print debug info every 5 seconds
        self.unit_last_action = {}  # Unit -> last action timestamp

    def initialize(self, world: World) -> None:
        """Initialize the AI system."""
        self.world = world

    def subscribe_events(self):
        pass

    def update(self, delta_time: float) -> None:
        """Update the AI system."""
        game_state = self.world.get_singleton_component(GameState)
        game_mode = self.world.get_singleton_component(GameModeComponent)

        if not game_state or game_state.game_over or game_state.paused:
            return

        # Determine game mode
        is_realtime = game_mode and game_mode.is_real_time()

        self.decision_timer += delta_time
        self.debug_timer += delta_time

        # In real-time mode, AI makes decisions more frequently.
        decision_interval = 0.3 if is_realtime else self.decision_interval

        if self.decision_timer >= decision_interval:
            if is_realtime:
                # Real-time: all AI players act concurrently
                self._make_realtime_ai_decisions()
            else:
                # Turn-based: only the current player acts
                current_player = self._get_current_player()
                if current_player:
                    ai_controlled = self.world.get_component(
                        current_player, AIControlled
                    )
                    if ai_controlled:
                        self._make_ai_decisions(current_player)

            self.decision_timer = 0.0

        # Debug output
        if is_realtime and self.debug_timer >= self.debug_interval:
            self._debug_ai_status()
            self.debug_timer = 0.0

    def _get_current_player(self) -> Optional[int]:
        """Get current player entity id."""
        game_state = self.world.get_singleton_component(GameState)
        if not game_state or not game_state.current_player:
            return None

        for entity in self.world.query().with_component(Player).entities():
            player = self.world.get_component(entity, Player)
            if player and player.faction == game_state.current_player:
                return entity

        return None

    def _make_ai_decisions(self, player_entity: int):
        """AI decision logic."""
        player = self.world.get_component(player_entity, Player)
        if not player:
            return

        # Collect all AI-controlled units
        ai_units = []
        for unit_entity in player.units:
            if self.world.has_component(unit_entity, Unit):
                unit_count = self.world.get_component(unit_entity, UnitCount)
                # Only consider units that are still alive (headcount > 0)
                if unit_count and unit_count.current_count > 0:
                    ai_units.append(unit_entity)

        if not ai_units:
            # No valid units remain; end the turn.
            self._end_ai_turn()
            return

        # Plan actions per unit
        actions_taken = 0
        for unit_entity in ai_units:
            if self._execute_unit_strategy(unit_entity):
                actions_taken += 1

        # If no actions were taken (or all units are exhausted), end the turn.
        if actions_taken == 0 or self._all_units_exhausted(ai_units):
            self._end_ai_turn()

    def _execute_unit_strategy(self, unit_entity: int) -> bool:
        """Execute one unit's strategy."""
        import time

        action_points = self.world.get_component(unit_entity, ActionPoints)
        movement = self.world.get_component(unit_entity, MovementPoints)
        combat = self.world.get_component(unit_entity, Combat)
        unit_count = self.world.get_component(unit_entity, UnitCount)
        game_mode = self.world.get_singleton_component(GameModeComponent)

        # Ensure the unit is alive (headcount > 0)
        if not unit_count or unit_count.current_count <= 0:
            return False

        # Skip decimated units (headcount <= 10%)
        if unit_count.is_decimated():
            return False

        # Check action points
        if not action_points or action_points.current_ap <= 0:
            return False

        # Add per-unit cooldown in real-time mode
        is_realtime = game_mode and game_mode.is_real_time()
        if is_realtime:
            current_time = time.time()
            last_action_time = self.unit_last_action.get(unit_entity, 0)

            # Each unit must wait at least 1 second between actions.
            if current_time - last_action_time < 1.0:
                return False

            can_move = movement and movement.current_mp > 0
            can_attack = combat and not combat.has_attacked
            if not can_move and not can_attack:
                return False
        else:
            # Turn-based: check whether the unit has already moved and attacked.
            if (movement and movement.has_moved) and (combat and combat.has_attacked):
                return False

        # Record action time
        if is_realtime:
            self.unit_last_action[unit_entity] = time.time()

        # Find nearest enemy
        enemy_target = self._find_nearest_enemy(unit_entity)
        if enemy_target:
            # Compute distance to enemy
            attacker_pos = self.world.get_component(unit_entity, HexPosition)
            target_pos = self.world.get_component(enemy_target, HexPosition)

            if attacker_pos and target_pos:
                distance = HexMath.hex_distance(
                    (attacker_pos.col, attacker_pos.row),
                    (target_pos.col, target_pos.row),
                )

                # Priority 1: attack if within range
                if (
                    combat
                    and not combat.has_attacked
                    and action_points.can_perform_action(ActionType.ATTACK)
                    and distance <= combat.attack_range
                ):
                    if self._try_attack(unit_entity, enemy_target):
                        return True

                # Priority 2: at mid distance (2-3 tiles), prefer defensive actions (capture/fortify, etc.)
                if 2 <= distance <= 3:
                    if self._execute_defensive_strategy(unit_entity):
                        return True

                # Priority 3: if far away, move closer
                if (
                    movement
                    and action_points.can_perform_action(ActionType.MOVE)
                    and distance > 1
                    and (
                        (is_realtime and movement.current_mp > 0)
                        or (not is_realtime and not movement.has_moved)
                    )
                ):
                    if self._move_towards_enemy(unit_entity, enemy_target):
                        return True

        # No enemy found: fall back to defensive strategy
        return self._execute_defensive_strategy(unit_entity)

    def _find_nearest_enemy(self, unit_entity: int) -> Optional[int]:
        """Find the nearest enemy unit."""
        unit = self.world.get_component(unit_entity, Unit)
        position = self.world.get_component(unit_entity, HexPosition)

        if not unit or not position:
            return None

        nearest_enemy = None
        min_distance = float("inf")

        for entity in (
            self.world.query().with_all(Unit, HexPosition, UnitCount).entities()
        ):
            enemy_unit = self.world.get_component(entity, Unit)
            enemy_pos = self.world.get_component(entity, HexPosition)
            enemy_count = self.world.get_component(entity, UnitCount)

            if (
                enemy_unit
                and enemy_pos
                and enemy_count
                and enemy_unit.faction != unit.faction
                and enemy_count.current_count > 0
            ):

                distance = HexMath.hex_distance(
                    (position.col, position.row), (enemy_pos.col, enemy_pos.row)
                )

                if distance < min_distance:
                    min_distance = distance
                    nearest_enemy = entity

        return nearest_enemy

    def _try_attack(self, attacker_entity: int, target_entity: int) -> bool:
        """Try to attack a target."""
        # Check attack range
        attacker_pos = self.world.get_component(attacker_entity, HexPosition)
        target_pos = self.world.get_component(target_entity, HexPosition)
        combat = self.world.get_component(attacker_entity, Combat)

        if not attacker_pos or not target_pos or not combat:
            return False

        distance = HexMath.hex_distance(
            (attacker_pos.col, attacker_pos.row), (target_pos.col, target_pos.row)
        )

        if distance <= combat.attack_range:
            # Execute attack (delegate to combat system)
            combat_system = self._get_combat_system()
            if combat_system:
                return combat_system.attack(attacker_entity, target_entity)

        return False

    def _move_towards_enemy(self, unit_entity: int, enemy_entity: int) -> bool:
        """Move closer to an enemy."""
        position = self.world.get_component(unit_entity, HexPosition)
        enemy_pos = self.world.get_component(enemy_entity, HexPosition)
        movement = self.world.get_component(unit_entity, MovementPoints)
        unit_count = self.world.get_component(unit_entity, UnitCount)

        if not all([position, enemy_pos, movement, unit_count]):
            return False

        # Compute effective movement range
        effective_movement = movement.get_effective_movement(unit_count)
        current_pos = (position.col, position.row)
        enemy_target_pos = (enemy_pos.col, enemy_pos.row)

        # Reachable positions with terrain movement costs
        reachable_positions = self._get_reachable_positions_with_terrain_cost(
            current_pos, effective_movement
        )

        if not reachable_positions:
            return False

        # Pick the best move position (closest to the enemy)
        best_pos = None
        best_distance = float("inf")

        for pos, cost in reachable_positions.items():
            if pos == current_pos:
                continue

            distance = HexMath.hex_distance(pos, enemy_target_pos)
            if distance < best_distance:
                best_distance = distance
                best_pos = pos

        if best_pos:
            # Execute move
            movement_system = self._get_movement_system()
            if movement_system:
                return movement_system.move_unit(unit_entity, best_pos)

        return False

    def _execute_defensive_strategy(self, unit_entity: int) -> bool:
        """Execute defensive strategy."""
        position = self.world.get_component(unit_entity, HexPosition)
        movement = self.world.get_component(unit_entity, MovementPoints)
        action_points = self.world.get_component(unit_entity, ActionPoints)
        game_mode = self.world.get_singleton_component(GameModeComponent)

        if not all([position, movement, action_points]):
            return False

        is_realtime = game_mode and game_mode.is_real_time()

        # Priority 1: capture important tiles (cities or neutral tiles)
        if action_points.can_perform_action(ActionType.OCCUPY):
            if self._try_occupy_territory(unit_entity):
                return True

        # Priority 2: build fortifications (if controlled and not yet fortified)
        if action_points.can_perform_action(ActionType.FORTIFY):
            if self._try_build_fortification(unit_entity):
                return True

        # Priority 3: garrison (if appropriate)
        if action_points.can_perform_action(ActionType.GARRISON):
            action_system = self._get_action_system()
            if action_system and action_system.perform_garrison(unit_entity):
                return True

        # Priority 4: reposition to better defensive terrain (lower frequency in real-time)
        should_move = False
        if is_realtime:
            # Real-time: only move when movement is sufficiently available to avoid jitter.
            should_move = (
                movement.current_mp >= movement.max_mp * 0.8 and not movement.has_moved
            )
        else:
            # Turn-based: original logic
            should_move = not movement.has_moved

        if should_move and action_points.can_perform_action(ActionType.MOVE):
            best_terrain_pos = self._find_best_defensive_terrain(unit_entity)
            if best_terrain_pos and best_terrain_pos != (position.col, position.row):
                movement_system = self._get_movement_system()
                if movement_system:
                    return movement_system.move_unit(unit_entity, best_terrain_pos)

        # Last resort: wait
        if action_points.can_perform_action(ActionType.REST):
            action_system = self._get_action_system()
            if action_system and action_system.perform_wait(unit_entity):
                return True

        return False

    def _find_best_defensive_terrain(
        self, unit_entity: int
    ) -> Optional[Tuple[int, int]]:
        """Find best defensive terrain within reach."""
        position = self.world.get_component(unit_entity, HexPosition)
        movement = self.world.get_component(unit_entity, MovementPoints)
        unit_count = self.world.get_component(unit_entity, UnitCount)
        unit = self.world.get_component(unit_entity, Unit)

        if not all([position, movement, unit_count, unit]):
            return None

        effective_movement = movement.get_effective_movement(unit_count)
        current_pos = (position.col, position.row)

        # Reachable positions with terrain movement costs
        reachable_positions = self._get_reachable_positions_with_terrain_cost(
            current_pos, effective_movement
        )

        best_pos = None
        best_score = -1

        map_data = self.world.get_singleton_component(MapData)
        if not map_data:
            return None

        for pos, cost in reachable_positions.items():
            tile_entity = map_data.tiles.get(pos)
            if tile_entity:
                terrain = self.world.get_component(tile_entity, Terrain)

                # Import TerritoryControl component
                from ..components import TerritoryControl

                territory_control = self.world.get_component(
                    tile_entity, TerritoryControl
                )

                if terrain:
                    # Compute defensive value for the terrain
                    from ..prefabs.config import GameConfig

                    score = 0
                    terrain_effect = GameConfig.TERRAIN_EFFECTS.get(
                        terrain.terrain_type
                    )
                    if terrain_effect:
                        score += terrain_effect.defense_bonus

                    # City tiles get extra score (strategic value)
                    if terrain.terrain_type == TerrainType.CITY:
                        score += 10

                    # Bonus for own-controlled tiles
                    if (
                        territory_control
                        and territory_control.controlling_faction == unit.faction
                    ):
                        score += 5
                        # Extra bonus for fortification level
                        score += territory_control.fortification_level * 3

                    # Bonus for neutral key terrain
                    elif not territory_control and terrain.terrain_type in [
                        TerrainType.CITY,
                        TerrainType.HILL,
                    ]:
                        score += 8

                    if score > best_score:
                        best_score = score
                        best_pos = pos

        return best_pos

    def _try_occupy_territory(self, unit_entity: int) -> bool:
        """Try to capture the tile at the unit's current position."""
        position = self.world.get_component(unit_entity, HexPosition)
        unit = self.world.get_component(unit_entity, Unit)

        if not position or not unit:
            return False

        current_pos = (position.col, position.row)

        # Get current tile entity
        map_data = self.world.get_singleton_component(MapData)
        if not map_data or current_pos not in map_data.tiles:
            return False

        tile_entity = map_data.tiles[current_pos]
        terrain = self.world.get_component(tile_entity, Terrain)

        # Determine whether capture is needed
        should_capture = False

        # Import TerritoryControl component
        from ..components import TerritoryControl

        territory_control = self.world.get_component(tile_entity, TerritoryControl)

        if not territory_control:
            # Neutral tile: capture
            should_capture = True
        elif territory_control.controlling_faction != unit.faction:
            # Enemy-controlled tile: recapture
            should_capture = True
        elif (
            terrain
            and terrain.terrain_type == TerrainType.CITY
            and territory_control.controlling_faction != unit.faction
        ):
            # Enemy city: high-priority target
            should_capture = True

        if should_capture:
            # Execute capture
            territory_system = self._get_territory_system()
            if territory_system:
                return territory_system.start_capture(unit_entity, current_pos)

        return False

    def _try_build_fortification(self, unit_entity: int) -> bool:
        """Try to build fortifications at the current position."""
        position = self.world.get_component(unit_entity, HexPosition)
        unit = self.world.get_component(unit_entity, Unit)

        if not position or not unit:
            return False

        current_pos = (position.col, position.row)

        # Get current tile entity
        map_data = self.world.get_singleton_component(MapData)
        if not map_data or current_pos not in map_data.tiles:
            return False

        tile_entity = map_data.tiles[current_pos]

        # Import TerritoryControl component
        from ..components import TerritoryControl

        territory_control = self.world.get_component(tile_entity, TerritoryControl)

        # Only build on own-controlled tiles
        if (
            not territory_control
            or territory_control.controlling_faction != unit.faction
        ):
            return False

        # Max fortification level guard
        max_fortification_level = 3
        if territory_control.fortification_level >= max_fortification_level:
            return False

        # Decide whether fortification is worth building (strategic value)
        if self._should_build_fortification(tile_entity, territory_control):
            # Execute fortification build
            territory_system = self._get_territory_system()
            if territory_system:
                return territory_system.build_fortification(unit_entity, current_pos)

        return False

    def _should_build_fortification(self, tile_entity: int, territory_control) -> bool:
        """Return whether to build fortifications here."""
        terrain = self.world.get_component(tile_entity, Terrain)

        # Cities: always prioritize fortification
        if terrain and terrain.terrain_type == TerrainType.CITY:
            return True

        # Fully captured tiles are worth fortifying
        if territory_control.capture_progress >= 1.0:
            return True

        # Border tiles (near enemies) are worth fortifying
        position = self.world.get_component(tile_entity, HexPosition)
        if position and self._is_border_position(
            (position.col, position.row), territory_control.controlling_faction
        ):
            return True

        return False

    def _is_border_position(self, pos: Tuple[int, int], current_faction) -> bool:
        """Return whether a position is a border (near enemy units or enemy-controlled tiles)."""
        # Check nearby enemy units
        for neighbor_pos in HexMath.hex_neighbors(*pos):
            # Check for an enemy unit at the neighbor position
            for entity in self.world.query().with_all(Unit, HexPosition).entities():
                unit_pos = self.world.get_component(entity, HexPosition)
                unit = self.world.get_component(entity, Unit)
                if (
                    unit_pos
                    and unit
                    and (unit_pos.col, unit_pos.row) == neighbor_pos
                    and unit.faction != current_faction
                ):
                    return True

        return False

    def _get_territory_system(self):
        """Get the territory system."""
        for system in self.world.systems:
            if system.__class__.__name__ == "TerritorySystem":
                return system
        return None

    def _get_obstacles_for_ai(self) -> Set[Tuple[int, int]]:
        """Get obstacles for AI pathfinding."""
        obstacles = set()

        # Add other unit positions as obstacles
        for entity in self.world.query().with_all(HexPosition, Unit).entities():
            pos = self.world.get_component(entity, HexPosition)
            if pos:
                obstacles.add((pos.col, pos.row))

        return obstacles

    def _all_units_exhausted(self, units: List[int]) -> bool:
        """Return whether all units are unable to act."""
        for unit_entity in units:
            action_points = self.world.get_component(unit_entity, ActionPoints)

            if action_points and action_points.current_ap > 0:
                return False

        return True

    def _end_ai_turn(self):
        """End the AI turn."""
        turn_system = self._get_turn_system()
        if turn_system:
            turn_system.end_turn()

    def _get_combat_system(self):
        """Get the combat system."""
        for system in self.world.systems:
            if system.__class__.__name__ == "CombatSystem":
                return system
        return None

    def _get_reachable_positions_with_terrain_cost(
        self, start_pos: Tuple[int, int], max_movement: int
    ) -> dict:
        """Get reachable positions accounting for terrain movement costs.

        Returns: {position: total_cost}
        """
        reachable = {}
        visited = set()
        queue = [(start_pos, 0)]  # (position, total_cost)

        while queue:
            current_pos, current_cost = queue.pop(0)

            if current_pos in visited:
                continue

            visited.add(current_pos)
            reachable[current_pos] = current_cost

            # Explore neighbors
            for neighbor in HexMath.hex_neighbors(*current_pos):
                if neighbor in visited:
                    continue

                # Skip blocked positions
                if self._is_position_blocked(neighbor):
                    continue

                # Terrain movement cost for this step
                terrain_cost = self._get_terrain_movement_cost(neighbor)
                new_cost = current_cost + terrain_cost

                # If cost exceeds max movement, skip
                if new_cost > max_movement:
                    continue

                queue.append((neighbor, new_cost))

        return reachable

    def _get_terrain_movement_cost(self, pos: Tuple[int, int]) -> int:
        """Get terrain movement cost at a position."""
        from ..prefabs.config import GameConfig

        # Fetch terrain component
        for entity in self.world.get_entities_with_component(Terrain):
            terrain = self.world.get_component(entity, Terrain)
            terrain_pos = self.world.get_component(entity, HexPosition)

            if terrain_pos and (terrain_pos.col, terrain_pos.row) == pos:
                terrain_effect = GameConfig.TERRAIN_EFFECTS.get(terrain.terrain_type)
                if terrain_effect:
                    return terrain_effect.movement_cost
                break

        # Default: plains cost
        return 1

    def _is_position_blocked(self, pos: Tuple[int, int]) -> bool:
        """Return whether a position is blocked."""
        # Blocked by another unit
        for entity in self.world.get_entities_with_component(Unit):
            unit_pos = self.world.get_component(entity, HexPosition)
            if unit_pos and (unit_pos.col, unit_pos.row) == pos:
                return True

        # Blocked by impassable terrain (movement_cost=999 treated as impassable)
        terrain_cost = self._get_terrain_movement_cost(pos)
        if terrain_cost >= 999:
            return True

        return False

    def _get_turn_system(self):
        """Get the turn system."""
        for system in self.world.systems:
            if system.__class__.__name__ == "TurnSystem":
                return system
        return None

    def _get_action_system(self):
        """Get the action system."""
        for system in self.world.systems:
            if system.__class__.__name__ == "ActionSystem":
                return system
        return None

    def _make_realtime_ai_decisions(self):
        """Real-time AI decision logic."""
        # Collect AI players
        ai_players = []
        for entity in self.world.query().with_all(Player, AIControlled).entities():
            ai_players.append(entity)

        # Execute decisions per AI player
        for player_entity in ai_players:
            self._make_ai_decisions(player_entity)

    def _debug_ai_status(self):
        """Debug AI status."""
        print("=== AI Status Debug ===")

        # Summarize AI unit status
        ai_unit_count = 0
        active_ai_units = 0

        for entity in self.world.query().with_all(Unit, AIControlled).entities():
            ai_unit_count += 1
            unit = self.world.get_component(entity, Unit)
            movement = self.world.get_component(entity, MovementPoints)
            combat = self.world.get_component(entity, Combat)
            unit_count = self.world.get_component(entity, UnitCount)
            action_points = self.world.get_component(entity, ActionPoints)

            if unit_count and unit_count.current_count > 0:
                can_move = movement and movement.current_mp > 0
                can_attack = combat and not combat.has_attacked
                has_ap = action_points and action_points.current_ap > 0

                if (can_move or can_attack) and has_ap:
                    active_ai_units += 1
                    print(
                        f"AI Unit {entity}: Faction={unit.faction}, Count={unit_count.current_count}, "
                        f"Movement={movement.current_mp}/{movement.max_mp}, "
                        f"AP={action_points.current_ap}/{action_points.max_ap}, "
                        f"CanAttack={can_attack}"
                    )

        print(f"Total AI units: {ai_unit_count}, Active AI units: {active_ai_units}")
        print("======================")

    def _get_movement_system(self):
        """Get the movement system."""
        for system in self.world.systems:
            if system.__class__.__name__ == "MovementSystem":
                return system
        return None
