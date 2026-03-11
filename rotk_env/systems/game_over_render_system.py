"""
Game Over Statistics Render System.
Renders background panel, winner info, aggregated statistics, and buttons.
"""

from pathlib import Path
import pygame
from typing import Dict, Any
from framework import World, System, RMS
from ..prefabs.config import Faction, GameConfig
from ..components.game_over import Winner, GameStatistics, GameOverButtons


class GameOverRenderSystem(System):
    """Render the Game Over statistics UI."""

    def __init__(self):
        super().__init__()
        self.priority = 1  # render late

        # Fonts
        pygame.font.init()
        file_path = Path("rotk_env/assets/fonts/sh.otf")
        self.font_large = pygame.font.Font(file_path, 48)
        self.font_medium = pygame.font.Font(file_path, 32)
        self.font_small = pygame.font.Font(file_path, 24)

        # Colors
        self.background_color = (20, 20, 30)
        self.text_color = (255, 255, 255)
        self.winner_color = (255, 215, 0)  # gold
        self.panel_color = (40, 40, 60, 180)

    def initialize(self, world: World) -> None:
        """Initialize with world reference."""
        self.world = world

    def subscribe_events(self) -> None:
        """No event subscriptions for this render-only system."""
        pass

    def update(self, dt: float) -> None:
        """Render the Game Over UI elements each frame."""
        # Clear screen (handled by engine)
        # RMS.clear()

        # Render sections
        self._render_background()
        self._render_title()
        self._render_winner_info()
        self._render_statistics()
        self._render_buttons()

        # Execute render
        # RMS.present()

    def _render_background(self) -> None:
        """Render background and main panel."""
        screen_width = GameConfig.WINDOW_WIDTH
        screen_height = GameConfig.WINDOW_HEIGHT

        # Fill background color
        background_surface = pygame.Surface((screen_width, screen_height))
        background_surface.fill(self.background_color)
        RMS.draw(background_surface, (0, 0))

        # Main panel
        panel_width = min(800, screen_width - 100)
        panel_height = min(600, screen_height - 100)
        panel_x = (screen_width - panel_width) // 2
        panel_y = (screen_height - panel_height) // 2

        # Semi-transparent panel
        panel_surface = pygame.Surface((panel_width, panel_height), pygame.SRCALPHA)
        panel_surface.fill(self.panel_color)
        RMS.draw(panel_surface, (panel_x, panel_y))

        # Border
        border_surface = pygame.Surface((panel_width, panel_height), pygame.SRCALPHA)
        # pygame.draw.rect(
        #     border_surface, (100, 100, 120), (0, 0, panel_width, panel_height), 3
        # )
        RMS.rect(
            (100, 100, 120),
            (panel_x, panel_y, panel_width, panel_height),
            width=3,
        )

    def _render_title(self) -> None:
        """Render title."""
        # Get screen width
        screen_width = GameConfig.WINDOW_WIDTH

        title_text = "GAME OVER"
        title_surface = self.font_large.render(title_text, True, self.text_color)
        title_x = (screen_width - title_surface.get_width()) // 2
        RMS.draw(title_surface, (title_x, 120))

    def _render_winner_info(self) -> None:
        """Render winner information or draw state."""
        # Screen size
        screen_width = GameConfig.WINDOW_WIDTH

        # Winner from world
        winner_component = self.world.get_singleton_component(Winner)
        winner = winner_component.faction if winner_component else None

        y_offset = 180

        if winner:
            winner_names = {
                Faction.WEI: "Wei",
                Faction.SHU: "Shu",
                Faction.WU: "Wu",
            }
            winner_text = f"Winner: {winner_names.get(winner, str(winner))}"
            winner_surface = self.font_medium.render(
                winner_text, True, self.winner_color
            )
            winner_x = (screen_width - winner_surface.get_width()) // 2
            RMS.draw(winner_surface, (winner_x, y_offset))
        else:
            draw_text = "Draw"
            draw_surface = self.font_medium.render(draw_text, True, self.text_color)
            draw_x = (screen_width - draw_surface.get_width()) // 2
            RMS.draw(draw_surface, (draw_x, y_offset))

    def _render_statistics(self) -> None:
        """Render statistics info (totals and per-faction)."""
        # Screen size
        screen_width = GameConfig.WINDOW_WIDTH

        # Get stats from world
        stats_component = self.world.get_singleton_component(GameStatistics)
        if not stats_component:
            return

        statistics = stats_component.data
        winner_component = self.world.get_singleton_component(Winner)
        winner = winner_component.faction if winner_component else None

        y_offset = 240
        line_height = 30

        # Overall statistics
        stats_lines = [
            f"Total turns: {statistics.get('total_turns', 0)}",
            f"Game duration: {statistics.get('game_duration', 0):.1f}s",
            f"Total units: {statistics.get('total_units', 0)}",
            f"Surviving units: {statistics.get('surviving_units', 0)}",
            "",
        ]

        for line in stats_lines:
            if line:
                text_surface = self.font_small.render(line, True, self.text_color)
                text_x = (screen_width - text_surface.get_width()) // 2
                RMS.draw(text_surface, (text_x, y_offset))
            y_offset += line_height

        # Per-faction statistics
        faction_names = {Faction.WEI: "Wei", Faction.SHU: "Shu", Faction.WU: "Wu"}
        faction_stats = statistics.get("faction_stats", {})

        for faction, stats in faction_stats.items():
            faction_name = faction_names.get(faction, str(faction))
            faction_text = f"{faction_name}: {stats.get('surviving_units', 0)}/{stats.get('total_units', 0)} alive"

            color = self.winner_color if faction == winner else self.text_color
            text_surface = self.font_small.render(faction_text, True, color)
            text_x = (screen_width - text_surface.get_width()) // 2
            RMS.draw(text_surface, (text_x, y_offset))
            y_offset += line_height

    def _render_buttons(self) -> None:
        """Render buttons with hover state."""
        # Buttons from world
        button_component = self.world.get_singleton_component(GameOverButtons)
        if not button_component:
            return

        for button_name, button in button_component.buttons.items():
            # Button background
            button_color = (
                button["hover_color"] if button["hover"] else button["default_color"]
            )

            # Button background surface
            button_surface = pygame.Surface(
                (button["rect"].width, button["rect"].height)
            )
            button_surface.fill(button_color)
            RMS.draw(button_surface, (button["rect"].x, button["rect"].y))

            # Border surface
            border_surface = pygame.Surface(
                (button["rect"].width, button["rect"].height), pygame.SRCALPHA
            )
            # pygame.draw.rect(
            #     border_surface,
            #     (120, 120, 140),
            #     (0, 0, button["rect"].width, button["rect"].height),
            #     2,
            # )
            RMS.rect(
                (120, 120, 140),
                (
                    button["rect"].x,
                    button["rect"].y,
                    button["rect"].width,
                    button["rect"].height,
                ),
                width=2,
            )
            RMS.draw(border_surface, (button["rect"].x, button["rect"].y))

            # Button label
            text_surface = self.font_medium.render(
                button["text"], True, self.text_color
            )
            text_x = button["rect"].centerx - text_surface.get_width() // 2
            text_y = button["rect"].centery - text_surface.get_height() // 2
            RMS.draw(text_surface, (text_x, text_y))

    def set_button_hover(self, button_name: str) -> None:
        """Set hover state for a button (not currently used)."""
        self.button_hover = button_name
