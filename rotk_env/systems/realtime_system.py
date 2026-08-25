"""
Real-time system - manages real-time game mode logic.
"""

from framework import System, World
from ..components import (
    Combat,
    Player,
    GameState,
    GameModeComponent,
)
from .game_over_policy import GameOverPolicy


class RealtimeSystem(System):
    """Real-time system - manages real-time game mode logic."""

    def __init__(self):
        super().__init__(required_components={Player}, priority=85)

    def initialize(self, world: World) -> None:
        self.world = world
        self._game_over_policy = GameOverPolicy(world)

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

    def _check_game_over(self) -> bool:
        return self._game_over_policy.apply()

    def _handle_attack_cooldowns(self, delta_time: float) -> None:
        """Handle combat-related cooldown logic."""
        for entity in self.world.query().with_component(Combat).entities():
            combat = self.world.get_component(entity, Combat)

            if combat and combat.has_attacked:
                combat.attack_cooldown -= delta_time
                if combat.attack_cooldown <= 0:
                    combat.has_attacked = False
                    combat.attack_cooldown = 0.0
