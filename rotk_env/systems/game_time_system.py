"""
Game time system - unified management of game time
"""

from framework import System, World
from ..components import GameTime, GameModeComponent, GameState, TurnManager
from ..prefabs.config import GameMode


class GameTimeSystem(System):
    """Game time system - provides unified time management"""

    def __init__(self):
        super().__init__(priority=10)  # Runs early, providing time service to other systems

    def initialize(self, world: World) -> None:
        """Initialize the game time system"""
        self.world = world

        # Ensure the GameTime component exists
        game_time = world.get_singleton_component(GameTime)
        if not game_time:
            game_time = GameTime()
            world.add_singleton_component(game_time)

        # Initialize based on the current game mode
        game_mode = world.get_singleton_component(GameModeComponent)
        if game_mode:
            game_time.initialize(game_mode.mode)
        else:
            game_time.initialize(GameMode.TURN_BASED)

    def subscribe_events(self):
        """Subscribe to events"""
        pass

    def update(self, delta_time: float) -> None:
        """Update the game time"""
        game_time = self.world.get_singleton_component(GameTime)
        if game_time:
            game_time.update(delta_time)

            # Sync turn number (if in turn-based mode)
            if game_time.is_turn_based():
                self._sync_turn_number(game_time)

    def _sync_turn_number(self, game_time: GameTime):
        """Sync turn number with game state"""
        game_state = self.world.get_singleton_component(GameState)
        if game_state and game_state.turn_number != game_time.current_turn:
            # If the game state's turn number has changed, sync it to the time system
            if game_state.turn_number > game_time.current_turn:
                game_time.current_turn = game_state.turn_number
                game_time.turn_start_time = game_time.last_update_time

    def advance_turn(self):
        """Advance to the next turn (called by the turn system)"""
        game_time = self.world.get_singleton_component(GameTime)
        if game_time:
            game_time.advance_turn()

    def pause_game(self):
        """Pause the game time"""
        game_time = self.world.get_singleton_component(GameTime)
        if game_time:
            game_time.pause()

    def resume_game(self):
        """Resume the game time"""
        game_time = self.world.get_singleton_component(GameTime)
        if game_time:
            game_time.resume()

    def set_time_scale(self, scale: float):
        """Set the time scale"""
        game_time = self.world.get_singleton_component(GameTime)
        if game_time:
            game_time.set_time_scale(scale)

    def get_current_time_display(self) -> str:
        """Get the current time display string"""
        game_time = self.world.get_singleton_component(GameTime)
        if game_time:
            return game_time.get_current_time_display()
        return "00:00"

    def get_current_turn(self) -> int:
        """Get the current turn number"""
        game_time = self.world.get_singleton_component(GameTime)
        if game_time:
            return game_time.current_turn
        return 1
