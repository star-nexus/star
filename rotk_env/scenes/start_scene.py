"""
Start scene.
"""

import pygame
from typing import Dict, Any, Optional
from framework import World
from framework.engine import RMS, EBS, MouseButtonDownEvent, MouseMotionEvent, MouseWheelEvent, Event, KeyDownEvent, QuitEvent
from framework.engine.scenes import Scene
from ..prefabs.config import Faction, GameConfig, PlayerType, GameMode
from ..components.start_menu import (
    StartMenuConfig,
    StartMenuButtons,
    StartMenuOptions,
    start_panel_layout,
    clamp_scenario_scroll,
)
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
        EBS.subscribe(MouseWheelEvent, self._handle_mouse_wheel)
        # EBS.subscribe(KeyDownEvent, self._handle_key_down)

    def update(self, dt: float) -> None:
        """Update the scene."""
        GameConfig.sync_from_display()
        self._layout_buttons()
        self._clamp_scenario_scroll()
        self.world.update(dt)

    def _clamp_scenario_scroll(self) -> None:
        config = self.world.get_singleton_component(StartMenuConfig)
        if not config:
            return
        geom = start_panel_layout(len(config.scenario_catalog or []))
        config.scenario_scroll = clamp_scenario_scroll(
            config.scenario_scroll, len(config.scenario_catalog or []), geom
        )

    def _layout_buttons(self) -> None:
        buttons_component = self.world.get_singleton_component(StartMenuButtons)
        if not buttons_component:
            return
        screen_width = GameConfig.WINDOW_WIDTH
        screen_height = GameConfig.WINDOW_HEIGHT
        start = buttons_component.buttons.get("start_game")
        quit_btn = buttons_component.buttons.get("quit")
        if start:
            start["rect"] = pygame.Rect(
                screen_width // 2 - 100, screen_height - 150, 200, 50
            )
        if quit_btn:
            quit_btn["rect"] = pygame.Rect(
                screen_width // 2 - 100, screen_height - 80, 200, 50
            )

    def _update_hover_state(self, event: MouseMotionEvent) -> None:
        """Update hover state."""
        if not self.is_active:
            return
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
        if not self.is_active:
            return
        GameConfig.sync_from_display()
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

        geom = start_panel_layout(len(config.scenario_catalog or []))
        panel_x = geom["panel_x"]

        mode_y = geom["mode_y"] + 60
        for i, mode in enumerate([GameMode.TURN_BASED, GameMode.REAL_TIME]):
            option_rect = pygame.Rect(panel_x + 50, mode_y + i * 45, 250, 30)
            if option_rect.collidepoint(pos):
                config.selected_mode = mode
                return

        player_y = geom["player_y"] + 60
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
            option_rect = pygame.Rect(panel_x + 50, player_y + i * 45, 500, 30)
            if option_rect.collidepoint(pos):
                config.selected_players = player_config.copy()
                return

        catalog = config.scenario_catalog or []
        option_y = geom["scenario_option_y"]
        cols = geom["scenario_cols"]
        col_w = geom["scenario_col_w"]
        row_h = geom["scenario_row_h"]
        visible_rows = geom["scenario_visible_rows"]
        scroll = clamp_scenario_scroll(config.scenario_scroll, len(catalog), geom)
        config.scenario_scroll = scroll
        for i, item in enumerate(catalog):
            col = i % cols
            vis_row = i // cols - scroll
            if vis_row < 0 or vis_row >= visible_rows:
                continue
            option_rect = pygame.Rect(
                panel_x + 50 + col * col_w,
                option_y + vis_row * row_h,
                col_w - 20,
                row_h - 4,
            )
            if option_rect.collidepoint(pos):
                config.selected_scenario = item["scenario"]
                return

    def _handle_mouse_wheel(self, event: MouseWheelEvent) -> None:
        if not self.is_active:
            return
        config = self.world.get_singleton_component(StartMenuConfig)
        if not config:
            return
        GameConfig.sync_from_display()
        geom = start_panel_layout(len(config.scenario_catalog or []))
        config.scenario_scroll = clamp_scenario_scroll(
            config.scenario_scroll - int(event.y),
            len(config.scenario_catalog or []),
            geom,
        )

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
        EBS.unsubscribe(MouseWheelEvent, self._handle_mouse_wheel)

    def get_game_config(self) -> Optional[Dict[str, Any]]:
        """Get the prepared game configuration."""
        return self.game_config
