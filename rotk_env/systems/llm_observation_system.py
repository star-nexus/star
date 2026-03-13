"""
LLM Observation System - Provides observation data collection for the LLM system
Supports multiple observation levels: faction view, single-unit view, god view, and more
"""

from typing import Dict, List, Any, Optional, Tuple, Set
from framework import World
from ..components import (
    Unit,
    UnitCount,
    HexPosition,
    MovementPoints,
    Combat,
    Vision,
    Player,
    GameState,
    FogOfWar,
    Terrain,
    Tile,
    UnitStatus,
    GameStats,
    BattleLog,
)
from ..prefabs.config import Faction, TerrainType
from ..utils.hex_utils import HexMath


class ObservationLevel:
    """Observation level definitions"""

    UNIT = "unit"  # Single unit view
    FACTION = "faction"  # Faction view
    GODVIEW = "godview"  # God view (omniscient)
    LIMITED = "limited"  # Limited view (based on fog of war)


class LLMObservationSystem:
    """LLM Observation System - Collects and provides game observation data at different levels"""

    def __init__(self, world: World):
        self.world = world
        self.cache = {}
        self.cache_timestamp = 0
        self.cache_duration = 1.0  # Cache for 1 second

    def get_observation(
        self,
        observation_level: str,
        faction: Optional[Faction] = None,
        unit_id: Optional[int] = None,
        include_hidden: bool = False,
    ) -> Dict[str, Any]:
        """Get observation data

        Args:
            observation_level: Observation level (unit/faction/godview/limited)
            faction: Faction (required for faction level)
            unit_id: Unit ID (required for unit level)
            include_hidden: Whether to include hidden information (godview only)

        Returns:
            Dict with 'success' field and either 'data' or 'error' information
        """
        try:
            import time

            current_time = time.time()

            # Parameter validation
            if not observation_level:
                return {
                    "success": False,
                    "error": "Missing required parameter: observation_level",
                    "error_code": "MISSING_PARAM",
                    "operation": "get_observation",
                }

            if observation_level not in [
                ObservationLevel.UNIT,
                ObservationLevel.FACTION,
                ObservationLevel.GODVIEW,
                ObservationLevel.LIMITED,
            ]:
                return {
                    "success": False,
                    "error": f"Invalid observation_level: {observation_level}",
                    "error_code": "INVALID_PARAM",
                    "operation": "get_observation",
                    "valid_levels": [
                        ObservationLevel.UNIT,
                        ObservationLevel.FACTION,
                        ObservationLevel.GODVIEW,
                        ObservationLevel.LIMITED,
                    ],
                }

            # Level-specific parameter validation
            if observation_level == ObservationLevel.UNIT:
                if unit_id is None:
                    return {
                        "success": False,
                        "error": "unit_id is required for UNIT observation level",
                        "error_code": "MISSING_REQUIRED_PARAM",
                        "operation": "get_observation",
                        "observation_level": observation_level,
                    }
                try:
                    unit_id = int(unit_id)
                except (ValueError, TypeError):
                    return {
                        "success": False,
                        "error": f"Invalid unit_id type: expected int, got {type(unit_id).__name__}",
                        "error_code": "INVALID_TYPE",
                        "operation": "get_observation",
                    }

            elif observation_level in [
                ObservationLevel.FACTION,
                ObservationLevel.LIMITED,
            ]:
                if faction is None:
                    return {
                        "success": False,
                        "error": f"faction is required for {observation_level} observation level",
                        "error_code": "MISSING_REQUIRED_PARAM",
                        "operation": "get_observation",
                        "observation_level": observation_level,
                    }

            # Check cache
            cache_key = f"{observation_level}_{faction}_{unit_id}_{include_hidden}"
            if (
                cache_key in self.cache
                and current_time - self.cache_timestamp < self.cache_duration
            ):
                cached_result = self.cache[cache_key]
                cached_result["from_cache"] = True
                return cached_result

            # Generate new observation data
            observation_data = None
            if observation_level == ObservationLevel.UNIT:
                observation_data = self._get_unit_observation(unit_id)
            elif observation_level == ObservationLevel.FACTION:
                observation_data = self._get_faction_observation(
                    faction, include_hidden
                )
            elif observation_level == ObservationLevel.GODVIEW:
                observation_data = self._get_godview_observation()
            elif observation_level == ObservationLevel.LIMITED:
                observation_data = self._get_limited_observation(faction)

            # Check if observation data has errors
            if observation_data and "error" in observation_data:
                result = {
                    "success": False,
                    "error": observation_data["error"],
                    "error_code": observation_data.get(
                        "error_code", "OBSERVATION_ERROR"
                    ),
                    "operation": "get_observation",
                    "observation_level": observation_level,
                }
            else:
                # Successfully retrieved observation data
                result = {
                    "success": True,
                    "data": observation_data,
                    "metadata": {
                        "timestamp": current_time,
                        "observation_level": observation_level,
                        "faction": (
                            faction.value
                            if faction and hasattr(faction, "value")
                            else str(faction) if faction else None
                        ),
                        "unit_id": unit_id,
                        "include_hidden": include_hidden,
                        "game_state": self._get_game_state_info(),
                    },
                    "operation": "get_observation",
                }

            # Update cache
            self.cache[cache_key] = result
            self.cache_timestamp = current_time

            return result

        except Exception as e:
            return {
                "success": False,
                "error": f"Unexpected error in get_observation: {str(e)}",
                "error_code": "INTERNAL_ERROR",
                "operation": "get_observation",
                "params": {
                    "observation_level": observation_level,
                    "faction": faction,
                    "unit_id": unit_id,
                    "include_hidden": include_hidden,
                },
            }

    def _get_unit_observation(self, unit_id: int) -> Dict[str, Any]:
        """Get observation data for a single unit"""
        try:
            if unit_id is None or not self.world.has_entity(unit_id):
                return {
                    "error": f"Unit {unit_id} does not exist",
                    "error_code": "UNIT_NOT_FOUND",
                }

            unit = self.world.get_component(unit_id, Unit)
            position = self.world.get_component(unit_id, HexPosition)
            unit_count = self.world.get_component(unit_id, UnitCount)
            movement = self.world.get_component(unit_id, MovementPoints)
            combat = self.world.get_component(unit_id, Combat)
            vision = self.world.get_component(unit_id, Vision)

            if not unit or not position:
                return {
                    "error": f"Unit {unit_id} missing essential components (Unit or HexPosition)",
                    "error_code": "COMPONENT_MISSING",
                }

            # Unit's own information
            unit_info = {
                "id": unit_id,
                "name": unit.name,
                "faction": (
                    unit.faction.value
                    if hasattr(unit.faction, "value")
                    else str(unit.faction)
                ),
                "type": (
                    unit.unit_type.value
                    if hasattr(unit.unit_type, "value")
                    else str(unit.unit_type)
                ),
                "position": {"col": position.col, "row": position.row},
            }

            # Add attribute information
            if unit_count:
                unit_info["unit_count"] = {
                    "current": unit_count.current_count,
                    "max": unit_count.max_count,
                    "percentage": (
                        unit_count.current_count / unit_count.max_count
                        if unit_count.max_count > 0
                        else 0
                    ),
                    "is_alive": unit_count.current_count > 0,
                }

            if movement:
                unit_info["movement"] = {
                    "current": movement.current_mp,
                    "max": movement.max_mp,
                    # "has_moved": movement.has_moved,  # Removed single-move display
                    "can_move": movement.current_mp > 0,  # Any positive MP allows movement
                }

            if combat:
                unit_info["combat"] = {
                    "attack": combat.base_attack,
                    "defense": combat.base_defense,
                    "range": combat.attack_range,
                    # "has_attacked": (  # Removed single-attack limitation display
                    #     combat.has_attacked
                    #     if hasattr(combat, "has_attacked")
                    #     else False
                    # ),
                    "can_attack": True,  # Any combat capability allows attacking
                }

            # Information within the unit's sight range
            visible_area = self._get_visible_area(unit_id)
            visible_units = self._get_visible_units(unit_id, visible_area)
            visible_terrain = self._get_visible_terrain(visible_area)

            return {
                "unit": unit_info,
                "visible_area": visible_area,
                "visible_units": visible_units,
                "visible_terrain": visible_terrain,
                "action_options": self._get_unit_action_options(unit_id),
            }

        except Exception as e:
            return {
                "error": f"Error getting unit observation: {str(e)}",
                "error_code": "OBSERVATION_ERROR",
            }

    def _get_faction_observation(
        self, faction: Faction, include_hidden: bool = False
    ) -> Dict[str, Any]:
        """Get faction observation data"""
        try:
            if not faction:
                return {
                    "error": "Faction not specified",
                    "error_code": "MISSING_FACTION",
                }

            # Get all units of the faction
            faction_units = []
            for entity in self.world.query().with_all(Unit).entities():
                unit = self.world.get_component(entity, Unit)
                if unit and unit.faction == faction:
                    unit_obs = self._get_unit_summary(entity, include_hidden)
                    faction_units.append(unit_obs)

            # Get known enemy units
            enemy_units = []
            visible_positions = set()

            # Collect vision ranges of all friendly units
            for entity in (
                self.world.query().with_all(Unit, Vision, HexPosition).entities()
            ):
                unit = self.world.get_component(entity, Unit)
                if unit and unit.faction == faction:
                    visible_area = self._get_visible_area(entity)
                    visible_positions.update(visible_area)

            # Get enemy units within visible area
            for entity in self.world.query().with_all(Unit, HexPosition).entities():
                unit = self.world.get_component(entity, Unit)
                position = self.world.get_component(entity, HexPosition)
                if (
                    unit
                    and position
                    and unit.faction != faction
                    and (position.col, position.row) in visible_positions
                ):
                    enemy_info = self._get_unit_summary(
                        entity, False
                    )  # Do not reveal hidden info for enemy units
                    enemy_units.append(enemy_info)

            # Strategic information
            strategic_info = self._get_strategic_info(faction)

            return {
                "faction": faction.value if hasattr(faction, "value") else str(faction),
                "own_units": faction_units,
                "known_enemy_units": enemy_units,
                "strategic_info": strategic_info,
                "territory_control": self._get_territory_control(faction),
                "resources": self._get_faction_resources(faction),
            }

        except Exception as e:
            return {
                "error": f"Error getting faction observation: {str(e)}",
                "error_code": "OBSERVATION_ERROR",
            }

    def _get_godview_observation(self) -> Dict[str, Any]:
        """Get god-view observation data (omniscient view)"""
        all_units = []
        for entity in self.world.query().with_all(Unit).entities():
            unit_info = self._get_unit_summary(entity, include_hidden=True)
            all_units.append(unit_info)

        # Group by faction
        units_by_faction = {}
        for unit in all_units:
            faction = unit.get("faction", "Unknown")
            if faction not in units_by_faction:
                units_by_faction[faction] = []
            units_by_faction[faction].append(unit)

        # Full map information
        map_info = self._get_full_map_info()

        # Global statistics
        global_stats = self._get_global_statistics()

        return {
            "all_units": all_units,
            "units_by_faction": units_by_faction,
            "map_info": map_info,
            "global_statistics": global_stats,
            "battle_history": self._get_battle_history(),
        }

    def _get_limited_observation(self, faction: Faction) -> Dict[str, Any]:
        """Get limited observation data (based on fog of war system)"""
        # Similar to faction observation but constrained by fog of war
        fog_of_war = self.world.get_singleton_component(FogOfWar)

        # Get explored areas
        explored_areas = set()
        if fog_of_war:
            # TODO: get explored areas from the fog of war system
            pass

        # Get currently visible areas
        visible_areas = set()
        for entity in self.world.query().with_all(Unit, Vision, HexPosition).entities():
            unit = self.world.get_component(entity, Unit)
            if unit and unit.faction == faction:
                unit_visible = self._get_visible_area(entity)
                visible_areas.update(unit_visible)

        return {
            "faction": faction.value if hasattr(faction, "value") else str(faction),
            "explored_areas": list(explored_areas),
            "current_visible_areas": list(visible_areas),
            "fog_of_war_status": "active" if fog_of_war else "disabled",
        }

    def _get_visible_area(self, unit_id: int) -> Set[Tuple[int, int]]:
        """Get the unit's visible area."""
        position = self.world.get_component(unit_id, HexPosition)
        vision = self.world.get_component(unit_id, Vision)

        if not position or not vision:
            return set()

        visible_positions = set()
        center = (position.col, position.row)

        # Simple vision calculation (hex range)
        for col in range(
            position.col - vision.sight_range, position.col + vision.sight_range + 1
        ):
            for row in range(
                position.row - vision.sight_range, position.row + vision.sight_range + 1
            ):
                if HexMath.hex_distance(center, (col, row)) <= vision.sight_range:
                    visible_positions.add((col, row))

        return visible_positions

    def _get_visible_units(
        self, observer_id: int, visible_area: Set[Tuple[int, int]]
    ) -> List[Dict[str, Any]]:
        """Get units within the visible area."""
        visible_units = []

        for entity in self.world.query().with_all(Unit, HexPosition).entities():
            if entity == observer_id:  # Skip the observer itself
                continue

            position = self.world.get_component(entity, HexPosition)
            if position and (position.col, position.row) in visible_area:
                unit_info = self._get_unit_summary(entity, include_hidden=False)
                visible_units.append(unit_info)

        return visible_units

    def _get_visible_terrain(
        self, visible_area: Set[Tuple[int, int]]
    ) -> List[Dict[str, Any]]:
        """Get terrain within the visible area."""
        terrain_info = []

        for col, row in visible_area:
            # Find terrain at this position
            for entity in self.world.query().with_all(Tile, HexPosition).entities():
                position = self.world.get_component(entity, HexPosition)
                tile = self.world.get_component(entity, Tile)
                terrain = self.world.get_component(entity, Terrain)

                if position and position.col == col and position.row == row:
                    terrain_data = {
                        "position": {"col": col, "row": row},
                        "passable": tile.passable if tile else True,
                    }

                    if terrain:
                        terrain_data["type"] = (
                            terrain.terrain_type.value
                            if hasattr(terrain.terrain_type, "value")
                            else str(terrain.terrain_type)
                        )
                        terrain_data["movement_cost"] = terrain.movement_cost
                        terrain_data["defense_bonus"] = terrain.defense_bonus

                    terrain_info.append(terrain_data)
                    break

        return terrain_info

    def _get_unit_summary(
        self, entity: int, include_hidden: bool = False
    ) -> Dict[str, Any]:
        """Get unit summary."""
        unit = self.world.get_component(entity, Unit)
        position = self.world.get_component(entity, HexPosition)
        unit_count = self.world.get_component(entity, UnitCount)
        movement = self.world.get_component(entity, MovementPoints)
        combat = self.world.get_component(entity, Combat)
        status = self.world.get_component(entity, UnitStatus)

        unit_info = {
            "id": entity,
            "name": unit.name if unit else "Unknown",
            "faction": (
                unit.faction.value
                if unit and hasattr(unit.faction, "value")
                else str(unit.faction) if unit else "Unknown"
            ),
            "type": (
                unit.unit_type.value
                if unit and hasattr(unit.unit_type, "value")
                else str(unit.unit_type) if unit else "Unknown"
            ),
        }

        if position:
            unit_info["position"] = {"col": position.col, "row": position.row}

        if unit_count:
            unit_info["unit_count"] = {
                "current": unit_count.current_count,
                "max": unit_count.max_count,
                "percentage": (
                    unit_count.current_count / unit_count.max_count
                    if unit_count.max_count > 0
                    else 0
                ),
            }

        # Only include detailed state when hidden info is allowed (e.g., god view).
        if include_hidden:
            if movement:
                unit_info["movement"] = {
                    "current": movement.current_mp,
                    "max": movement.max_mp,
                    # "has_moved": movement.has_moved,  # Removed single-move display
                }

            if combat:
                unit_info["combat"] = {
                    "attack": combat.attack,
                    "defense": combat.defense,
                    "range": combat.attack_range,
                    # "has_attacked": combat.has_attacked,  # Removed single-attack limitation display
                    "can_attack": True,  # Any combat capability allows attacking
                }

            if status:
                unit_info["status"] = {
                    "is_defending": getattr(status, "is_defending", False),
                    "is_fortified": getattr(status, "is_fortified", False),
                    "is_moving": getattr(status, "is_moving", False),
                }

        return unit_info

    def _get_unit_action_options(self, unit_id: int) -> List[str]:
        """Get action options the unit can execute."""
        movement = self.world.get_component(unit_id, MovementPoints)
        combat = self.world.get_component(unit_id, Combat)

        actions = []

        if movement and movement.current_mp > 0:  # Any positive MP allows movement
            actions.append("move")

        if combat:  # Any combat component enables attack (do not check has_attacked)
            actions.append("attack")

        actions.extend(["defend", "scout", "retreat", "fortify"])

        return actions

    def _get_strategic_info(self, faction: Faction) -> Dict[str, Any]:
        """Get faction-level strategic info."""
        return {
            "total_units": len(
                [
                    e
                    for e in self.world.query().with_all(Unit).entities()
                    if self.world.get_component(e, Unit).faction == faction
                ]
            ),
            "units_ready_to_act": len(
                [
                    e
                    for e in self.world.query()
                    .with_all(Unit, MovementPoints)
                    .entities()
                    if (
                        self.world.get_component(e, Unit).faction == faction
                        and self.world.get_component(e, MovementPoints).current_mp > 0
                    )
                ]
            ),
            "wounded_units": len(
                [
                    e
                    for e in self.world.query().with_all(Unit, UnitCount).entities()
                    if (
                        self.world.get_component(e, Unit).faction == faction
                        and self.world.get_component(e, UnitCount).current_count
                        < self.world.get_component(e, UnitCount).max_count
                    )
                ]
            ),
        }

    def _get_territory_control(self, faction: Faction) -> Dict[str, Any]:
        """Get territory control info."""
        # TODO: Implement territory control calculation
        return {"controlled_tiles": 0, "contested_tiles": 0, "strategic_points": []}

    def _get_faction_resources(self, faction: Faction) -> Dict[str, Any]:
        """Get faction resources."""
        # TODO: Implement resource system
        return {"manpower": 1000, "supplies": 500, "morale": 80}

    def _get_full_map_info(self) -> Dict[str, Any]:
        """Get full map information."""
        tiles = []
        for entity in self.world.query().with_all(Tile, HexPosition).entities():
            position = self.world.get_component(entity, HexPosition)
            tile = self.world.get_component(entity, Tile)
            terrain = self.world.get_component(entity, Terrain)

            tile_info = {
                "position": {"col": position.col, "row": position.row},
                "passable": tile.passable if tile else True,
            }

            if terrain:
                tile_info["terrain_type"] = (
                    terrain.terrain_type.value
                    if hasattr(terrain.terrain_type, "value")
                    else str(terrain.terrain_type)
                )
                tile_info["movement_cost"] = terrain.movement_cost
                tile_info["defense_bonus"] = terrain.defense_bonus

            tiles.append(tile_info)

        return {"tiles": tiles}

    def _get_global_statistics(self) -> Dict[str, Any]:
        """Get global statistics."""
        game_stats = self.world.get_singleton_component(GameStats)

        if game_stats:
            return {
                "turn_number": getattr(game_stats, "turn_number", 1),
                "total_battles": getattr(game_stats, "total_battles", 0),
                "total_casualties": getattr(game_stats, "total_casualties", 0),
            }

        return {"turn_number": 1, "total_battles": 0, "total_casualties": 0}

    def _get_battle_history(self) -> List[Dict[str, Any]]:
        """Get battle history."""
        battle_log = self.world.get_singleton_component(BattleLog)

        if battle_log and hasattr(battle_log, "entries"):
            return [
                {
                    "turn": entry.turn,
                    "attacker": entry.attacker_name,
                    "defender": entry.defender_name,
                    "damage": entry.damage,
                    "result": entry.result,
                }
                for entry in battle_log.entries[-10:]  # Last 10 battles
            ]

        return []

    def _get_game_state_info(self) -> Dict[str, Any]:
        """Get game state information."""
        game_state = self.world.get_singleton_component(GameState)

        if game_state:
            return {
                "current_player": (
                    game_state.current_player.value
                    if hasattr(game_state.current_player, "value")
                    else str(game_state.current_player)
                ),
                "game_mode": (
                    game_state.game_mode.value
                    if hasattr(game_state.game_mode, "value")
                    else str(game_state.game_mode)
                ),
                "turn_number": getattr(game_state, "turn_number", 1),
                "phase": getattr(game_state, "phase", "action"),
            }

        return {
            "current_player": "Unknown",
            "game_mode": "Unknown",
            "turn_number": 1,
            "phase": "action",
        }

    def clear_cache(self):
        """Clear observation cache."""
        self.cache.clear()
        self.cache_timestamp = 0
