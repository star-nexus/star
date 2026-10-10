"""
UI Button System - Handles UI button rendering, interaction and callbacks
"""

import pygame
from pathlib import Path
from framework import System
from framework.engine import RMS
from ..components import (
    UIButton,
    UIButtonCollection,
    UIPanel,
    InputState,
    GameState,
    TurnManager,
    Player,
    UIState,
)
from ..prefabs.config import GameConfig


class UIButtonSystem(System):
    """UI button system for handling button interactions"""

    def __init__(self):
        super().__init__(priority=2)  # High priority, process before UI rendering
        self.font = None
        self.button_font = None

        # Initialize fonts
        pygame.font.init()
        try:
            file_path = Path("rotk_env/assets/fonts/sh.otf")
            self.font = pygame.font.Font(file_path, 18)
            self.button_font = pygame.font.Font(file_path, 16)
        except:
            # Use default font as fallback
            self.font = pygame.font.Font(None, 18)
            self.button_font = pygame.font.Font(None, 16)

    def initialize(self, world) -> None:
        """Initialize button system"""
        self.world = world
        self._create_ui_buttons()

    def subscribe_events(self):
        """Subscribe to events"""
        pass

    def update(self, delta_time: float) -> None:
        """Update button system"""
        self._layout_ui_buttons()
        self._update_button_states()
        self._handle_button_clicks()
        self._render_buttons()

    def _layout_ui_buttons(self) -> None:
        collection = self.world.get_singleton_component(UIButtonCollection)
        if not collection:
            return
        ctx = getattr(self.world, '_ui_context', None)
        if ctx:
            # Layout stays in UiContext; legacy UIButton fields remain intact.
            return
        w, h = GameConfig.WINDOW_WIDTH, GameConfig.WINDOW_HEIGHT
        specs = {
            "end_turn": (w - 150, h - 60),
            "settings": (w - 80, 10),
            "help": (w - 160, 10),
            "stats": (w - 240, 10),
        }
        for name, (x, y) in specs.items():
            entity = collection.get_button(name)
            if entity is None:
                continue
            button = self.world.get_component(entity, UIButton)
            if button:
                button.x = x
                button.y = y

    def _button_rect(self, button):
        ctx = getattr(self.world, '_ui_context', None)
        if ctx:
            side = ctx.layout.sidebar
            if button.callback_name == 'show_settings':
                return None
            if button.callback_name == 'toggle_help':
                return pygame.Rect(side.right-88,16,76,30)
            if button.callback_name == 'toggle_stats':
                return pygame.Rect(side.right-174,16,76,30)
            if button.callback_name == 'end_turn':
                return ctx.layout.footer
        return pygame.Rect(button.x,button.y,button.width,button.height)

    def _create_ui_buttons(self):
        """Create UI buttons"""
        # Create button collection singleton component
        button_collection = UIButtonCollection()
        self.world.add_singleton_component(button_collection)

        print("Creating UI buttons...")  # Debug output

        # Create end turn button
        end_turn_button = self.world.create_entity()
        self.world.add_component(
            end_turn_button,
            UIButton(
                x=GameConfig.WINDOW_WIDTH - 150,
                y=GameConfig.WINDOW_HEIGHT - 60,
                width=140,
                height=40,
                text="End Turn",
                background_color=(80, 120, 80),
                hover_color=(100, 150, 100),
                callback_name="end_turn",
            ),
        )
        button_collection.add_button("end_turn", end_turn_button)
        print(f"✓ Created End Turn button (Entity ID: {end_turn_button})")

        # Create settings button
        settings_button = self.world.create_entity()
        self.world.add_component(
            settings_button,
            UIButton(
                x=GameConfig.WINDOW_WIDTH - 80,
                y=10,
                width=70,
                height=30,
                text="Settings",
                background_color=(100, 100, 100),
                hover_color=(130, 130, 130),
                callback_name="show_settings",
            ),
        )
        button_collection.add_button("settings", settings_button)
        print(f"✓ Created Settings button (Entity ID: {settings_button})")

        # Create help button
        help_button = self.world.create_entity()
        self.world.add_component(
            help_button,
            UIButton(
                x=GameConfig.WINDOW_WIDTH - 160,
                y=10,
                width=70,
                height=30,
                text="Help",
                background_color=(80, 80, 120),
                hover_color=(100, 100, 150),
                callback_name="toggle_help",
            ),
        )
        button_collection.add_button("help", help_button)
        print(f"✓ Created Help button (Entity ID: {help_button})")

        # Create statistics button
        stats_button = self.world.create_entity()
        self.world.add_component(
            stats_button,
            UIButton(
                x=GameConfig.WINDOW_WIDTH - 240,
                y=10,
                width=70,
                height=30,
                text="Statistics",
                background_color=(120, 80, 80),
                hover_color=(150, 100, 100),
                callback_name="toggle_stats",
            ),
        )
        button_collection.add_button("stats", stats_button)
        print(f"✓ Created Statistics button (Entity ID: {stats_button})")

        print("UI buttons creation completed!")

    def _update_button_states(self):
        """Update button states"""
        input_state = self.world.get_singleton_component(InputState)
        if not input_state:
            return

        mouse_x, mouse_y = input_state.mouse_pos

        # Update hover state for all buttons
        for entity in self.world.query().with_component(UIButton).ordered_entities():
            button = self.world.get_component(entity, UIButton)
            if not button or not button.is_enabled or not button.is_visible:
                continue

            # Check if mouse is over button
            rect = self._button_rect(button)
            is_hovered = bool(rect and rect.collidepoint(mouse_x, mouse_y))
            button.is_hovered = is_hovered

    def _handle_button_clicks(self):
        """Handle button clicks"""
        input_state = self.world.get_singleton_component(InputState)
        if not input_state:
            return

        # Check if left mouse button was just pressed
        if 1 not in input_state.mouse_pressed:  # 1 is left button
            return

        mouse_x, mouse_y = input_state.mouse_pos

        # Check clicked buttons
        for entity in self.world.query().with_component(UIButton).ordered_entities():
            button = self.world.get_component(entity, UIButton)
            if not button or not button.is_enabled or not button.is_visible:
                continue

            # Check if click is within button
            rect = self._button_rect(button)
            if rect and rect.collidepoint(mouse_x, mouse_y):
                ctx = getattr(self.world, '_ui_context', None)
                if ctx and ctx.modal_visible(self.world) and button.callback_name not in ('toggle_help', 'toggle_stats'):
                    return
                self._handle_button_callback(button)
                break

    def _handle_button_callback(self, button: UIButton):
        """Handle button callback"""
        if not button.callback_name:
            return

        print(f"Button clicked: {button.text} (callback: {button.callback_name})")  # Debug output

        # Execute corresponding function based on callback name
        if button.callback_name == "end_turn":
            self._end_turn()
        elif button.callback_name == "show_settings":
            self._show_settings()
        elif button.callback_name == "toggle_help":
            self._toggle_help()
        elif button.callback_name == "toggle_stats":
            self._toggle_stats()

    def _end_turn(self):
        """End current turn"""
        print("Executing end turn operation...")  # Debug output

        game_state = self.world.get_singleton_component(GameState)
        turn_manager = self.world.get_singleton_component(TurnManager)

        if not game_state or not turn_manager:
            print("Unable to get game state or turn manager")
            return

        # Switch to next player
        current_index = turn_manager.current_player_index
        turn_manager.next_player()

        # If back to first player, increment turn number
        if turn_manager.current_player_index == 0:
            game_state.turn_number += 1
            print(f"New turn started: {game_state.turn_number}")

        # Update current player
        current_player_entity = turn_manager.get_current_player()
        if current_player_entity:
            player = self.world.get_component(current_player_entity, Player)
            if player:
                game_state.current_player = player.faction
                print(f"Switched to player: {player.faction.value}")

    def _show_settings(self):
        """Show settings panel"""
        print("Showing settings panel")  # Temporary implementation

    def _toggle_help(self):
        """Toggle help panel display"""
        ui_state = self.world.get_singleton_component(UIState)
        if ui_state:
            ui_state.show_help = not ui_state.show_help
            print(f"Help panel: {'shown' if ui_state.show_help else 'hidden'}")

    def _toggle_stats(self):
        """Toggle statistics panel display"""
        ui_state = self.world.get_singleton_component(UIState)
        if ui_state:
            ui_state.show_stats = not ui_state.show_stats
            print(f"Statistics panel: {'shown' if ui_state.show_stats else 'hidden'}")

    def _render_buttons(self):
        """Render all buttons"""
        for entity in self.world.query().with_component(UIButton).ordered_entities():
            button = self.world.get_component(entity, UIButton)
            if not button or not button.is_visible:
                continue

            if self._button_rect(button) is not None:
                self._render_button(button)

    def _render_button(self, button: UIButton):
        """Render single button"""
        ctx = getattr(self.world, '_ui_context', None)
        if ctx:
            from ..ui.context import MUTED, PANEL, BORDER, TEXT
            rect = self._button_rect(button)
            if rect is None:
                return
            RMS.rect((55,73,88) if button.is_hovered and button.is_enabled else PANEL, rect)
            RMS.rect(BORDER, rect, 1)
            ctx.text(button.text, (rect.centerx, rect.centery-ctx.font(18).get_height()//2),
                     size=18, color=TEXT if button.is_enabled else MUTED, centered=True)
            return
        # Choose background color
        if button.is_hovered and button.is_enabled:
            bg_color = button.hover_color
        else:
            bg_color = button.background_color

        # If button is disabled, use darker color
        if not button.is_enabled:
            bg_color = tuple(c // 2 for c in bg_color)

        # Create button surface
        button_surface = pygame.Surface((button.width, button.height))
        button_surface.fill(bg_color)

        # Draw border
        if button.border_width > 0:
            border_color = button.border_color
            if not button.is_enabled:
                border_color = tuple(c // 2 for c in border_color)
            pygame.draw.rect(
                button_surface,
                border_color,
                (0, 0, button.width, button.height),
                button.border_width,
            )

        # Render text
        text_color = button.text_color
        if not button.is_enabled:
            text_color = tuple(c // 2 for c in text_color)

        text_surface = self.button_font.render(button.text, True, text_color)
        text_rect = text_surface.get_rect(
            center=(button.width // 2, button.height // 2)
        )
        button_surface.blit(text_surface, text_rect)

        # Draw to screen
        RMS.draw(button_surface, (button.x, button.y))
