"""
Game Over Statistics Scene.
Builds a lightweight world with winner info, statistics, and buttons,
and wires up render systems and mouse interactions.
"""

import pygame
from typing import Dict, Any, Optional
from framework import (
    World,
    SMS,
    RMS,
    EBS,
    MouseButtonDownEvent,
    MouseMotionEvent,
    MouseWheelEvent,
    Event,
)
from framework.engine.engine_event import QuitEvent
from framework.engine.scenes import Scene
from ..components.game_over import Winner, GameStatistics, GameOverButtons
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
            "restart": {
                "rect": pygame.Rect(start_x, button_y, button_width, button_height),
                "text": "Restart",
                "hover": False,
                "default_color": (60, 60, 80),
                "hover_color": (80, 80, 100),
                "action": self._restart_game,
            },
            "view_report": {
                "rect": pygame.Rect(start_x + button_width + button_spacing, button_y, button_width, button_height),
                "text": "View Report",
                "hover": False,
                "default_color": (60, 80, 60),
                "hover_color": (80, 100, 80),
                "action": self._toggle_report_view,
            },
            "quit": {
                "rect": pygame.Rect(start_x + 2 * (button_width + button_spacing), button_y, button_width, button_height),
                "text": "Quit",
                "hover": False,
                "default_color": (80, 60, 60),
                "hover_color": (100, 80, 80),
                "action": self._quit_game,
            },
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
        if self.world:
            self.world.update(dt)

    def handle_event(self, event: Event) -> None:
        """Handle mouse input events."""
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

        for button_name, button in button_component.buttons.items():
            if button["rect"].collidepoint(pos):
                button["action"]()

    def _handle_mouse_motion(self, pos: tuple) -> None:
        """Handle hover effects for buttons."""
        button_component = self.world.get_singleton_component(GameOverButtons)
        if not button_component:
            return

        for button_name, button in button_component.buttons.items():
            if button["rect"].collidepoint(pos):
                button["hover"] = True
            else:
                button["hover"] = False

    def _handle_mouse_wheel(self, y: int) -> None:
        """Handle mouse wheel: forward to settlement report system."""
        # Forward to settlement report render system
        for system in self.world.systems:
            if isinstance(system, SettlementReportRenderSystem):
                system.handle_scroll(y)
                break

    def exit(self):
        return super().exit()

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
