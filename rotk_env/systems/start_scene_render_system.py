"""
Start Scene Render System
"""

from pathlib import Path
import pygame
from typing import Dict, Any
from framework import World, System, RMS
from ..prefabs.config import Faction, GameConfig, PlayerType, GameMode
from ..components.start_menu import StartMenuConfig, StartMenuButtons, StartMenuOptions


class StartSceneRenderSystem(System):
    """Start scene render system"""

    def __init__(self):
        super().__init__()
        self.priority = 1

        pygame.font.init()
        self._initialize_font_system()

        self.background_color = (15, 25, 35)
        self.panel_color = (30, 40, 60, 200)
        self.text_color = (255, 255, 255)
        self.accent_color = (255, 215, 0)
        self.selected_color = (100, 150, 255)
        self.button_color = (60, 80, 120)
        self.button_hover_color = (80, 100, 140)

        self.hover_button = None
        self.hover_option = None

    def _initialize_font_system(self) -> None:
        """Initialize professional font system"""
        try:
            custom_font_path = Path("rotk_env/assets/fonts/sh.otf")
            if custom_font_path.exists():
                self._load_custom_fonts(custom_font_path)
            else:
                self._load_system_fonts()
        except Exception as e:
            print(f"Font loading failed, falling back to system default font: {e}")
            self._load_system_fonts()

    def _load_custom_fonts(self, font_path: Path) -> None:
        """Load custom font"""
        self.font_title = self._load_title_font(52)
        self.font_subtitle = pygame.font.Font(font_path, 24)

        self.font_large = pygame.font.Font(font_path, 36)
        self.font_medium = pygame.font.Font(font_path, 28)
        self.font_small = pygame.font.Font(font_path, 22)
        self.font_button = pygame.font.Font(font_path, 18)

    def _load_title_font(self, size: int) -> pygame.font.Font:
        """Load a dedicated font for the title - prioritize fonts with a sense of history"""
        # Priority list of historical-style fonts for the title
        title_fonts = [
            "Trajan-Regular.ttf",      # Roman style, solemn and elegant
            "Cinzel-Regular.ttf",      # Classical-modern fusion
            "IM-Fell-Double-Pica.ttf", # Rustic and weighty
            "CinzelDecorative-Regular.ttf", # Decorative classical
        ]
        
        for font_name in title_fonts:
            try:
                font_path = Path(f"rotk_env/assets/fonts/{font_name}")
                if font_path.exists():
                    print(f"Using title font: {font_name}")
                    return pygame.font.Font(font_path, size)
            except Exception as e:
                print(f"Failed to load font {font_name}: {e}")
                continue
        
        # If no professional font is found, fall back to the default font
        print("Falling back to default font for title")
        return pygame.font.Font(Path("rotk_env/assets/fonts/sh.otf"), size)

    def _load_system_fonts(self) -> None:
        """Load system fonts as fallback"""
        self.font_title = pygame.font.Font(None, 52)
        self.font_subtitle = pygame.font.Font(None, 24)

        self.font_large = pygame.font.Font(None, 36)
        self.font_medium = pygame.font.Font(None, 28)
        self.font_small = pygame.font.Font(None, 22)
        self.font_button = pygame.font.Font(None, 18)

    def _render_text_with_style(self, text: str, font: pygame.font.Font, color: tuple, 
                               x: int, y: int, center_x: bool = False, 
                               shadow: bool = False, shadow_offset: tuple = (2, 2)) -> None:
        """Text rendering method"""
        # Render shadow (if needed)
        if shadow:
            shadow_surface = font.render(text, True, (0, 0, 0, 120))
            shadow_x = x + shadow_offset[0] if not center_x else x
            shadow_y = y + shadow_offset[1]
            if center_x:
                shadow_x = x - shadow_surface.get_width() // 2
            RMS.draw(shadow_surface, (shadow_x, shadow_y))
        
        # Render main text
        text_surface = font.render(text, True, color)
        text_x = x - text_surface.get_width() // 2 if center_x else x
        RMS.draw(text_surface, (text_x, y))

    def initialize(self, world: World) -> None:
        """Initialize the system"""
        self.world = world
        pass

    def subscribe_events(self) -> None:
        """Subscribe to events"""
        pass

    def update(self, dt: float) -> None:
        """Update the system"""
        # Clear screen

        # Render each part
        self._render_background()
        self._render_title()
        self._render_config_panel()
        self._render_buttons()

    def _render_background(self) -> None:
        """Render background"""
        # Get screen size
        screen_width = GameConfig.WINDOW_WIDTH
        screen_height = GameConfig.WINDOW_HEIGHT

        # Render gradient background
        background_surface = pygame.Surface((screen_width, screen_height))

        # Simple gradient effect
        for y in range(screen_height):
            color_factor = y / screen_height
            r = int(self.background_color[0] * (1 + color_factor * 0.3))
            g = int(self.background_color[1] * (1 + color_factor * 0.3))
            b = int(self.background_color[2] * (1 + color_factor * 0.3))
            color = (min(255, r), min(255, g), min(255, b))
            pygame.draw.line(background_surface, color, (0, y), (screen_width, y))

        RMS.draw(background_surface, (0, 0))

    def _render_title(self) -> None:
        """Render title"""
        # Get screen size
        screen_width = GameConfig.WINDOW_WIDTH
        screen_height = GameConfig.WINDOW_HEIGHT

        # Main title - enhanced version
        title_text = "Romance of the Three Kingdoms"
        self._render_enhanced_title(title_text, screen_width, 60)

        # Subtitle - use elegant rendering method
        subtitle_text = "A strategic and tactical reasoning environment for LLM adversarial play"
        self._render_text_with_style(
            subtitle_text, 
            self.font_subtitle, 
            self.text_color, 
            screen_width // 2, 
            130, 
            center_x=True, 
            shadow=True
        )

    def _render_enhanced_title(self, text: str, screen_width: int, y: int) -> None:
        """Render enhanced main title - bold, shadow, glow effect"""
        bold_offset = 1  # Reduce bold offset
        
        # Render shadow effect
        shadow_surface = self.font_title.render(text, True, (0, 0, 0, 120))  # Reduce shadow transparency
        title_x = (screen_width - shadow_surface.get_width()) // 2
        RMS.draw(shadow_surface, (title_x + 2, y + 2))  # Reduce shadow offset
        
        # Render bold effect - reduce direction
        bold_directions = [
            (bold_offset, 0), (-bold_offset, 0),  # Horizontal bold
            (0, bold_offset), (0, -bold_offset),  # Vertical bold
        ]
        
        for dx, dy in bold_directions:
            bold_surface = self.font_title.render(text, True, self.accent_color)
            RMS.draw(bold_surface, (title_x + dx, y + dy))
        
        # Render main text
        main_surface = self.font_title.render(text, True, self.accent_color)
        RMS.draw(main_surface, (title_x, y))
        
        # Render glow effect
        self._render_title_glow(text, title_x, y)

    def _render_title_glow(self, text: str, x: int, y: int) -> None:
        """Render title glow effect - gentle version"""
        # Render once to get size
        temp_surface = self.font_title.render(text, True, (255, 255, 255))
        text_width = temp_surface.get_width()
        text_height = temp_surface.get_height()
        
        # Create glow surface - reduce size
        glow_surface = pygame.Surface((text_width + 20, text_height + 20), pygame.SRCALPHA)
        
        # Render gentle glow effect - reduce layers and strength
        for i in range(3, 0, -1):
            alpha = max(0, 15 - i * 4)  # Reduce transparency
            glow_color = (*self.accent_color, alpha)
            glow_text = self.font_title.render(text, True, glow_color)
            glow_x = 10 - i * 2
            glow_y = 10 - i * 2
            glow_surface.blit(glow_text, (glow_x, glow_y))
        
        RMS.draw(glow_surface, (x - 10, y - 10))

    def _render_config_panel(self) -> None:
        """Render config panel"""
        # Get screen size
        screen_width = GameConfig.WINDOW_WIDTH
        screen_height = GameConfig.WINDOW_HEIGHT

        config = self.world.get_singleton_component(StartMenuConfig)
        if not config:
            return

        # Panel position and size
        panel_width = 600
        panel_height = 400
        panel_x = (screen_width - panel_width) // 2
        panel_y = 200

        # Render panel background
        panel_surface = pygame.Surface((panel_width, panel_height), pygame.SRCALPHA)
        panel_surface.fill(self.panel_color)
        RMS.draw(panel_surface, (panel_x, panel_y))

        # Render border
        border_surface = pygame.Surface((panel_width, panel_height), pygame.SRCALPHA)
        pygame.draw.rect(
            border_surface, self.accent_color, (0, 0, panel_width, panel_height), 2
        )
        RMS.draw(border_surface, (panel_x, panel_y))

        # Render config options
        y_offset = panel_y + 30
        self._render_mode_config(config, panel_x, y_offset)

        y_offset += 160  # Increase spacing to fit new line spacing
        self._render_player_config(config, panel_x, y_offset)

        # y_offset += 150
        # self._render_scenario_config(config, panel_x, y_offset)

    def _render_mode_config(self, config: StartMenuConfig, x: int, y: int) -> None:
        """Render game mode config"""
        self._render_text_with_style(
            "Battle Mode", 
            self.font_medium, 
            self.text_color, 
            x + 30, 
            y, 
            shadow=True
        )

        # Mode options
        mode_options = [
            (GameMode.TURN_BASED, "Strategic Turn-Based"), 
            (GameMode.REAL_TIME, "Dynamic Real-Time")
        ]

        option_x = x + 50
        option_y = y + 60
        for i, (mode, name) in enumerate(mode_options):
            color = (
                self.selected_color if mode == config.selected_mode else self.text_color
            )
            option_surface = self.font_small.render(f"○ {name}", True, color)
            if mode == config.selected_mode:
                option_surface = self.font_small.render(f"● {name}", True, color)

            RMS.draw(option_surface, (option_x, option_y + i * 45))

    def _render_player_config(self, config: StartMenuConfig, x: int, y: int) -> None:
        """Render player config"""
        self._render_text_with_style(
            "Player Configuration", 
            self.font_medium, 
            self.text_color, 
            x + 30, 
            y, 
            shadow=True
        )

        # Player config options
        player_configs = [
            ({Faction.WEI: PlayerType.HUMAN, Faction.SHU: PlayerType.AI}, "Human Commander vs AI Strategist"),
            ({Faction.WEI: PlayerType.AI, Faction.SHU: PlayerType.AI}, "AI vs AI Battle"),
            (
                {
                    Faction.WEI: PlayerType.AI,
                    Faction.SHU: PlayerType.AI,
                    Faction.WU: PlayerType.AI,
                },
                "Three Kingdoms Epic",
            ),
        ]

        option_y = y + 60
        for i, (players, name) in enumerate(player_configs):
            is_selected = self._compare_player_configs(config.selected_players, players)
            color = self.selected_color if is_selected else self.text_color
            option_surface = self.font_small.render(f"○ {name}", True, color)
            if is_selected:
                option_surface = self.font_small.render(f"● {name}", True, color)

            # Use the same line spacing as the game mode
            RMS.draw(option_surface, (x + 50, option_y + i * 45))

    def _render_scenario_config(self, config: StartMenuConfig, x: int, y: int) -> None:
        """Render scenario config"""
        title_surface = self.font_large.render("Map Scenario", True, self.text_color)
        RMS.draw(title_surface, (x + 30, y))

        # Scenario options
        scenarios = [
            ("default", "Default Map"),
            ("plains", "Plains Campaign"),
            ("mountains", "Mountains Campaign"),
        ]

        option_y = y + 40
        for i, (scenario_id, name) in enumerate(scenarios):
            is_selected = config.selected_scenario == scenario_id
            color = self.selected_color if is_selected else self.text_color
            option_surface = self.font_small.render(f"○ {name}", True, color)
            if is_selected:
                option_surface = self.font_small.render(f"● {name}", True, color)

            RMS.draw(option_surface, (x + 50, option_y + i * 30))

    def _compare_player_configs(
        self, config1: Dict[Faction, PlayerType], config2: Dict[Faction, PlayerType]
    ) -> bool:
        """Compare two player configurations for equality"""
        if len(config1) != len(config2):
            return False
        for faction, player_type in config1.items():
            if faction not in config2 or config2[faction] != player_type:
                return False
        return True

    def _render_buttons(self) -> None:
        """Render buttons"""
        button_component = self.world.get_singleton_component(StartMenuButtons)
        if not button_component:
            return

        for button_name, button in button_component.buttons.items():
            # Button background
            is_hover = button_name == self.hover_button
            button_color = self.button_hover_color if is_hover else self.button_color

            # Create button background surface
            button_surface = pygame.Surface(
                (button["rect"].width, button["rect"].height)
            )
            button_surface.fill(button_color)
            RMS.draw(button_surface, (button["rect"].x, button["rect"].y))

            # Create border surface
            border_surface = pygame.Surface(
                (button["rect"].width, button["rect"].height), pygame.SRCALPHA
            )
            border_color = self.accent_color if is_hover else self.text_color
            pygame.draw.rect(
                border_surface,
                border_color,
                (0, 0, button["rect"].width, button["rect"].height),
                2,
            )
            RMS.draw(border_surface, (button["rect"].x, button["rect"].y))

            # Button text
            text_color = self.accent_color if is_hover else self.text_color
            text_surface = self.font_button.render(button["text"], True, text_color)
            text_x = button["rect"].centerx - text_surface.get_width() // 2
            text_y = button["rect"].centery - text_surface.get_height() // 2
            RMS.draw(text_surface, (text_x, text_y))

    def set_hover_button(self, button_name: str) -> None:
        """Set hover button"""
        self.hover_button = button_name

    def set_hover_option(self, option_name: str) -> None:
        """Set hover option"""
        self.hover_option = option_name
