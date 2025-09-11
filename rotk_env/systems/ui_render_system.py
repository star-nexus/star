"""
UI Render System - Responsible for rendering game information, 
statistics, help and other UI elements
"""

import pygame
from pathlib import Path
from framework import System, RMS
from ..components import (
    GameState,
    GameStats,
    UIState,
    TurnManager,
    Player,
)
from ..prefabs.config import GameConfig


class UIRenderSystem(System):
    """UI rendering system for game interface elements"""

    def __init__(self):
        super().__init__(priority=3)  # Lower priority
        self.font = None
        self.small_font = None

        # Initialize fonts
        pygame.font.init()
        file_path = Path("rotk_env/assets/fonts/sh.otf")
        self.font = pygame.font.Font(file_path, 24)
        self.small_font = pygame.font.Font(file_path, 16)

    def initialize(self, world) -> None:
        """Initialize the UI rendering system"""
        self.world = world

    def subscribe_events(self):
        """Subscribe to events (UI render system doesn't need to subscribe to events)"""
        pass

    def update(self, delta_time: float) -> None:
        """Update UI rendering"""
        self._render_ui()

    def _render_ui(self):
        """Render UI interface"""
        self._render_game_info()
        self._render_stats_panel()
        self._render_help_panel()

    def _render_game_info(self):
        """Render game information (top of screen)"""
        game_state = self.world.get_singleton_component(GameState)
        turn_manager = self.world.get_singleton_component(TurnManager)

        if not game_state or not turn_manager:
            return

        # Render turn information
        turn_text = f"Turn {game_state.turn_number}"
        turn_surface = self.font.render(turn_text, True, (255, 255, 255))
        RMS.draw(turn_surface, (10, 10))

        # Render current player
        current_player_entity = turn_manager.get_current_player()
        if current_player_entity:
            player_comp = self.world.get_component(current_player_entity, Player)
            if player_comp:
                player_text = f"Active Faction: {player_comp.name}"
                player_color = GameConfig.FACTION_COLORS.get(
                    player_comp.faction, (255, 255, 255)
                )
                player_surface = self.font.render(player_text, True, player_color)
                RMS.draw(player_surface, (250, 10))

        # Render game phase (simplified handling here)
        phase_text = f"Game Mode: {game_state.game_mode.value}"
        phase_surface = self.small_font.render(phase_text, True, (200, 200, 200))
        RMS.draw(phase_surface, (10, 40))

    def _render_stats_panel(self):
        """Render statistics panel"""
        ui_state = self.world.get_singleton_component(UIState)
        game_stats = self.world.get_singleton_component(GameStats)

        if not ui_state or not ui_state.show_stats or not game_stats:
            return

        # Create statistics panel background
        panel_width = 300
        panel_height = 400
        panel_x = GameConfig.WINDOW_WIDTH - panel_width - 10
        panel_y = 150

        panel_surface = pygame.Surface((panel_width, panel_height))
        panel_surface.set_alpha(200)
        panel_surface.fill((0, 0, 0))
        RMS.draw(panel_surface, (panel_x, panel_y))

        # Draw border
        RMS.rect((150, 150, 150), (panel_x, panel_y, panel_width, panel_height), 2)

        # Render title
        title_surface = self.font.render("GAME STATISTICS", True, (255, 255, 255))
        RMS.draw(title_surface, (panel_x + 10, panel_y + 10))

        # Render faction statistics
        y_offset = panel_y + 50
        line_height = 25

        for faction, faction_stats in game_stats.faction_stats.items():
            if y_offset + line_height > panel_y + panel_height - 20:
                break

            # Safely get faction color
            color = GameConfig.FACTION_COLORS.get(faction, (255, 255, 255))

            # Faction name
            faction_text = f"{faction.value}:"
            faction_surface = self.font.render(faction_text, True, color)
            RMS.draw(faction_surface, (panel_x + 10, y_offset))
            y_offset += line_height

            # Statistics data
            for stat_name, stat_value in faction_stats.items():
                if y_offset + 20 > panel_y + panel_height - 20:
                    break
                stat_text = f"  {stat_name}: {stat_value}"
                stat_surface = self.small_font.render(stat_text, True, (255, 255, 255))
                RMS.draw(stat_surface, (panel_x + 10, y_offset))
                y_offset += 20

            y_offset += 10

    def _render_help_panel(self):
        """Render help panel"""
        ui_state = self.world.get_singleton_component(UIState)
        if not ui_state or not ui_state.show_help:
            return

        # Create help panel background
        panel_width = 500
        panel_height = 400
        panel_x = (GameConfig.WINDOW_WIDTH - panel_width) // 2
        panel_y = (GameConfig.WINDOW_HEIGHT - panel_height) // 2

        panel_surface = pygame.Surface((panel_width, panel_height))
        panel_surface.set_alpha(240)
        panel_surface.fill((0, 0, 30))
        RMS.draw(panel_surface, (panel_x, panel_y))

        # Draw border
        RMS.rect((100, 150, 200), (panel_x, panel_y, panel_width, panel_height), 3)

        # Render title
        title_surface = self.font.render("GAME HELP", True, (255, 255, 255))
        title_rect = title_surface.get_rect(
            center=(panel_x + panel_width // 2, panel_y + 30)
        )
        RMS.draw(title_surface, title_rect)

        # Render help content
        help_content = [
            "Basic Controls:",
            "  Left Mouse - Select Unit",
            "  Right Mouse - Move Unit",
            "  Middle Mouse - Attack Enemy",
            "",
            "Keyboard Shortcuts:",
            "  SPACE - End Turn",
            "  ESC - Cancel Selection",
            "  H - Toggle Help",
            "  S - Toggle Statistics",
            "  B - Toggle Battle Log",
            "  1-4 - Switch View Mode",
            "",
            "Game Rules:",
            "  Each unit can move once per turn",
            "  Units cannot move after attacking",
            "  Units die when health reaches 0",
            "  Eliminate all enemies to win",
            "",
            "Press H to close this help panel",
        ]

        y_offset = panel_y + 70
        line_height = 18

        for line in help_content:
            if y_offset + line_height > panel_y + panel_height - 20:
                break

            if line == "":
                y_offset += line_height // 2
                continue

            color = (255, 255, 255)
            if line.endswith(":"):
                color = (255, 255, 0)  # Headers in yellow
            elif line.startswith("  "):
                color = (200, 200, 200)  # Indented content in light gray

            line_surface = self.small_font.render(line, True, color)
            RMS.draw(line_surface, (panel_x + 20, y_offset))
            y_offset += line_height
