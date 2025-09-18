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
from ..prefabs.config import GameConfig, GameMode


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
        """Render game information (top of screen) - mode-specific display"""
        game_state = self.world.get_singleton_component(GameState)
        turn_manager = self.world.get_singleton_component(TurnManager)

        if not game_state:
            return

        # Render game mode indicator
        mode_text = f"Mode: {game_state.game_mode.value}"
        mode_color = (
            (100, 255, 100)
            if game_state.game_mode == GameMode.TURN_BASED
            else (255, 255, 100)
        )
        mode_surface = self.small_font.render(mode_text, True, mode_color)
        RMS.draw(mode_surface, (10, 10))

        # Mode-specific rendering
        if game_state.game_mode == GameMode.TURN_BASED:
            self._render_turn_based_info(game_state, turn_manager)
        elif game_state.game_mode == GameMode.REAL_TIME:
            self._render_real_time_info(game_state)

    def _render_turn_based_info(self, game_state, turn_manager):
        """Render turn-based mode specific information"""
        # Render turn number with emphasis
        turn_text = f"Turn {game_state.turn_number}"
        turn_surface = self.font.render(turn_text, True, (255, 255, 255))
        RMS.draw(turn_surface, (10, 40))

        # Render current active faction with clear indicator
        if hasattr(game_state, "current_player") and game_state.current_player:
            faction_text = f"Active: {game_state.current_player.value}"
            faction_color = GameConfig.FACTION_COLORS.get(
                game_state.current_player, (255, 255, 255)
            )
            faction_surface = self.font.render(faction_text, True, faction_color)
            RMS.draw(faction_surface, (250, 40))

            # Add visual indicator for active faction
            indicator_rect = (240, 45, 8, 20)
            RMS.rect(faction_color, indicator_rect, 0)

        # Show turn end instruction and player type
        if turn_manager:
            current_player_entity = turn_manager.get_current_player()
            if current_player_entity:
                player_comp = self.world.get_component(current_player_entity, Player)
                if player_comp:
                    # Show player type
                    player_type_text = f"Player: {player_comp.player_type.value}"
                    player_type_surface = self.small_font.render(
                        player_type_text, True, (150, 150, 150)
                    )
                    RMS.draw(player_type_surface, (250, 70))

                    # Show specific instructions based on player type
                    if player_comp.player_type.value == "human":
                        hint_text = "Press SPACE to end turn"
                        hint_color = (255, 255, 100)
                    elif player_comp.player_type.value == "ai":
                        hint_text = "AI thinking..."
                        hint_color = (100, 255, 100)
                    else:  # LLM
                        hint_text = "Waiting for LLM agent..."
                        hint_color = (100, 200, 255)

                    hint_surface = self.small_font.render(hint_text, True, hint_color)
                    RMS.draw(hint_surface, (250, 90))

        # Show waiting factions in turn-based mode
        self._render_waiting_factions(game_state)

    def _render_real_time_info(self, game_state):
        """Render real-time mode specific information"""
        # Show game time - try to get from GameStats if game_time not available
        if hasattr(game_state, "game_time"):
            time_text = f"Game Time: {game_state.game_time:.1f}s"
        else:
            # Fallback to GameStats total_game_time
            game_stats = self.world.get_singleton_component(GameStats)
            if game_stats:
                minutes = int(game_stats.total_game_time // 60)
                seconds = int(game_stats.total_game_time % 60)
                time_text = f"Game Time: {minutes:02d}:{seconds:02d}"
            else:
                time_text = "Game Time: 00:00"

        time_surface = self.font.render(time_text, True, (255, 255, 255))
        RMS.draw(time_surface, (10, 40))

        # Show all factions as active
        active_text = "All factions active"
        active_surface = self.font.render(active_text, True, (255, 255, 100))
        RMS.draw(active_surface, (250, 40))

        # Show faction status indicators
        self._render_faction_status_indicators()

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

    def _render_faction_status_indicators(self):
        """Render faction status indicators for real-time mode"""
        from ..components import Unit

        # Get all factions with units
        faction_units = {}
        for entity in self.world.query().with_component(Unit).entities():
            unit = self.world.get_component(entity, Unit)
            if unit:
                faction = unit.faction
                if faction not in faction_units:
                    faction_units[faction] = 0
                faction_units[faction] += 1

        # Render faction status indicators
        x_offset = 450
        y_pos = 40
        indicator_size = 12
        spacing = 80

        for i, (faction, unit_count) in enumerate(faction_units.items()):
            faction_color = GameConfig.FACTION_COLORS.get(faction, (255, 255, 255))

            # Faction indicator circle
            circle_center = (x_offset + i * spacing, y_pos)
            RMS.circle(faction_color, circle_center, indicator_size, 0)

            # Faction name and unit count
            faction_text = f"{faction.value}: {unit_count}"
            faction_surface = self.small_font.render(faction_text, True, faction_color)
            RMS.draw(faction_surface, (x_offset + i * spacing - 20, y_pos + 15))

    def _render_waiting_factions(self, game_state):
        """Render waiting factions in turn-based mode"""
        from ..components import Unit

        # Get all factions
        all_factions = set()
        for entity in self.world.query().with_component(Unit).entities():
            unit = self.world.get_component(entity, Unit)
            if unit:
                all_factions.add(unit.faction)

        # Show waiting factions
        waiting_factions = [f for f in all_factions if f != game_state.current_player]

        if waiting_factions:
            waiting_text = "Waiting: " + ", ".join([f.value for f in waiting_factions])
            waiting_surface = self.small_font.render(
                waiting_text, True, (150, 150, 150)
            )
            RMS.draw(waiting_surface, (10, 70))
