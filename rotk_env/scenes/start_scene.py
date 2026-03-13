"""
Start scene.
"""

import pygame
from typing import Dict, Any, Optional
from framework import (
    World,
    RMS,
    EBS,
    MouseButtonDownEvent,
    MouseMotionEvent,
    Event,
    KeyDownEvent,
    QuitEvent,
)
from framework.engine.scenes import Scene
from ..prefabs.config import Faction, GameConfig, PlayerType, GameMode
from ..components.start_menu import StartMenuConfig, StartMenuButtons, StartMenuOptions
from ..systems.start_scene_render_system import StartSceneRenderSystem


class StartScene(Scene):
    """Start scene."""

    def __init__(self, engine):
        super().__init__(engine)
        self.name = "start"
        self.world = World()
        self.game_config = None  # Configuration passed to GameScene

    def enter(self, **kwargs) -> None:
        """Called when entering the scene."""
        super().enter(**kwargs)
        # Create configuration entity
        self.world.add_singleton_component(StartMenuConfig())

        # Get screen size
        screen_width = GameConfig.WINDOW_WIDTH
        screen_height = GameConfig.WINDOW_HEIGHT
        # Define buttons
        buttons = {
            "start_game": {
                "text": "Start Game",
                "rect": pygame.Rect(
                    screen_width // 2 - 100, screen_height - 150, 200, 50
                ),
                "hover": False,
                "default_color": (60, 80, 120),
                "hover_color": (80, 100, 140),
                "action": self._start_game,
            },
            "quit": {
                "text": "Quit",
                "rect": pygame.Rect(
                    screen_width // 2 - 100, screen_height - 80, 200, 50
                ),
                "hover": False,
                "default_color": (60, 80, 120),
                "hover_color": (80, 100, 140),
                "action": self._quit_game,
            },
        }

        options = {}
        # Create options component

        self.world.add_singleton_component(
            StartMenuButtons(buttons=buttons, options=options)
        )

        # Initialize render system
        self.world.add_system(StartSceneRenderSystem())
        self.subscribe_events()

    def subscribe_events(self) -> None:
        EBS.subscribe(MouseMotionEvent, self._update_hover_state)
        EBS.subscribe(MouseButtonDownEvent, self._handle_mouse_click)
        # EBS.subscribe(KeyDownEvent, self._handle_key_down)

    def update(self, dt: float) -> None:
        """Update the scene."""

        # Update render system
        self.world.update(dt)

    def _update_hover_state(self, event: MouseMotionEvent) -> None:
        """Update hover state."""
        buttons_component = self.world.get_singleton_component(StartMenuButtons)
        if not buttons_component:
            return

        # Update button hover state
        for button_name, button in buttons_component.buttons.items():
            if button["rect"].collidepoint(event.pos):
                button["hover"] = True
            else:
                button["hover"] = False

        # self.render_system.set_hover_button(hover_button)

        # Option hover (not implemented)
        # self._update_option_hover()

    def _update_option_hover(self) -> None:
        """Update option hover state (placeholder)."""
        pass
        # Get screen size
        # screen_width = GameConfig.WINDOW_WIDTH
        # screen_height = GameConfig.WINDOW_HEIGHT
        # # Panel position
        # panel_x = (screen_width - 600) // 2
        # panel_y = 200

        # # Check hover for various options
        # hover_option = None

        # # Game mode options
        # mode_y = panel_y + 70
        # for i, mode in enumerate([GameMode.TURN_BASED, GameMode.REAL_TIME]):
        #     option_rect = pygame.Rect(panel_x + 50 + i * 150, mode_y, 120, 30)
        #     if option_rect.collidepoint(self.mouse_pos):
        #         hover_option = f"mode_{mode.value}"
        #         break

        # # Player configuration options
        # if not hover_option:
        #     player_y = panel_y + 170
        #     for i in range(3):  # Three player configuration options
        #         option_rect = pygame.Rect(panel_x + 50, player_y + i * 30, 200, 30)
        #         if option_rect.collidepoint(self.mouse_pos):
        #             hover_option = f"player_{i}"
        #             break

        # # Scenario options
        # if not hover_option:
        #     scenario_y = panel_y + 270
        #     for i in range(3):  # Three scenario options
        #         option_rect = pygame.Rect(panel_x + 50, scenario_y + i * 30, 200, 30)
        #         if option_rect.collidepoint(self.mouse_pos):
        #             hover_option = f"scenario_{i}"
        #             break

        # self.render_system.set_hover_option(hover_option)

    def _handle_mouse_click(self, event: MouseButtonDownEvent) -> None:
        """Handle mouse click."""
        pos = event.pos
        # Check button clicks
        buttons_component = self.world.get_singleton_component(StartMenuButtons)
        if buttons_component:
            for button_name, button in buttons_component.buttons.items():
                if button["rect"].collidepoint(pos):
                    button["action"]()
                    return

        # Check configuration option clicks
        self._handle_config_click(pos)

    def _handle_config_click(self, pos: tuple) -> None:
        """Handle configuration option clicks."""
        config = self.world.get_singleton_component(StartMenuConfig)
        if not config:
            return

        # Get screen size
        screen_width = GameConfig.WINDOW_WIDTH
        screen_height = GameConfig.WINDOW_HEIGHT
        # Panel position
        panel_x = (screen_width - 600) // 2
        panel_y = 200

        print(
            f"Click position: {pos}, panel position: ({panel_x}, {panel_y})"
        )  # Debug

        # Check game mode option clicks
        mode_y = panel_y + 30 + 60  # panel_y + 30 (y_offset) + 60 (option_y offset)
        for i, mode in enumerate([GameMode.TURN_BASED, GameMode.REAL_TIME]):
            # Vertical layout (kept consistent with render system)
            option_rect = pygame.Rect(panel_x + 50, mode_y + i * 45, 300, 30)
            print(
                f"Mode option {i} ({mode.value}) rect: {option_rect}"
            )  # Debug
            if option_rect.collidepoint(pos):
                config.selected_mode = mode
                print(f"Selected mode: {mode.value}")  # Debug
                return

        # Check player configuration option clicks
        player_y = panel_y + 190 + 60  # panel_y + 190 (y_offset + 160) + 60 (option_y offset)
        player_configs = [
            {Faction.WEI: PlayerType.HUMAN, Faction.SHU: PlayerType.AI},
            {Faction.WEI: PlayerType.AI, Faction.SHU: PlayerType.AI},
            {
                Faction.WEI: PlayerType.AI,
                Faction.SHU: PlayerType.AI,
                Faction.WU: PlayerType.AI,
            },
        ]

        for i, player_config in enumerate(player_configs):
            # 45px spacing (kept consistent with render system)
            option_rect = pygame.Rect(panel_x + 50, player_y + i * 45, 400, 30)
            config_name = ["Human vs AI", "AI vs AI", "Three Kingdoms Mode"][i]
            print(f"Player config {i} ({config_name}) rect: {option_rect}")  # Debug
            if option_rect.collidepoint(pos):
                config.selected_players = player_config.copy()
                print(
                    f"Selected player config: {config_name}, factions: {list(player_config.keys())}"
                )  # Debug
                return

        # # Check scenario option clicks
        # scenario_y = panel_y + 290
        # scenarios = ["default", "plains", "mountains"]
        # for i, scenario in enumerate(scenarios):
        #     option_rect = pygame.Rect(panel_x + 50, scenario_y + i * 30, 200, 30)
        #     if option_rect.collidepoint(pos):
        #         config.selected_scenario = scenario
        #         return

    def _start_game(self) -> None:
        """Start the game."""
        config = self.world.get_singleton_component(StartMenuConfig)
        if not config:
            return

        # Build game configuration
        self.game_config = {
            "mode": config.selected_mode,
            "players": config.selected_players.copy(),
            "scenario": config.selected_scenario,
        }

        # Switch to game scene via the engine
        self.engine.scene_manager.switch_to("game", **self.game_config)

    def _quit_game(self) -> None:
        """Quit the game."""
        EBS.publish(QuitEvent(sender=__name__, timestamp=pygame.time.get_ticks()))

    def exit(self) -> None:
        """Exit the scene."""
        super().exit()
        self.cleanup()

    def cleanup(self) -> None:
        """Cleanup scene resources."""
        if self.world:
            self.world.reset()
        EBS.unsubscribe(MouseMotionEvent, self._update_hover_state)
        EBS.unsubscribe(MouseButtonDownEvent, self._handle_mouse_click)

    def get_game_config(self) -> Optional[Dict[str, Any]]:
        """Get the prepared game configuration."""
        return self.game_config
