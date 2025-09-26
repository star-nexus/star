"""
Statistics System - Responsible for game data statistics and recording
Strictly follows ECS specification: only handles business logic, does not store data
"""

import time
from typing import Dict, Set, Tuple, Optional, List, Any
from framework import System, World
from ..components import (
    Unit,
    UnitCount,
    HexPosition,
    MovementPoints,
    Combat,
    Vision,
    GameStats,
    BattleLog,
    UnitObservation,
    UnitStatistics,
    VisibilityTracker,
    GameModeStatistics,
    GameState,
    FogOfWar,
    Terrain,
    Tile,
    GameModeComponent,
    GameTime,
)
from ..prefabs.config import Faction, TerrainType


class StatisticsSystem(System):
    """Statistics system - manages game statistics and data recording"""

    def __init__(self):
        super().__init__(priority=15)
        self.last_update_time = 0.0
        self.observation_interval = 1.0  # Record observation data every second

    def initialize(self, world: World) -> None:
        """Initialize statistics system"""
        self.world = world

        # Initialize statistics components
        self._initialize_statistics_components()

    def subscribe_events(self) -> None:
        """Subscribe to events"""
        pass

    def _initialize_statistics_components(self) -> None:
        """Initialize all statistics-related components"""
        # Game statistics
        if not self.world.get_singleton_component(GameStats):
            stats = GameStats()
            stats.game_start_time = time.time()
            self.world.add_singleton_component(stats)

        # Game mode statistics
        if not self.world.get_singleton_component(GameModeStatistics):
            mode_stats = GameModeStatistics()
            self.world.add_singleton_component(mode_stats)

        # Visibility tracker
        if not self.world.get_singleton_component(VisibilityTracker):
            visibility_tracker = VisibilityTracker()
            self.world.add_singleton_component(visibility_tracker)

    def update(self, delta_time: float) -> None:
        """Update statistics system"""
        current_time = time.time()

        # Update game time
        self._update_game_time(delta_time)

        # Periodically record unit observation data
        if current_time - self.last_update_time >= self.observation_interval:
            self._record_unit_observations()
            self._update_visibility_tracking()
            self._update_faction_statistics()
            self.last_update_time = current_time

    def _update_game_time(self, dt: float) -> None:
        """Update game time"""
        stats = self.world.get_singleton_component(GameStats)
        mode_stats = self.world.get_singleton_component(GameModeStatistics)

        if stats:
            stats.total_game_time += dt

        if mode_stats and mode_stats.current_mode == "realtime":
            mode_stats.realtime_stats["total_game_time"] += dt

    def _record_unit_observations(self) -> None:
        """Record unit observation data"""
        stats = self.world.get_singleton_component(GameStats)
        if not stats:
            return

        current_time = time.time()

        # Record observation data for each unit
        for entity in (
            self.world.query().with_all(Unit, UnitCount, HexPosition).entities()
        ):
            unit = self.world.get_component(entity, Unit)
            unit_count = self.world.get_component(entity, UnitCount)
            position = self.world.get_component(entity, HexPosition)
            movement = self.world.get_component(entity, MovementPoints)
            combat = self.world.get_component(entity, Combat)

            if not all([unit, unit_count, position]):
                continue

            # Get or create observation component
            observation = self.world.get_component(entity, UnitObservation)
            if not observation:
                observation = UnitObservation()
                self.world.add_component(entity, observation)

            # Update observation data
            observation.previous_position = observation.current_position
            observation.current_position = (position.col, position.row)
            observation.health_percentage = (
                unit_count.current_count / unit_count.max_count
            ) * 100

            if movement:
                observation.movement_remaining = movement.current_mp
                observation.has_acted_this_turn = movement.has_moved

                # Calculate movement distance
                if observation.previous_position != observation.current_position:
                    observation.total_distance_moved += 1
                    observation.movement_path.append(observation.current_position)

                    # Limit path length
                    if len(observation.movement_path) > 50:
                        observation.movement_path = observation.movement_path[-50:]

            if combat:
                observation.in_combat = combat.has_attacked
                if combat.has_attacked:
                    observation.last_combat_time = current_time

            # Get terrain information
            terrain_type = self._get_terrain_at_position(position.col, position.row)
            observation.current_terrain_type = terrain_type

            # Record to historical data
            observation_data = {
                "entity": entity,
                "faction": unit.faction.value,
                "unit_type": unit.unit_type.value,
                "position": observation.current_position,
                "health_percentage": observation.health_percentage,
                "movement_remaining": observation.movement_remaining,
                "in_combat": observation.in_combat,
                "terrain_type": observation.current_terrain_type,
                "timestamp": stats.total_game_time,
            }

            # Add observation record
            stats.unit_observation_history.append(observation_data)

            # Limit historical record count
            if len(stats.unit_observation_history) > 10000:
                stats.unit_observation_history = stats.unit_observation_history[-5000:]

    def _get_terrain_at_position(self, col: int, row: int) -> str:
        """Get terrain type at specified position"""
        try:
            # Try to get terrain information from map data
            from ..components import MapData

            map_data = self.world.get_singleton_component(MapData)
            if map_data and (col, row) in map_data.tiles:
                tile_entity = map_data.tiles[(col, row)]
                terrain = self.world.get_component(tile_entity, Terrain)
                if terrain:
                    return terrain.terrain_type.value
        except:
            pass
        return "plains"  # Default terrain

    def _update_visibility_tracking(self) -> None:
        """Update visibility tracking"""
        visibility_tracker = self.world.get_singleton_component(VisibilityTracker)
        fog_of_war = self.world.get_singleton_component(FogOfWar)

        if not visibility_tracker or not fog_of_war:
            return

        # Clear current visible units
        for faction in visibility_tracker.faction_visible_units:
            visibility_tracker.faction_visible_units[faction].clear()

        # Update visibility for each unit
        for entity in self.world.query().with_all(Unit, HexPosition).entities():
            unit = self.world.get_component(entity, Unit)
            position = self.world.get_component(entity, HexPosition)

            if not unit or not position:
                continue

            visible_to = set()
            unit_pos = (position.col, position.row)

            # Check which factions can see this unit
            for faction, vision_tiles in fog_of_war.faction_vision.items():
                if unit_pos in vision_tiles and faction != unit.faction:
                    visible_to.add(faction)

            # Unit's own faction can always see it
            visible_to.add(unit.faction)

            # Update visibility data
            self._update_unit_visibility(entity, visible_to, visibility_tracker)

    def _update_unit_visibility(
        self,
        unit_entity: int,
        visible_to: Set[Faction],
        visibility_tracker: VisibilityTracker,
    ) -> None:
        """Update unit visibility data"""
        current_time = time.time()

        # Update visible units mapping
        for faction in visible_to:
            if faction not in visibility_tracker.faction_visible_units:
                visibility_tracker.faction_visible_units[faction] = set()
            visibility_tracker.faction_visible_units[faction].add(unit_entity)

        # Record visibility history
        if unit_entity not in visibility_tracker.visibility_history:
            visibility_tracker.visibility_history[unit_entity] = []

        visibility_record = {
            "timestamp": current_time,
            "visible_to": list(visible_to),
            "newly_spotted": False,
            "lost_sight": False,
        }

        visibility_tracker.visibility_history[unit_entity].append(visibility_record)

        # Limit historical record count
        if len(visibility_tracker.visibility_history[unit_entity]) > 100:
            visibility_tracker.visibility_history[unit_entity] = (
                visibility_tracker.visibility_history[unit_entity][-100:]
            )

        # Update unit observation component
        observation = self.world.get_component(unit_entity, UnitObservation)
        if observation:
            observation.is_visible_to = visible_to
            observation.last_seen_time = current_time

    def _update_faction_statistics(self) -> None:
        """Update faction statistics"""
        stats = self.world.get_singleton_component(GameStats)
        if not stats:
            return

        # Count territory control for each faction
        faction_territories = {}

        # Count units and positions controlled by each faction
        for entity in (
            self.world.query().with_all(Unit, HexPosition, UnitCount).entities()
        ):
            unit = self.world.get_component(entity, Unit)
            unit_count = self.world.get_component(entity, UnitCount)

            if not unit or not unit_count or unit_count.current_count <= 0:
                continue

            faction = unit.faction

            # Initialize faction statistics
            self._initialize_faction_stats(faction, stats)

            # Count territory (simplified: each living unit controls 1 territory)
            faction_territories[faction] = faction_territories.get(faction, 0) + 1

        # Update territory control statistics
        for faction, territory_count in faction_territories.items():
            if faction in stats.faction_stats:
                stats.faction_stats[faction]["territory_controlled"] = territory_count

    def _initialize_faction_stats(self, faction: Faction, stats: GameStats) -> None:
        """Initialize faction statistics data"""
        if faction not in stats.faction_stats:
            stats.faction_stats[faction] = {
                "kills": 0,
                "losses": 0,
                "damage_dealt": 0,
                "damage_taken": 0,
                "units_created": 0,
                "turns_played": 0,
                "territory_controlled": 0,
                "actions_taken": 0,
                "movement_distance": 0,
                "battles_won": 0,
                "battles_lost": 0,
            }

    # === Public interface methods - called by other systems ===

    def record_combat_action(
        self, attacker_entity: int, target_entity: int, damage: int, result: str
    ) -> None:
        """Record combat action"""
        stats = self.world.get_singleton_component(GameStats)
        battle_log = self.world.get_singleton_component(BattleLog)
        mode_stats = self.world.get_singleton_component(GameModeStatistics)

        attacker_unit = self.world.get_component(attacker_entity, Unit)
        target_unit = self.world.get_component(target_entity, Unit)

        if not attacker_unit or not target_unit:
            return

        # Update unit statistics
        self._update_unit_combat_stats(attacker_entity, target_entity, damage, result)

        # Update faction statistics
        if stats:
            self._initialize_faction_stats(attacker_unit.faction, stats)
            self._initialize_faction_stats(target_unit.faction, stats)

            stats.faction_stats[attacker_unit.faction]["damage_dealt"] += damage
            stats.faction_stats[target_unit.faction]["damage_taken"] += damage

            if result == "kill":
                stats.faction_stats[attacker_unit.faction]["kills"] += 1
                stats.faction_stats[target_unit.faction]["losses"] += 1

            # Record battle history
            battle_record = {
                "attacker_faction": attacker_unit.faction.value,
                "target_faction": target_unit.faction.value,
                "damage": damage,
                "result": result,
                "attacker_entity": attacker_entity,
                "target_entity": target_entity,
                "timestamp": stats.total_game_time,
            }
            stats.battle_history.append(battle_record)

        # Record to battle log
        if battle_log:
            self._add_battle_log_entry(
                battle_log, attacker_unit, target_unit, damage, result
            )

        # Record game mode statistics
        if mode_stats:
            self._record_mode_action(mode_stats, attacker_unit.faction, "combat")

    def _update_unit_combat_stats(
        self, attacker_entity: int, target_entity: int, damage: int, result: str
    ) -> None:
        """Update unit combat statistics"""
        # Attacker statistics
        attacker_stats = self.world.get_component(attacker_entity, UnitStatistics)
        if not attacker_stats:
            attacker_stats = UnitStatistics()
            self.world.add_component(attacker_entity, attacker_stats)

        attacker_stats.attacks_made += 1
        attacker_stats.damage_dealt += damage
        attacker_stats.battles_participated += 1

        # Target statistics
        target_stats = self.world.get_component(target_entity, UnitStatistics)
        if not target_stats:
            target_stats = UnitStatistics()
            self.world.add_component(target_entity, target_stats)

        target_stats.damage_taken += damage
        target_stats.battles_participated += 1

        # If target dies
        if result == "kill":
            attacker_stats.kills += 1
            attacker_stats.battles_won += 1
            target_stats.deaths += 1
            target_stats.battles_lost += 1

    def _get_current_time_info(self) -> tuple[str, Optional[int]]:
        """Get current time information (game time display and turn number)"""
        game_time = self.world.get_singleton_component(GameTime)
        if game_time:
            return game_time.get_current_time_display(), game_time.get_turn_number()

        # Compatibility: use GameState to determine mode
        game_state = self.world.get_singleton_component(GameState)
        if game_state:
            if game_state.game_mode.value == "turn_based":
                # 回合制：显示回合数
                time_display = f"Turn {game_state.turn_number}"
                return time_display, game_state.turn_number
            else:
                # 实时制：显示游戏时间
                stats = self.world.get_singleton_component(GameStats)
                if stats:
                    minutes = int(stats.total_game_time // 60)
                    seconds = int(stats.total_game_time % 60)
                    time_display = f"{minutes:02d}:{seconds:02d}"
                else:
                    time_display = "00:00"
                return time_display, None

        # 默认回退
        return "00:00", None

    def _get_current_turn_number(self) -> Optional[int]:
        """Get current turn number (only in turn-based mode)"""
        _, turn_number = self._get_current_time_info()
        return turn_number

    def _add_battle_log_entry(
        self,
        battle_log: BattleLog,
        attacker_unit: Unit,
        target_unit: Unit,
        damage: int,
        result: str,
    ) -> None:
        """Add battle log entry"""
        if result == "kill":
            message = f"{attacker_unit.faction.value} defeated {target_unit.faction.value}'s {target_unit.unit_type.value}"
            log_type = "combat"
            color = (255, 100, 100)
        else:
            message = f"{attacker_unit.faction.value} dealt {damage} damage to {target_unit.faction.value}"
            log_type = "combat"
            color = (255, 200, 100)

        time_display, turn_number = self._get_current_time_info()
        battle_log.add_entry(
            message,
            log_type,
            attacker_unit.faction.value,
            color,
            time_display,
            turn_number,
        )

    def _add_movement_log_entry(
        self,
        battle_log: BattleLog,
        unit: Unit,
        from_pos: Tuple[int, int],
        to_pos: Tuple[int, int],
    ) -> None:
        """Add movement log entry"""
        message = f"{unit.faction.value}'s {unit.unit_type.value} moved ({from_pos[0]},{from_pos[1]})->({to_pos[0]},{to_pos[1]})"
        log_type = "movement"
        color = (100, 200, 255)  # Blue
        time_display, turn_number = self._get_current_time_info()
        battle_log.add_entry(
            message, log_type, unit.faction.value, color, time_display, turn_number
        )

    def _add_turn_change_log_entry(
        self,
        battle_log: BattleLog,
        previous_faction: Optional[Faction],
        new_faction: Faction,
    ) -> None:
        """Add turn change log entry"""
        if previous_faction:
            message = (
                f"{previous_faction.value} turn ended, {new_faction.value} turn started"
            )
        else:
            message = f"{new_faction.value} turn started"
        log_type = "turn"
        color = (255, 255, 100)  # Yellow
        time_display, turn_number = self._get_current_time_info()
        battle_log.add_entry(
            message, log_type, new_faction.value, color, time_display, turn_number
        )

    def record_movement_action(
        self, entity: int, from_pos: Tuple[int, int], to_pos: Tuple[int, int]
    ) -> None:
        """Record movement action"""
        unit = self.world.get_component(entity, Unit)
        if not unit:
            return

        # Update unit statistics
        unit_stats = self.world.get_component(entity, UnitStatistics)
        if not unit_stats:
            unit_stats = UnitStatistics()
            self.world.add_component(entity, unit_stats)

        unit_stats.moves_made += 1

        # Update game statistics
        stats = self.world.get_singleton_component(GameStats)
        if stats:
            self._initialize_faction_stats(unit.faction, stats)
            stats.faction_stats[unit.faction]["actions_taken"] += 1
            stats.faction_stats[unit.faction]["movement_distance"] += 1

        # Record game mode statistics
        mode_stats = self.world.get_singleton_component(GameModeStatistics)
        if mode_stats:
            self._record_mode_action(mode_stats, unit.faction, "movement")

        # Record to battle log
        battle_log = self.world.get_singleton_component(BattleLog)
        if battle_log:
            self._add_movement_log_entry(battle_log, unit, from_pos, to_pos)

    def record_turn_change(
        self, previous_faction: Optional[Faction], new_faction: Faction
    ) -> None:
        """Record turn change"""
        stats = self.world.get_singleton_component(GameStats)
        mode_stats = self.world.get_singleton_component(GameModeStatistics)
        game_state = self.world.get_singleton_component(GameState)

        if not game_state:
            return

        # Record turn history
        if stats:
            turn_record = {
                "turn_number": game_state.turn_number,
                "previous_faction": (
                    previous_faction.value if previous_faction else None
                ),
                "new_faction": new_faction.value,
                "game_mode": game_state.game_mode.value,
                "timestamp": stats.total_game_time,
            }
            stats.turn_history.append(turn_record)

        # Update game mode statistics
        if mode_stats:
            self._handle_turn_change(mode_stats, previous_faction, new_faction)

        # Update faction turn statistics
        if stats:
            self._initialize_faction_stats(new_faction, stats)

        # Record to battle log
        battle_log = self.world.get_singleton_component(BattleLog)
        if battle_log:
            self._add_turn_change_log_entry(battle_log, previous_faction, new_faction)

        # Update turn statistics
        if stats:
            stats.faction_stats[new_faction]["turns_played"] += 1

    def _record_mode_action(
        self, mode_stats: GameModeStatistics, faction: Faction, action_type: str
    ) -> None:
        """Record game mode action"""
        current_time = time.time()

        if mode_stats.current_mode == "turn_based":
            mode_stats.actions_this_turn += 1
        else:  # realtime
            # Update actions per minute
            if current_time - mode_stats.last_action_time > 60:
                mode_stats.actions_this_minute = 0
            mode_stats.actions_this_minute += 1

            # Update real-time statistics
            if faction not in mode_stats.realtime_stats["faction_activity"]:
                mode_stats.realtime_stats["faction_activity"][faction] = 0
            mode_stats.realtime_stats["faction_activity"][faction] += 1

            mode_stats.realtime_stats["action_frequency"].append(
                {
                    "timestamp": current_time,
                    "faction": faction,
                    "action_type": action_type,
                }
            )

        mode_stats.last_action_time = current_time

    def _handle_turn_change(
        self,
        mode_stats: GameModeStatistics,
        previous_faction: Optional[Faction],
        new_faction: Faction,
    ) -> None:
        """Handle turn change statistics"""
        if mode_stats.current_mode == "turn_based":
            # End previous turn
            if previous_faction and mode_stats.current_turn_start_time > 0:
                turn_duration = time.time() - mode_stats.current_turn_start_time

                # Update statistics
                mode_stats.turn_based_stats["total_turns"] += 1
                mode_stats.turn_based_stats["turn_durations"].append(turn_duration)

                if (
                    previous_faction
                    not in mode_stats.turn_based_stats["faction_turn_times"]
                ):
                    mode_stats.turn_based_stats["faction_turn_times"][
                        previous_faction
                    ] = []
                mode_stats.turn_based_stats["faction_turn_times"][
                    previous_faction
                ].append(turn_duration)

                # Update averages
                durations = mode_stats.turn_based_stats["turn_durations"]
                mode_stats.turn_based_stats["average_turn_duration"] = sum(
                    durations
                ) / len(durations)
                mode_stats.turn_based_stats["longest_turn"] = max(durations)
                mode_stats.turn_based_stats["shortest_turn"] = min(durations)

                # Record actions this turn
                turn_num = mode_stats.turn_based_stats["total_turns"]
                mode_stats.turn_based_stats["actions_per_turn"][
                    turn_num
                ] = mode_stats.actions_this_turn

            # Start new turn
            mode_stats.current_turn_start_time = time.time()
            mode_stats.actions_this_turn = 0

            if new_faction not in mode_stats.turn_based_stats["faction_turn_times"]:
                mode_stats.turn_based_stats["faction_turn_times"][new_faction] = []

    # === New event recording methods ===

    def record_defense_action(self, entity: int, attacker_entity: int) -> None:
        """Record defense action"""
        unit = self.world.get_component(entity, Unit)
        attacker_unit = self.world.get_component(attacker_entity, Unit)
        if not unit or not attacker_unit:
            return

        # Update unit statistics
        unit_stats = self.world.get_component(entity, UnitStatistics)
        if not unit_stats:
            unit_stats = UnitStatistics()
            self.world.add_component(entity, unit_stats)

        unit_stats.defenses_made += 1

        # Record to battle log
        battle_log = self.world.get_singleton_component(BattleLog)
        if battle_log:
            message = f"{unit.faction.value}'s {unit.unit_type.value} defended against attack from {attacker_unit.faction.value}"
            time_display, turn_number = self._get_current_time_info()
            battle_log.add_entry(
                message,
                "defense",
                unit.faction.value,
                (0, 255, 255),
                time_display,
                turn_number,
            )

    def record_skill_action(self, entity: int, skill_name: str) -> None:
        """Record skill usage"""
        unit = self.world.get_component(entity, Unit)
        if not unit:
            return

        # Record to battle log
        battle_log = self.world.get_singleton_component(BattleLog)
        if battle_log:
            message = f"{unit.faction.value}'s {unit.unit_type.value} used skill: {skill_name}"
            time_display, turn_number = self._get_current_time_info()
            battle_log.add_entry(
                message,
                "skill",
                unit.faction.value,
                (255, 165, 0),
                time_display,
                turn_number,
            )

    def record_garrison_action(self, entity: int) -> None:
        """Record garrison action"""
        unit = self.world.get_component(entity, Unit)
        if not unit:
            return

        # Record to battle log
        battle_log = self.world.get_singleton_component(BattleLog)
        if battle_log:
            message = (
                f"{unit.faction.value}'s {unit.unit_type.value} entered garrison status"
            )
            time_display, turn_number = self._get_current_time_info()
            battle_log.add_entry(
                message,
                "garrison",
                unit.faction.value,
                (128, 255, 128),
                time_display,
                turn_number,
            )

    def record_wait_action(self, entity: int) -> None:
        """Record wait action"""
        unit = self.world.get_component(entity, Unit)
        if not unit:
            return

        # Record to battle log
        battle_log = self.world.get_singleton_component(BattleLog)
        if battle_log:
            message = f"{unit.faction.value}'s {unit.unit_type.value} chose to wait"
            time_display, turn_number = self._get_current_time_info()
            battle_log.add_entry(
                message,
                "wait",
                unit.faction.value,
                (192, 192, 192),
                time_display,
                turn_number,
            )

    def record_death_action(
        self, entity: int, killer_entity: Optional[int] = None
    ) -> None:
        """Record unit death"""
        unit = self.world.get_component(entity, Unit)
        if not unit:
            return

        battle_log = self.world.get_singleton_component(BattleLog)
        game_state = self.world.get_singleton_component(GameState)

        if battle_log:
            if killer_entity:
                killer_unit = self.world.get_component(killer_entity, Unit)
                if killer_unit:
                    message = f"{unit.faction.value}'s {unit.unit_type.value} was defeated by {killer_unit.faction.value}"
                else:
                    message = (
                        f"{unit.faction.value}'s {unit.unit_type.value} died in battle"
                    )
            else:
                message = (
                    f"{unit.faction.value}'s {unit.unit_type.value} died in battle"
                )

            # 根据游戏模式选择时间显示方式
            if game_state and game_state.game_mode.value == "turn_based":
                # 回合制：显示回合数
                time_display = f"Turn {game_state.turn_number}"
                turn_number = game_state.turn_number
            else:
                # 实时制：显示游戏时间
                stats = self.world.get_singleton_component(GameStats)
                if stats:
                    minutes = int(stats.total_game_time // 60)
                    seconds = int(stats.total_game_time % 60)
                    time_display = f"{minutes:02d}:{seconds:02d}"
                else:
                    time_display = "00:00"
                turn_number = None

            battle_log.add_entry(
                message,
                "death",
                unit.faction.value,
                (255, 0, 0),
                time_display,
                turn_number,
            )

    def record_game_event(
        self,
        event_type: str,
        message: str,
        faction: str = "",
        color: tuple = (255, 255, 255),
    ) -> None:
        """Record general game event"""
        battle_log = self.world.get_singleton_component(BattleLog)
        if battle_log:
            time_display, turn_number = self._get_current_time_info()
            battle_log.add_entry(
                message, event_type, faction, color, time_display, turn_number
            )

    # === Data query methods ===

    def get_detailed_statistics(self) -> Dict:
        """Get detailed statistics information"""
        stats = self.world.get_singleton_component(GameStats)
        mode_stats = self.world.get_singleton_component(GameModeStatistics)
        visibility_tracker = self.world.get_singleton_component(VisibilityTracker)

        result = {
            "game_stats": {},
            "mode_stats": {},
            "visibility_stats": {},
            "unit_stats": {},
        }

        if stats:
            result["game_stats"] = {
                "total_game_time": stats.total_game_time,
                "faction_summaries": {
                    faction.value: self._get_faction_summary(faction, stats)
                    for faction in stats.faction_stats.keys()
                },
                "battle_count": len(stats.battle_history),
                "turn_count": len(stats.turn_history),
                "observation_count": len(stats.unit_observation_history),
            }

        if mode_stats:
            result["mode_stats"] = self._get_performance_metrics(mode_stats)

        if visibility_tracker:
            result["visibility_stats"] = {
                "total_units_tracked": len(visibility_tracker.visibility_history),
                "faction_visible_counts": {
                    faction.value: len(units)
                    for faction, units in visibility_tracker.faction_visible_units.items()
                },
            }

        # Collect unit statistics
        result["unit_stats"] = self._collect_unit_statistics()

        return result

    def _get_faction_summary(self, faction: Faction, stats: GameStats) -> Dict:
        """Get faction statistics summary"""
        if faction not in stats.faction_stats:
            return {}

        faction_stats = stats.faction_stats[faction].copy()
        faction_stats["kd_ratio"] = faction_stats["kills"] / max(
            1, faction_stats["losses"]
        )
        faction_stats["damage_ratio"] = faction_stats["damage_dealt"] / max(
            1, faction_stats["damage_taken"]
        )
        faction_stats["win_rate"] = faction_stats["battles_won"] / max(
            1, faction_stats["battles_won"] + faction_stats["battles_lost"]
        )
        return faction_stats

    def _get_performance_metrics(self, mode_stats: GameModeStatistics) -> Dict:
        """Get performance metrics"""
        if mode_stats.current_mode == "turn_based":
            return {
                "mode": "turn_based",
                "avg_turn_duration": mode_stats.turn_based_stats[
                    "average_turn_duration"
                ],
                "total_turns": mode_stats.turn_based_stats["total_turns"],
                "actions_per_turn": mode_stats.actions_this_turn,
                "efficiency": mode_stats.actions_this_turn
                / max(1, mode_stats.turn_based_stats["average_turn_duration"]),
            }
        else:
            return {
                "mode": "realtime",
                "game_time": mode_stats.realtime_stats["total_game_time"],
                "actions_per_minute": mode_stats.actions_this_minute,
                "total_actions": sum(
                    mode_stats.realtime_stats["faction_activity"].values()
                ),
                "activity_level": (
                    "high"
                    if mode_stats.actions_this_minute > 10
                    else "medium" if mode_stats.actions_this_minute > 5 else "low"
                ),
            }

    def _collect_unit_statistics(self) -> Dict:
        """Collect unit statistics information"""
        unit_stats_summary = {}
        for entity in self.world.query().with_all(Unit, UnitStatistics).entities():
            unit = self.world.get_component(entity, Unit)
            unit_stats = self.world.get_component(entity, UnitStatistics)

            if unit and unit_stats:
                faction_key = unit.faction.value
                if faction_key not in unit_stats_summary:
                    unit_stats_summary[faction_key] = {
                        "total_kills": 0,
                        "total_damage": 0,
                        "total_moves": 0,
                        "total_battles": 0,
                        "unit_count": 0,
                    }

                faction_summary = unit_stats_summary[faction_key]
                faction_summary["total_kills"] += unit_stats.kills
                faction_summary["total_damage"] += unit_stats.damage_dealt
                faction_summary["total_moves"] += unit_stats.moves_made
                faction_summary["total_battles"] += unit_stats.battles_participated
                faction_summary["unit_count"] += 1

        return unit_stats_summary

    def get_unit_visibility_summary(self, unit_entity: int) -> Dict:
        """Get unit visibility summary"""
        visibility_tracker = self.world.get_singleton_component(VisibilityTracker)
        if (
            not visibility_tracker
            or unit_entity not in visibility_tracker.visibility_history
        ):
            return {}

        history = visibility_tracker.visibility_history[unit_entity]
        if not history:
            return {}

        total_time = (
            history[-1]["timestamp"] - history[0]["timestamp"]
            if len(history) > 1
            else 0
        )
        visible_time = 0
        sight_changes = 0

        for i, record in enumerate(history):
            if record["visible_to"]:
                if i < len(history) - 1:
                    visible_time += history[i + 1]["timestamp"] - record["timestamp"]

            if i > 0 and len(record["visible_to"]) != len(history[i - 1]["visible_to"]):
                sight_changes += 1

        return {
            "total_time": total_time,
            "visible_time": visible_time,
            "visibility_ratio": visible_time / max(1, total_time),
            "sight_changes": sight_changes,
            "currently_visible_to": history[-1]["visible_to"] if history else [],
        }
