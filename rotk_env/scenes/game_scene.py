"""
Main game scene
"""

import pygame
import time
from typing import Dict, Any
from framework.engine.scenes import Scene, SMS
from framework import World
from ..prefabs.config import Faction
from ..systems import (
    AnimationSystem,
    MapSystem,
    TurnSystem,
    RealtimeSystem,
    MovementSystem,
    CombatSystem,
    VisionSystem,
    AISystem,
    InputHandlingSystem,
    MiniMapSystem,
    TerritorySystem,
    UnitActionButtonSystem,
    ActionSystem,
    UIButtonSystem,
    UIRenderSystem,
    MockLLMAISystem,
)
from ..systems.map_render_system import MapRenderSystem
from ..systems.unit_render_system import UnitRenderSystem

# from ..systems.improved_ui_render_system import ImprovedUIRenderSystem
# from ..systems.improved_ui_button_system import ImprovedUIButtonSystem
from ..systems.effect_render_system import EffectRenderSystem
from ..systems.panel_render_system import PanelRenderSystem
from ..systems.statistics_system import StatisticsSystem
from ..systems.game_time_system import GameTimeSystem
from ..systems.llm_system import LLMSystem
from ..systems.resource_recovery_system import ResourceRecoverySystem
from ..systems.settlement_report_system import SettlementReportSystem
from ..utils.hex_utils import HexMath
from ..components.settlement_report import SettlementReport
from ..components import (
    GameState,
    UIState,
    InputState,
    FogOfWar,
    GameStats,
    Player,
    AIControlled,
    Unit,
    UnitCount,
    MovementPoints,
    ActionPoints,
    AttackPoints,
    ConstructionPoints,
    SkillPoints,
    Combat,
    Vision,
    HexPosition,
    MiniMap,
    GameModeComponent,
    UnitStatus,
    UnitSkills,
    MovementAnimation,
    BattleLog,
    UnitObservation,
    UnitStatistics,
    VisibilityTracker,
    GameModeStatistics,
    UIButton,
    UIButtonCollection,
    UIPanel,
    TurnManager,
)
from ..prefabs.config import Faction, PlayerType, GameConfig, UnitType, GameMode
from performance_profiler import profiler


class GameScene(Scene):
    """Main game scene"""

    def __init__(self, engine):
        super().__init__(engine)
        self.name = "game"
        self.world = World()

        # Default configuration, will be overridden in enter
        self.players = {Faction.WEI: PlayerType.HUMAN, Faction.SHU: PlayerType.AI}
        self.game_mode = GameMode.TURN_BASED  # Default game mode

        # Initialization flag
        self.initialized = False

        # 🆕 Game end waiting state
        self.game_end_wait_start = None
        self.game_end_wait_timeout = 15.0  # Maximum wait time for 5 seconds

    def enter(self, **kwargs):
        """Called when entering the scene"""
        super().enter(**kwargs)

        # Get configuration from kwargs
        self.players = kwargs.get(
            "players", {Faction.WEI: PlayerType.HUMAN, Faction.SHU: PlayerType.AI}
        )

        mode = kwargs.get("mode", GameMode.TURN_BASED)
        if isinstance(mode, str):
            try:
                mode = GameMode(mode)
            except ValueError:
                mode = GameMode.TURN_BASED
        self.game_mode = mode

        headless = kwargs.get("headless", False)
        self.headless = headless

        # Get scene parameters (optional)
        self.scenario = kwargs.get("scenario", "default")

        if not self.initialized:
            self._initialize_game()
            self.initialized = True

    def _initialize_game(self):
        """Initialize game"""
        # First initialize game mode component
        self._initialize_game_mode()

        # 🆕 Initialize Agent info registry
        self._initialize_agent_registry()

        # Initialize systems
        self._initialize_systems()

        # Initialize players
        self._initialize_players()

        # Initialize units
        # for wei, shu, wu: infantry, archer, cavalry
        self._initialize_units([[1, 3, 1], [1, 3, 1], [1, 3, 1]])

        # Initialize game statistics
        self._initialize_stats()

        # Initialize minimap
        self._initialize_minimap()

    def _initialize_systems(self):
        """Initialize all game systems"""
        # Add systems in order of priority

        systems = [
            GameTimeSystem(),  # Game time system (priority 10) - earliest execution
            MapSystem(),  # Map system (priority 100)
            VisionSystem(),  # Vision system
            ActionSystem(),  # Action system
            MovementSystem(),  # Movement system
            CombatSystem(),  # Combat system
            TerritorySystem(),  # Territory system
            ResourceRecoverySystem(),  # Resource recovery system
            # MockLLMAISystem(),  # Mock LLM AI system - new AI using LLM Action Handler V3
            LLMSystem(),  # LLM system (priority 5)
            StatisticsSystem(),  # Statistics system
            AnimationSystem(),  # Animation system (priority 15)
            InputHandlingSystem(),  # Input system (priority 10)
            UnitActionButtonSystem(),  # Unit action button system (priority 4)
            # Render systems are split into multiple independent systems (from lowest to highest layer)
            MapRenderSystem(),  # Map render system (lowest layer)
            UnitRenderSystem(),  # Unit render system (above map)
            EffectRenderSystem(),  # Effect render system (above unit)
            PanelRenderSystem(),  # Panel render system (above effect)
            UIButtonSystem(),  # Improved UI button system (priority 2)
            UIRenderSystem(),  # Improved UI render system (top layer)
            MiniMapSystem(),  # MiniMap system (priority 5)
            SettlementReportSystem(),  # Settlement report system (priority 200, executed after game ends)
        ]
        if self.game_mode == GameMode.REAL_TIME:
            systems.append(RealtimeSystem())
        else:
            systems.append(TurnSystem())

        for system in systems:
            self.world.add_system(system)

    def _initialize_game_mode(self):
        """Initialize game mode component"""
        game_mode = GameModeComponent(mode=self.game_mode)
        self.world.add_singleton_component(game_mode)

    def _initialize_players(self):
        """Initialize players"""

        # Initialize turn manager
        turn_manager = TurnManager()
        self.world.add_singleton_component(turn_manager)

        for faction, player_type in self.players.items():
            # Create player entity
            player_entity = self.world.create_entity()

            # Add player component
            player_comp = Player(
                faction=faction,
                player_type=player_type,
                color=GameConfig.FACTION_COLORS[faction],
                units=set(),
            )
            self.world.add_component(player_entity, player_comp)

            # If AI player, add AI control component
            if player_type == PlayerType.AI:
                self.world.add_component(player_entity, AIControlled())

            # Add player to turn manager
            turn_manager.add_player(player_entity)

    def _initialize_units(self, unit_assignments: list[list[int]]):
        """Initialize units - automatically generate units and positions based on quantity"""

        # Define the starting area center for each faction
        faction_centers = {
            Faction.WEI: (3, 3),
            Faction.SHU: (-3, -3),
            Faction.WU: (3, -3),
        }

        # Define unit quantity (only process factions participating in the game)
        unit_counts = {}
        for faction in self.players.keys():
            if faction == Faction.WEI:
                unit_counts[faction] = unit_assignments[0]
            elif faction == Faction.SHU:
                unit_counts[faction] = unit_assignments[1]
            elif faction == Faction.WU:
                unit_counts[faction] = unit_assignments[2]

        # 🆕 Record initial unit count to GameStats (ensure GameStats exists)
        game_stats = self.world.get_singleton_component(GameStats)
        if not game_stats:
            # If GameStats does not exist, create a temporary one, it will be correctly initialized when _initialize_stats is called
            print(
                "[GameScene] ⚠️ GameStats component does not exist, waiting for subsequent initialization..."
            )
            pass

        # Temporarily store the initial unit count, write it to GameStats in _initialize_stats
        self._temp_initial_unit_counts = {}
        for faction, count in unit_counts.items():
            total_units = sum(count)
            self._temp_initial_unit_counts[faction] = total_units
            print(
                f"[GameScene] Preparing to record {faction.value} faction initial unit count: {total_units}"
            )

        for faction, count in unit_counts.items():
            if sum(count) == 0:
                continue

            player_entity = self._get_player_entity(faction)
            if not player_entity:
                continue

            player = self.world.get_component(player_entity, Player)
            center_col, center_row = faction_centers[faction]

            # Generate all unit positions for this faction
            positions = self._generate_unit_positions_simple(
                center_col, center_row, sum(count), faction
            )

            # Generate diverse unit types
            unit_types = self._generate_unit_types(count)
            if len(unit_types) > 1 and faction == Faction.WEI:
                unit_types[0], unit_types[1] = unit_types[1], unit_types[0]
                unit_types[2], unit_types[-1] = unit_types[-1], unit_types[2]

            for i, ((q, r), unit_type) in enumerate(zip(positions, unit_types)):
                unit_entity = self._create_unit(
                    faction=faction,
                    unit_type=unit_type,
                    position=(q, r),
                    name=f"{faction.value}_{unit_type.value}_{i+1}",
                )
                player.units.add(unit_entity)


    def _generate_unit_positions_simple(
        self, center_col: int, center_row: int, count: int, faction: Faction
    ) -> list:
        """Generate unit positions based on count - uses spiral distribution from center"""
        # Use the existing _generate_unit_positions method which properly handles count
        if faction == Faction.WEI:
            return [(1, 3), (2, 3), (1, 4), (2, 4), (3, 3)]
        elif faction == Faction.SHU:
            return [(-2,-3), (-1,-4), (-3,-4), (-2,-4), (-1, -5)]
        elif faction == Faction.WU:
            return [(1, -3), (2, -3), (1, -4), (2, -4), (3, -3)]
        else:
            return self._generate_unit_positions(center_col, center_row, count)
        # return self._generate_unit_positions(center_col, center_row, count)


    def _generate_unit_positions(
        self, center_col: int, center_row: int, count: int
    ) -> list:
        """Generate unit positions - based on the center point, spiral distribution"""
        positions = []
        if count == 0:
            return []

        if count == 1:
            return [(center_col, center_row)]

        # The first unit is placed in the center
        positions.append((center_col, center_row))
        remaining = count - 1

        # Six hexagon directions (flat-top orientation)
        hex_directions = [(1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1)]

        radius = 1
        while remaining > 0 and radius <= 5:  # Limit maximum radius
            # Current ring position count
            positions_in_ring = min(remaining, 6 * radius)

            # Uniformly distribute positions on the current ring
            for i in range(positions_in_ring):
                if i < 6:  # First layer (6 directions each)
                    dq, dr = hex_directions[i]
                    col = center_col + dq * radius
                    row = center_row + dr * radius
                else:  # Fill edges
                    # Add extra positions on the hexagon edges
                    side = (i - 6) // radius
                    pos_on_side = (i - 6) % radius

                    if side < 6:
                        dq1, dr1 = hex_directions[side]
                        dq2, dr2 = hex_directions[(side + 1) % 6]

                        # Interpolate on the edges
                        t = (pos_on_side + 1) / (radius + 1)
                        col = center_col + int(dq1 * radius * (1 - t) + dq2 * radius * t)
                        row = center_row + int(dr1 * radius * (1 - t) + dr2 * radius * t)
                    else:
                        break

                positions.append((col, row))
                remaining -= 1

                if remaining <= 0:
                    break

            radius += 1

        return positions[:count]

    def _generate_unit_types(self, count: int | list) -> list:
        """Generate diverse unit type combinations"""

        unit_types = []

        if isinstance(count, list) and len(count) == 3:
            # count is a 3 element list [infantry count, archer count, cavalry count]
            infantry_count, archer_count, cavalry_count = count
            unit_types = []

            # Add specified number of each type of unit
            unit_types.extend([UnitType.INFANTRY] * infantry_count)
            unit_types.extend([UnitType.ARCHER] * archer_count)
            unit_types.extend([UnitType.CAVALRY] * cavalry_count)

            return unit_types

        base_ratios = {
            UnitType.INFANTRY: 0.50,
            UnitType.CAVALRY: 0.30,
            UnitType.ARCHER: 0.20,
        }

        # Calculate the number of each type of unit based on the quantity
        for unit_type, ratio in base_ratios.items():
            type_count = max(1, int(count * ratio)) if count >= 4 else 1
            unit_types.extend([unit_type] * type_count)

        # If the total is not enough, use infantry to supplement
        while len(unit_types) < count:
            unit_types.append(UnitType.INFANTRY)

        # If it exceeds, remove the extra (remove archers first)
        while len(unit_types) > count:
            for remove_type in [UnitType.ARCHER, UnitType.CAVALRY]:
                if remove_type in unit_types:
                    unit_types.remove(remove_type)
                    break
            else:
                unit_types.pop()

        # Shuffle the order
        # random.shuffle(unit_types)
        return unit_types

    def _create_unit(
        self, faction: Faction, unit_type: UnitType, position: tuple, name: str = ""
    ) -> int:
        """Create unit"""

        unit_entity = self.world.create_entity()

        # Set attributes based on unit type
        unit_stats = GameConfig.UNIT_STATS[unit_type]

        self.world.add_component(
            unit_entity, Unit(unit_type=unit_type, faction=faction, name=name)
        )

        self.world.add_component(unit_entity, HexPosition(position[0], position[1]))
        self.world.add_component(
            unit_entity,
            UnitCount(
                current_count=unit_stats.max_count, max_count=unit_stats.max_count
            ),
        )
        self.world.add_component(
            unit_entity,
            MovementPoints(
                base_mp=unit_stats.movement,
                current_mp=unit_stats.movement,
                max_mp=unit_stats.movement,
            ),
        )

        game_mode_comp = self.world.get_singleton_component(GameModeComponent)
        is_turn_based = game_mode_comp and game_mode_comp.mode == GameMode.TURN_BASED
        ap = 2 if is_turn_based else 1

        self.world.add_component(
            unit_entity,
            ActionPoints(
                current_ap=ap,
                max_ap=ap,
            ),
        )
        self.world.add_component(
            unit_entity,
            AttackPoints(
                normal_attacks=1,  # Default attack times
                max_normal_attacks=1,
            ),
        )
        self.world.add_component(
            unit_entity,
            ConstructionPoints(
                current_cp=1,  # Default construction points
                max_cp=1,
            ),
        )
        self.world.add_component(
            unit_entity,
            SkillPoints(
                current_sp=1,  # Default skill points
                max_sp=1,
            ),
        )
        self.world.add_component(
            unit_entity,
            Combat(
                base_attack=unit_stats.base_attack,
                base_defense=unit_stats.base_defense,
                attack_range=unit_stats.attack_range,
            ),
        )
        self.world.add_component(unit_entity, Vision(range=unit_stats.vision_range))
        self.world.add_component(unit_entity, UnitStatus(current_status="normal"))

        # Add skill component
        self.world.add_component(unit_entity, UnitSkills())

        return unit_entity

    def _get_player_entity(self, faction: Faction) -> int:
        """Get the player entity for the specified faction"""

        for entity in self.world.query().with_component(Player).entities():
            player = self.world.get_component(entity, Player)
            if player and player.faction == faction:
                return entity
        return None

    def _initialize_stats(self):
        """Initialize game statistics component - pure data initialization"""

        # Initialize game statistics component
        stats = GameStats()
        stats.game_start_time = time.time()

        # 🆕 Write the previously recorded initial unit count to GameStats
        if hasattr(self, "_temp_initial_unit_counts"):
            stats.initial_unit_counts = self._temp_initial_unit_counts.copy()
            print(
                f"[GameScene] ✅ The initial unit count has been written to GameStats: {stats.initial_unit_counts}"
            )
        else:
            print("[GameScene] ⚠️ The temporary initial unit count record was not found")

        self.world.add_singleton_component(stats)

        # Initialize battle log
        battle_log = BattleLog()
        battle_log.add_entry("Game Start", "turn", "", (0, 255, 0))
        battle_log.add_entry("Wei Faction Turn Start", "turn", "wei", (255, 100, 100))
        self.world.add_singleton_component(battle_log)

        # Initialize visibility tracker
        visibility_tracker = VisibilityTracker()
        self.world.add_singleton_component(visibility_tracker)

        # Initialize game mode statistics
        game_mode_stats = GameModeStatistics(current_mode=self.game_mode.value)
        self.world.add_singleton_component(game_mode_stats)

        # Initialize game state
        from ..prefabs.config import GameMode

        first_faction = list(self.players.keys())[0] if self.players else Faction.WEI
        game_state = GameState(
            current_player=first_faction,
            turn_number=1,
            game_mode=self.game_mode,
            game_over=False,
            winner=None,
            max_turns=GameConfig.MAX_TURNS,
        )
        self.world.add_singleton_component(game_state)

        # Initialize other singleton components
        self.world.add_singleton_component(UIState())
        self.world.add_singleton_component(InputState())
        self.world.add_singleton_component(FogOfWar())

        # Initialize fog of war
        self.world.add_singleton_component(FogOfWar())

    def update(self, delta_time: float) -> None:
        """Update scene"""
        if self.is_active:
            # Check exit event
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.engine.quit()
                    return

            # Update world
            with profiler.time_system("world_update"):
                self.world.update(delta_time)

            # 🆕 Check game end - wait for settlement report to complete before switching scene
            game_state = self.world.get_singleton_component(GameState)
            if game_state and game_state.game_over:
                # Record wait start time
                if self.game_end_wait_start is None:
                    import time

                    self.game_end_wait_start = time.time()
                    print("[GameScene] 🏁 Game End, waiting for settlement report...")

                # Check if the settlement report has been completed
                settlement_report = self.world.get_singleton_component(SettlementReport)
                if settlement_report:
                    # Settlement report generated, can switch scene
                    print(
                        "[GameScene] ✅ Settlement report generated, switching to game over scene"
                    )
                    self._switch_to_game_over(game_state)
                else:
                    # Check if it is timeout
                    import time

                    elapsed = time.time() - self.game_end_wait_start
                    if elapsed >= self.game_end_wait_timeout:
                        print(
                            f"[GameScene] ⏰ Waiting for settlement report timeout ({elapsed:.1f}s), switching to game over scene"
                        )
                        self._switch_to_game_over(game_state)
                    else:
                        # Wait for settlement report generation (output progress once per second)
                        if int(elapsed) != getattr(self, "_last_wait_second", -1):
                            remaining = self.game_end_wait_timeout - elapsed
                            print(
                                f"[GameScene] ⏳ Waiting for settlement report generation... {elapsed:.1f}s / {self.game_end_wait_timeout}s (remaining {remaining:.1f}s)"
                            )
                            self._last_wait_second = int(elapsed)

    def _switch_to_game_over(self, game_state):
        """Switch to game over scene"""
        # Collect statistics data
        statistics = self._collect_game_statistics()

        # Switch to game over scene, pass statistics data
        if self.headless:
            # Print statistics data in headless mode
            print(f"Game End, Winner: {game_state.winner}, \nStatistics: {statistics}")
        else:
            SMS.switch_to("game_over", winner=game_state.winner, statistics=statistics)

    def _collect_game_statistics(self) -> Dict[str, Any]:
        """Collect game statistics data"""
        from ..components import Unit, UnitCount, GameTime, GameState

        total_units = 0
        surviving_units = 0
        faction_stats = {}

        # Count all units
        for faction in [Faction.WEI, Faction.SHU, Faction.WU]:
            faction_total = 0
            faction_surviving = 0

            for entity in self.world.query().with_component(Unit).entities():
                unit = self.world.get_component(entity, Unit)
                unit_count = self.world.get_component(entity, UnitCount)

                if unit.faction == faction:
                    faction_total += 1
                    total_units += 1

                    if unit_count and unit_count.current_count > 0:
                        faction_surviving += 1
                        surviving_units += 1

            if faction_total > 0:  # Only record factions with units
                faction_stats[faction] = {
                    "total_units": faction_total,
                    "surviving_units": faction_surviving,
                }

        # Get game state information
        total_turns = 0
        game_duration = 0.0

        try:
            game_state = self.world.get_singleton_component(GameState)
            total_turns = game_state.turn_number

            game_time = self.world.get_singleton_component(GameTime)
            game_duration = game_time.get_game_elapsed_seconds()

        except Exception as e:
            print(f"Error occurred while retrieving game state: {e}")

        return {
            "total_turns": total_turns,
            "game_duration": game_duration,
            "total_units": total_units,
            "surviving_units": surviving_units,
            "faction_stats": faction_stats,
        }

    def _initialize_minimap(self):
        """Initialize minimap"""
        minimap = MiniMap(
            visible=True,
            width=200,
            height=150,
            position=(10, 10),
            scale=0.1,
            center_on_camera=True,
            show_units=True,
            show_terrain=True,
            show_fog_of_war=False,  # Minimap does not show fog, can see the global
            show_camera_viewport=True,
            clickable=True,
        )
        self.world.add_singleton_component(minimap)

    def exit(self):
        """Called when exiting scene"""
        super().exit()

        # Clean up world
        self.world.reset()

    def _initialize_agent_registry(self):
        """Initialize Agent info registry"""
        from ..components.agent_info import AgentInfoRegistry

        registry = AgentInfoRegistry()
        self.world.add_singleton_component(registry)
        print("[GameScene] Agent info registry initialized")
