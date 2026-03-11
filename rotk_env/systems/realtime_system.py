"""
Real-time system - manages real-time game mode logic.
"""

from framework import System, World
from ..components import (
    Unit,
    UnitCount,
    MovementPoints,
    Combat,
    Player,
    GameState,
    GameModeComponent,
    GameStats,
)
from ..prefabs.config import GameConfig, GameMode, Faction


class RealtimeSystem(System):
    """Real-time system - manages real-time game mode logic."""

    def __init__(self):
        super().__init__(required_components={Player}, priority=85)
        self.ai_decision_timer = 0.0
        self.ai_decision_interval = 1.0  # AI makes one resource-recovery decision per second

    def initialize(self, world: World) -> None:
        self.world = world

    def subscribe_events(self):
        pass

    def update(self, delta_time: float) -> None:
        game_mode = self.world.get_singleton_component(GameModeComponent)
        game_state = self.world.get_singleton_component(GameState)

        if not game_mode or not game_mode.is_real_time():
            return

        if not game_state or game_state.game_over:
            return

        # Check win/loss conditions.
        if self._check_game_over():
            return

        # Handle combat cooldowns.
        self._handle_attack_cooldowns(delta_time)

        # Per-tick AI decision update.
        self._update_ai_decisions(delta_time)

    def _check_game_over(self) -> bool:
        """Check win/loss conditions."""
        game_state = self.world.get_singleton_component(GameState)
        if not game_state or game_state.game_over:
            return True

        # Check whether any faction has run out of units.
        factions_with_units = set()
        faction_unit_counts = {}

        for entity in self.world.query().with_all(Unit, UnitCount).entities():
            unit = self.world.get_component(entity, Unit)
            unit_count = self.world.get_component(entity, UnitCount)

            # Only count units with troops remaining.
            if unit and unit_count and unit_count.current_count > 0:
                factions_with_units.add(unit.faction)
                faction_unit_counts[unit.faction] = (
                    faction_unit_counts.get(unit.faction, 0) + 1
                )

        # End the game when fewer than 2 factions still have units.
        if len(factions_with_units) < 2:
            game_state.game_over = True
            if factions_with_units:
                game_state.winner = list(factions_with_units)[0]

            # Record end-of-game statistics.
            statistics_system = self._get_statistics_system()
            if statistics_system:
                # Record end-of-game statistics here if needed.
                pass

            return True

        # Check whether the maximum round count has been reached.
        if (
            hasattr(game_state, "max_turns")
            and game_state.turn_number >= game_state.max_turns
        ):
            game_state.game_over = True
            return True

        return False

    def _get_statistics_system(self):
        """Get the StatisticsSystem instance."""
        for system in self.world.systems:
            if system.__class__.__name__ == "StatisticsSystem":
                return system
        return None

    def _handle_attack_cooldowns(self, delta_time: float) -> None:
        """Handle combat-related cooldown logic."""
        for entity in self.world.query().with_component(Combat).entities():
            combat = self.world.get_component(entity, Combat)

            if combat and combat.has_attacked:
                if not hasattr(combat, "attack_cooldown"):
                    combat.attack_cooldown = 0.5  # 0.5-second attack cooldown to increase attack frequency
                else:
                    combat.attack_cooldown -= delta_time
                    if combat.attack_cooldown <= 0:
                        combat.has_attacked = False
                        combat.attack_cooldown = 0.0

    def _update_ai_decisions(self, delta_time: float) -> None:
        """Per-tick AI decision update for real-time mode."""
        self.ai_decision_timer += delta_time

        if self.ai_decision_timer >= self.ai_decision_interval:
            self.ai_decision_timer = 0.0

            # Trigger AI decision-making.
            self._boost_ai_units()

    def _boost_ai_units(self):
        """Grant AI units additional action opportunities."""
        from ..components import AIControlled

        for entity in self.world.query().with_all(Unit, AIControlled).entities():
            movement = self.world.get_component(entity, MovementPoints)
            combat = self.world.get_component(entity, Combat)
            unit_count = self.world.get_component(entity, UnitCount)

            # Only boost units with troops remaining.
            if not unit_count or unit_count.current_count <= 0:
                continue

            # Give AI units a small bonus to action capacity.
            if movement and unit_count:
                max_movement = movement.get_effective_movement(unit_count)
                if movement.current_mp < max_movement:
                    movement.current_mp = min(
                        max_movement, movement.current_mp + 0.2  # grant extra action capacity
                    )

            # Reduce AI unit attack cooldown.
            if combat and hasattr(combat, "attack_cooldown"):
                combat.attack_cooldown = max(
                    0, combat.attack_cooldown - 0.8
                )  # larger cooldown reduction
