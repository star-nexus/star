"""
Turn system - manages turn-based game logic (per rulebook v1.2).
"""

from framework import System, World
from framework.engine.events import EBS
from ..components import (
    Player,
    GameState,
    MovementPoints,
    Combat,
    Unit,
    GameModeComponent,
    ActionPoints,
    UnitCount,
)
from ..prefabs.config import GameConfig, GameMode, Faction
from ..utils.env_events import TurnStartEvent


class TurnSystem(System):
    """Turn system - focused on turn-based game-loop logic."""

    def __init__(self):
        super().__init__(required_components={Player}, priority=90)
        self.turn_timer = 0.0
        self.auto_turn_duration = 30.0  # auto-end-turn timeout in seconds

    def initialize(self, world: World) -> None:
        self.world = world

        # Check if a GameState component already exists.
        game_state = self.world.get_singleton_component(GameState)
        if not game_state:
            # None found; create a default GameState.
            game_state = GameState(
                current_player=Faction.WEI,
                turn_number=1,
                game_over=False,
                max_turns=GameConfig.MAX_TURNS,
            )
            self.world.add_singleton_component(game_state)

        # Set the first active player.
        self._start_next_turn()

    def subscribe_events(self):
        pass

    def update(self, delta_time: float) -> None:
        game_mode = self.world.get_singleton_component(GameModeComponent)
        game_state = self.world.get_singleton_component(GameState)

        # Only runs in turn-based game mode.
        if not game_mode or not game_mode.is_turn_based():
            return

        if not game_state or game_state.game_over:
            return

        self._update_turn_based(delta_time)

    def _update_turn_based(self, delta_time: float) -> None:
        """Update turn-based mode logic."""
        # Check win/loss conditions.
        if self._check_game_over():
            return

    def end_turn(self):
        """End the current turn."""
        # Reset unit action states.
        self._reset_unit_actions()

        # Check win/loss conditions.
        if self._check_game_over():
            return

        # Advance to the next turn.
        self._start_next_turn()

    def agent_end_turn(self):
        """End the current faction's actions and hand off to the next faction."""
        # Check win/loss conditions.
        if self._check_game_over():
            return True

        # Switch to the next faction (without resetting unit states).
        self._switch_to_next_faction()

        # Notify the next agent that its turn has started.
        # self._notify_next_agent_turn()

        return True

    def _switch_to_next_faction(self):
        """Advance to the next faction in rotation."""
        game_state = self.world.get_singleton_component(GameState)
        players = list(self.world.query().with_component(Player).entities())

        if not players:
            return

        # Determine the next player.
        current_index = 0
        if game_state.current_player:
            for i, entity in enumerate(players):
                player = self.world.get_component(entity, Player)
                if player and player.faction == game_state.current_player:
                    current_index = (i + 1) % len(players)
                    break

        # Set the new active player.
        next_player_entity = players[current_index]
        next_player = self.world.get_component(next_player_entity, Player)

        if next_player:
            previous_faction = game_state.current_player
            game_state.current_player = next_player.faction

            print(
                f"🔄 Faction turn: {previous_faction.value} -> {next_player.faction.value}"
            )

            # Record the faction change in the statistics system.
            statistics_system = self._get_statistics_system()
            if statistics_system:
                statistics_system.record_turn_change(
                    previous_faction, next_player.faction
                )

            # When we cycle back to the first player (index 0), all factions have acted — start a new round.
            if current_index == 0:
                game_state.turn_number += 1
                print(f"🔄 New round started: round {game_state.turn_number}")

                # Only reset all units' action states at the start of a new round.
                self._reset_unit_actions()

            # Reset the turn timer.
            self.turn_timer = 0.0

            # Publish turn-start event.
            EBS.publish(TurnStartEvent(game_state.current_player))

    def _reset_unit_actions(self):
        """Reset all units' action states."""
        # Retrieve ActionSystem to reset turn actions.
        action_system = self._get_action_system()
        if action_system:
            action_system.reset_turn_actions()
        else:
            # Fallback: reset directly.
            self._manual_reset_actions()

    def _manual_reset_actions(self):
        """Manually reset action states."""
        for entity in self.world.query().with_component(MovementPoints).entities():
            movement = self.world.get_component(entity, MovementPoints)
            unit_count = self.world.get_component(entity, UnitCount)
            action_points = self.world.get_component(entity, ActionPoints)

            if movement:
                # First restore movement to maximum.
                movement.reset()
                # Then scale by effective movement given unit count.
                if unit_count:
                    effective_mp = movement.get_effective_movement(unit_count)
                    movement.current_mp = effective_mp
                # movement.has_moved = False  # single-move restriction removed

            if action_points:
                action_points.reset()

        for entity in self.world.query().with_component(Combat).entities():
            combat = self.world.get_component(entity, Combat)
            if combat:
                pass  # combat.has_attacked = False  # single-attack restriction removed

    def _start_next_turn(self):
        """Start the next turn with a full reset (used at game start, etc.)."""
        game_state = self.world.get_singleton_component(GameState)
        players = list(self.world.query().with_component(Player).entities())

        if not players:
            return

        # Determine the next player.
        current_index = 0
        if game_state.current_player:
            for i, entity in enumerate(players):
                player = self.world.get_component(entity, Player)
                if player and player.faction == game_state.current_player:
                    current_index = (i + 1) % len(players)
                    break

        # Set the new active player.
        next_player_entity = players[current_index]
        next_player = self.world.get_component(next_player_entity, Player)

        if next_player:
            previous_faction = game_state.current_player
            game_state.current_player = next_player.faction

            print(f"🎮 Game start: {game_state.current_player.value} acts first")

            # Record the turn change in the statistics system.
            statistics_system = self._get_statistics_system()
            if statistics_system:
                statistics_system.record_turn_change(
                    previous_faction, next_player.faction
                )

            # If we've looped back to the first player, increment the round counter.
            if current_index == 0:
                game_state.turn_number += 1

            # Reset the turn timer.
            self.turn_timer = 0.0

            # Publish turn-start event.
            EBS.publish(TurnStartEvent(game_state.current_player))

    # def _notify_next_agent_turn(self):
    #     """Notify the next agent that its turn has started."""
    #     game_state = self.world.get_singleton_component(GameState)
    #     if not game_state:
    #         return

    #     # Retrieve the LLM system to dispatch notifications.
    #     llm_system = self._get_llm_system()
    #     if llm_system and hasattr(llm_system, "client"):
    #         try:
    #             # Build the start_turn message.
    #             start_turn_message = {
    #                 "type": "start_turn",
    #                 "data": {
    #                     "faction": game_state.current_player.value,
    #                     "turn_number": game_state.turn_number,
    #                     "timestamp": self._get_current_timestamp(),
    #                     "message": f"It's {game_state.current_player.value}'s turn to act",
    #                 },
    #             }

    #             # Dispatch to all connected agents.
    #             for agent_id in llm_system.client.connected_agents:
    #                 llm_system.client.send_message(
    #                     start_turn_message, target={"type": "agent", "id": agent_id}
    #                 )

    #             print(
    #                 f"📢 Turn-start notification sent to agents: {game_state.current_player.value}"
    #             )

    #         except Exception as e:
    #             print(f"❌ Failed to send turn-start notification: {e}")

    def _get_current_timestamp(self):
        """Return the current Unix timestamp."""
        import time

        return time.time()

    def _get_statistics_system(self):
        """Get the StatisticsSystem instance."""
        for system in self.world.systems:
            if system.__class__.__name__ == "StatisticsSystem":
                return system
        return None

    def _get_action_system(self):
        """Get the ActionSystem instance."""
        for system in self.world.systems:
            if system.__class__.__name__ == "ActionSystem":
                return system
        return None

    # def _get_llm_system(self):
    #     """Get the LLMSystem instance."""
    #     for system in self.world.systems:
    #         if system.__class__.__name__ == "LLMSystem":
    #             return system
    #     return None

    def _check_game_over(self) -> bool:
        """Check whether the game is over."""
        game_state = self.world.get_singleton_component(GameState)

        # Check the turn limit.
        if game_state.turn_number > game_state.max_turns:
            game_state.game_over = True
            return True

        # Check whether only one faction still has units.
        factions_with_units = set()
        for entity in self.world.query().with_component(Unit).entities():
            unit = self.world.get_component(entity, Unit)
            unit_count = self.world.get_component(entity, UnitCount)

            # Only count units with troops remaining.
            if unit and unit_count and unit_count.current_count > 0:
                factions_with_units.add(unit.faction)

        if len(factions_with_units) <= 1:
            game_state.game_over = True
            if factions_with_units:
                game_state.winner = list(factions_with_units)[0]
            return True

        return False
