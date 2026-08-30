"""
Game Over Statistics Scene.
Builds a lightweight world with winner info, statistics, and buttons,
and wires up render systems and mouse interactions.
"""

import pygame
from typing import Dict, Any, Optional
from framework import World
from framework.engine import SMS, RMS, EBS, MouseButtonDownEvent, MouseMotionEvent, MouseWheelEvent, Event
from framework.engine.engine_event import QuitEvent
from framework.engine.scenes import Scene
from ..components.game_over import (
    Winner,
    GameStatistics,
    GameOverButtons,
    GameOverButton,
)
from ..systems.game_over_render_system import GameOverRenderSystem
from ..systems.settlement_report_render_system import SettlementReportRenderSystem
from ..prefabs.config import Faction, GameConfig


class GameOverScene(Scene):
    """Game over/statistics scene."""

    def __init__(self, engine):
        super().__init__(engine)

    def enter(self, **kwargs) -> None:
        """Enter scene with provided kwargs (winner, statistics)."""
        super().enter(**kwargs)
        self.world = World()

        # Extract data from kwargs
        winner = kwargs.get("winner", None)
        statistics = kwargs.get("statistics", {})

        # Winner component
        winner_component = Winner(faction=winner)
        self.world.add_singleton_component(winner_component)

        # Statistics component
        stats_component = GameStatistics(data=statistics)
        self.world.add_singleton_component(stats_component)

        # Create buttons
        self._create_buttons()

        # Add render systems
        game_over_system = GameOverRenderSystem()
        settlement_report_system = SettlementReportRenderSystem()
        
        self.world.add_system(game_over_system)
        self.world.add_system(settlement_report_system)

        self.subscribe_events()

    def _create_buttons(self) -> None:
        """Create buttons for the Game Over screen."""
        # Screen size
        screen_width = GameConfig.WINDOW_WIDTH
        screen_height = GameConfig.WINDOW_HEIGHT

        button_width = 150
        button_height = 40
        button_spacing = 20
        total_width = 3 * button_width + 2 * button_spacing  # 3 buttons
        start_x = (screen_width - total_width) // 2
        button_y = screen_height - 150

        buttons = {
            "restart": GameOverButton(
                action="restart",
                label="Restart",
                x=start_x,
                y=button_y,
                w=button_width,
                h=button_height,
                default_color=(60, 60, 80),
                hover_color=(80, 80, 100),
            ),
            "view_report": GameOverButton(
                action="view_report",
                label="View Report",
                x=start_x + button_width + button_spacing,
                y=button_y,
                w=button_width,
                h=button_height,
                default_color=(60, 80, 60),
                hover_color=(80, 100, 80),
            ),
            "quit": GameOverButton(
                action="quit",
                label="Quit",
                x=start_x + 2 * (button_width + button_spacing),
                y=button_y,
                w=button_width,
                h=button_height,
                default_color=(80, 60, 60),
                hover_color=(100, 80, 80),
            ),
        }

        # Add buttons component
        button_component = GameOverButtons(buttons=buttons)
        self.world.add_singleton_component(button_component)

    def subscribe_events(self) -> None:
        """Subscribe mouse events for click/hover/wheel."""
        # Mouse click and move events
        EBS.subscribe(MouseButtonDownEvent, self.handle_event)
        EBS.subscribe(MouseMotionEvent, self.handle_event)
        EBS.subscribe(MouseWheelEvent, self.handle_event)

    def update(self, dt: float) -> None:
        """Update scene world."""
        GameConfig.sync_from_display()
        self._layout_buttons()
        if self.world:
            self.world.update(dt)

    def _layout_buttons(self) -> None:
        if not getattr(self, "world", None):
            return
        button_component = self.world.get_singleton_component(GameOverButtons)
        if not button_component:
            return
        screen_width = GameConfig.WINDOW_WIDTH
        screen_height = GameConfig.WINDOW_HEIGHT
        button_width = 150
        button_spacing = 20
        total_width = 3 * button_width + 2 * button_spacing
        start_x = (screen_width - total_width) // 2
        button_y = screen_height - 150
        for i, button in enumerate(button_component.buttons.values()):
            button.x = start_x + i * (button_width + button_spacing)
            button.y = button_y

    def handle_event(self, event: Event) -> None:
        """Handle mouse input events."""
        if not self.is_active or not getattr(self, "world", None):
            return
        if isinstance(event, MouseButtonDownEvent):
            if event.button == 1:  # left click
                self._handle_mouse_click(event.pos)
        elif isinstance(event, MouseMotionEvent):
            self._handle_mouse_motion(event.pos)
        elif isinstance(event, MouseWheelEvent):
            self._handle_mouse_wheel(event.y)

    def _handle_mouse_click(self, pos: tuple) -> None:
        """Handle mouse click on buttons."""
        button_component = self.world.get_singleton_component(GameOverButtons)
        if not button_component:
            return

        for button in button_component.buttons.values():
            if button.contains(pos):
                self._dispatch_button(button.action)
                return

    def _handle_mouse_motion(self, pos: tuple) -> None:
        """Handle hover effects for buttons."""
        button_component = self.world.get_singleton_component(GameOverButtons)
        if not button_component:
            return

        for button in button_component.buttons.values():
            button.hover = button.contains(pos)

    def _handle_mouse_wheel(self, y: int) -> None:
        """Handle mouse wheel: forward to settlement report system."""
        if not getattr(self, "world", None):
            return
        for system in self.world.systems:
            if isinstance(system, SettlementReportRenderSystem):
                system.handle_scroll(y)
                break

    def exit(self):
        super().exit()
        self.cleanup()

    def _dispatch_button(self, action: str) -> None:
        """Map button action ids to scene behavior."""
        if action == "restart":
            self._restart_game()
        elif action == "view_report":
            self._toggle_report_view()
        elif action == "quit":
            self._quit_game()

    def _restart_game(self) -> None:
        """Restart the game by switching to start scene."""
        SMS.switch_to("start")

    def _toggle_report_view(self) -> None:
        """Toggle report view (placeholder for extended logic)."""
        print("[GameOverScene] 📊 View detailed settlement report")

    def _quit_game(self) -> None:
        """Quit game via event bus."""
        EBS.publish(QuitEvent(sender=__name__, timestamp=pygame.time.get_ticks()))

    def cleanup(self) -> None:
        """Cleanup scene and unsubscribe events."""
        if self.world:
            self.world.reset()
        EBS.unsubscribe(MouseButtonDownEvent, self.handle_event)
        EBS.unsubscribe(MouseMotionEvent, self.handle_event)
        EBS.unsubscribe(MouseWheelEvent, self.handle_event)
