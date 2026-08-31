"""
Start scene.
"""

import pygame
from typing import Dict, Any, Optional
from framework import World
from framework.engine import EBS, MouseButtonDownEvent, MouseMotionEvent, MouseWheelEvent, QuitEvent
from framework.engine.scenes import Scene
from ..prefabs.config import GameConfig, GameMode
from ..prefabs.world_builder import DEFAULT_HUB_URL
from ..components.start_menu import (
    StartMenuConfig,
    StartMenuButtons,
    START_PLAYER_OPTIONS,
    START_CONTROLLER_OPTIONS,
    controller_backend_flags,
    start_panel_layout,
    clamp_scenario_scroll,
)
from ..systems.start_scene_render_system import StartSceneRenderSystem


class StartScene(Scene):
    """Start scene and the single visible-window handoff into GameScene.

    Both menu launches and ``--skip-start`` visible launches queue the same
    GameScene kwargs here.  The actual scene switch happens from ``update()``,
    after the engine's input-dispatch phase, so GameScene is never constructed
    from two different lifecycle points (pre-loop CLI vs in-event UI callback).
    """

    def __init__(self, engine):
        super().__init__(engine)
        self.name = "start"
        self.world = World()
        self.game_config = None
        self._pending_game_config = None

    def enter(self, **kwargs) -> None:
        """Called when entering the scene."""
        super().enter(**kwargs)
        self.world.add_singleton_component(StartMenuConfig())

        screen_width = GameConfig.WINDOW_WIDTH
        screen_height = GameConfig.WINDOW_HEIGHT
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

        self.world.add_singleton_component(
            StartMenuButtons(buttons=buttons, options={})
        )
        self.world.add_system(StartSceneRenderSystem())
        self.subscribe_events()

        auto_start_config = kwargs.get("auto_start_config")
        if auto_start_config is not None:
            self._queue_game_start(auto_start_config)

    def subscribe_events(self) -> None:
        EBS.subscribe(MouseMotionEvent, self._update_hover_state)
        EBS.subscribe(MouseButtonDownEvent, self._handle_mouse_click)
        EBS.subscribe(MouseWheelEvent, self._handle_mouse_wheel)

    def update(self, dt: float) -> None:
        """Update the scene and perform any queued launch at a frame boundary."""
        GameConfig.sync_from_display()
        if self._flush_pending_game_start():
            return
        self._layout_buttons()
        self._clamp_scenario_scroll()
        self.world.update(dt)

    def _queue_game_start(self, game_config: Dict[str, Any]) -> None:
        """Queue one visible GameScene launch using an immutable kwargs snapshot."""
        self.game_config = dict(game_config)
        self._pending_game_config = dict(game_config)

    def _focus_display_window(self) -> None:
        """Best-effort SDL focus normalization shared by UI and visible CLI.

        On macOS a freshly created window launched from Terminal can otherwise
        consume the first click as an activation click. The menu path naturally
        has focus because the user just clicked Start; --skip-start did not.
        Pygame 2 exposes SDL_Window::focus through the experimental _sdl2 view.
        If a platform/backend does not support it, gameplay still proceeds.
        """
        try:
            from pygame._sdl2.video import Window

            Window.from_display_module().focus()
        except (ImportError, AttributeError, pygame.error):
            pass

    def _flush_pending_game_start(self) -> bool:
        """Switch to GameScene outside input-event dispatch; return if switched."""
        if self._pending_game_config is None:
            return False
        game_config = self._pending_game_config
        self._pending_game_config = None
        self._focus_display_window()
        self.engine.scene_manager.switch_to("game", **game_config)
        return True

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
        for button in buttons_component.buttons.values():
            button["hover"] = button["rect"].collidepoint(event.pos)

    def _handle_mouse_click(self, event: MouseButtonDownEvent) -> None:
        """Handle mouse click."""
        if not self.is_active:
            return
        GameConfig.sync_from_display()
        pos = event.pos

        buttons_component = self.world.get_singleton_component(StartMenuButtons)
        if buttons_component:
            for button in buttons_component.buttons.values():
                if button["rect"].collidepoint(pos):
                    button["action"]()
                    return

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
        for i, (player_config, _label) in enumerate(START_PLAYER_OPTIONS):
            option_rect = pygame.Rect(panel_x + 50, player_y + i * 45, 500, 30)
            if option_rect.collidepoint(pos):
                config.selected_players = player_config.copy()
                return

        controller_y = geom["controller_option_y"]
        controller_spacing = geom["controller_spacing"]
        for i, (backend, _label) in enumerate(START_CONTROLLER_OPTIONS):
            option_rect = pygame.Rect(
                panel_x + 50,
                controller_y + i * controller_spacing,
                500,
                28,
            )
            if option_rect.collidepoint(pos):
                config.selected_controller_backend = backend
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
        """Queue the menu-selected game using the shared visible launch path."""
        config = self.world.get_singleton_component(StartMenuConfig)
        if not config:
            return

        enable_mock_ai, use_hub = controller_backend_flags(
            config.selected_controller_backend
        )
        game_config = {
            "mode": config.selected_mode,
            "players": config.selected_players.copy(),
            "scenario": config.selected_scenario,
            "enable_mock_ai": enable_mock_ai,
            "hub_url": DEFAULT_HUB_URL if use_hub else None,
        }
        self._queue_game_start(game_config)

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
