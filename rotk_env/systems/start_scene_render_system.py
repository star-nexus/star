"""Start Scene Render System."""

from pathlib import Path
from typing import Dict

import pygame
from framework import World, System
from framework.engine import RMS

from ..prefabs.config import Faction, GameConfig, PlayerType, GameMode
from ..components.start_menu import (
    StartMenuConfig,
    StartMenuButtons,
    START_PLAYER_OPTIONS,
    START_CONTROLLER_OPTIONS,
    start_panel_layout,
    clamp_scenario_scroll,
    START_SCENARIO_COLS,
    START_SCENARIO_COL_W,
    START_SCENARIO_ROW_H,
)


class StartSceneRenderSystem(System):
    """Render the start scene with topology and controller backend separated."""

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

    def _initialize_font_system(self) -> None:
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
        self.font_title = self._load_title_font(52)
        self.font_subtitle = pygame.font.Font(font_path, 24)
        self.font_large = pygame.font.Font(font_path, 36)
        self.font_medium = pygame.font.Font(font_path, 28)
        self.font_small = pygame.font.Font(font_path, 22)
        self.font_button = pygame.font.Font(font_path, 18)

    def _load_title_font(self, size: int) -> pygame.font.Font:
        title_fonts = [
            "Trajan-Regular.ttf",
            "Cinzel-Regular.ttf",
            "IM-Fell-Double-Pica.ttf",
            "CinzelDecorative-Regular.ttf",
        ]
        for font_name in title_fonts:
            try:
                font_path = Path(f"rotk_env/assets/fonts/{font_name}")
                if font_path.exists():
                    print(f"Using title font: {font_name}")
                    return pygame.font.Font(font_path, size)
            except Exception as e:
                print(f"Failed to load font {font_name}: {e}")
        print("Falling back to default font for title")
        return pygame.font.Font(Path("rotk_env/assets/fonts/sh.otf"), size)

    def _load_system_fonts(self) -> None:
        self.font_title = pygame.font.Font(None, 52)
        self.font_subtitle = pygame.font.Font(None, 24)
        self.font_large = pygame.font.Font(None, 36)
        self.font_medium = pygame.font.Font(None, 28)
        self.font_small = pygame.font.Font(None, 22)
        self.font_button = pygame.font.Font(None, 18)

    def _render_text_with_style(
        self,
        text: str,
        font: pygame.font.Font,
        color: tuple,
        x: int,
        y: int,
        center_x: bool = False,
        shadow: bool = False,
        shadow_offset: tuple = (2, 2),
    ) -> None:
        if shadow:
            shadow_surface = font.render(text, True, (0, 0, 0, 120))
            shadow_x = x if center_x else x + shadow_offset[0]
            if center_x:
                shadow_x -= shadow_surface.get_width() // 2
            RMS.draw(shadow_surface, (shadow_x, y + shadow_offset[1]))

        text_surface = font.render(text, True, color)
        text_x = x - text_surface.get_width() // 2 if center_x else x
        RMS.draw(text_surface, (text_x, y))

    def initialize(self, world: World) -> None:
        self.world = world

    def subscribe_events(self) -> None:
        pass

    def update(self, dt: float) -> None:
        self._render_background()
        self._render_title()
        self._render_config_panel()
        self._render_buttons()

    def _render_background(self) -> None:
        screen_width = GameConfig.WINDOW_WIDTH
        screen_height = GameConfig.WINDOW_HEIGHT
        background_surface = pygame.Surface((screen_width, screen_height))
        for y in range(screen_height):
            color_factor = y / screen_height
            r = int(self.background_color[0] * (1 + color_factor * 0.3))
            g = int(self.background_color[1] * (1 + color_factor * 0.3))
            b = int(self.background_color[2] * (1 + color_factor * 0.3))
            color = (min(255, r), min(255, g), min(255, b))
            pygame.draw.line(background_surface, color, (0, y), (screen_width, y))
        RMS.draw(background_surface, (0, 0))

    def _render_title(self) -> None:
        screen_width = GameConfig.WINDOW_WIDTH
        self._render_enhanced_title("Romance of the Three Kingdoms", screen_width, 60)
        self._render_text_with_style(
            "A strategic and tactical reasoning environment for LLM adversarial play",
            self.font_subtitle,
            self.text_color,
            screen_width // 2,
            130,
            center_x=True,
            shadow=True,
        )

    def _render_enhanced_title(self, text: str, screen_width: int, y: int) -> None:
        bold_offset = 1
        shadow_surface = self.font_title.render(text, True, (0, 0, 0, 120))
        title_x = (screen_width - shadow_surface.get_width()) // 2
        RMS.draw(shadow_surface, (title_x + 2, y + 2))
        for dx, dy in [
            (bold_offset, 0),
            (-bold_offset, 0),
            (0, bold_offset),
            (0, -bold_offset),
        ]:
            RMS.draw(
                self.font_title.render(text, True, self.accent_color),
                (title_x + dx, y + dy),
            )
        RMS.draw(self.font_title.render(text, True, self.accent_color), (title_x, y))
        self._render_title_glow(text, title_x, y)

    def _render_title_glow(self, text: str, x: int, y: int) -> None:
        temp_surface = self.font_title.render(text, True, (255, 255, 255))
        glow_surface = pygame.Surface(
            (temp_surface.get_width() + 20, temp_surface.get_height() + 20),
            pygame.SRCALPHA,
        )
        for i in range(3, 0, -1):
            alpha = max(0, 15 - i * 4)
            glow_text = self.font_title.render(
                text, True, (*self.accent_color, alpha)
            )
            glow_surface.blit(glow_text, (10 - i * 2, 10 - i * 2))
        RMS.draw(glow_surface, (x - 10, y - 10))

    def _render_config_panel(self) -> None:
        config = self.world.get_singleton_component(StartMenuConfig)
        if not config:
            return

        geom = start_panel_layout(len(config.scenario_catalog or []))
        panel_width = geom["panel_width"]
        panel_height = geom["panel_height"]
        panel_x = geom["panel_x"]
        panel_y = geom["panel_y"]

        panel_surface = pygame.Surface((panel_width, panel_height), pygame.SRCALPHA)
        panel_surface.fill(self.panel_color)
        RMS.draw(panel_surface, (panel_x, panel_y))

        border_surface = pygame.Surface((panel_width, panel_height), pygame.SRCALPHA)
        pygame.draw.rect(
            border_surface,
            self.accent_color,
            (0, 0, panel_width, panel_height),
            2,
        )
        RMS.draw(border_surface, (panel_x, panel_y))

        self._render_mode_config(config, panel_x, geom["mode_y"])
        self._render_player_config(config, panel_x, geom["player_y"])
        self._render_controller_config(config, panel_x, geom)
        self._render_scenario_config(config, geom)

    def _render_mode_config(self, config: StartMenuConfig, x: int, y: int) -> None:
        self._render_text_with_style(
            "Battle Mode", self.font_medium, self.text_color, x + 30, y, shadow=True
        )
        mode_options = [
            (GameMode.TURN_BASED, "Strategic Turn-Based"),
            (GameMode.REAL_TIME, "Dynamic Real-Time"),
        ]
        option_y = y + 60
        for i, (mode, name) in enumerate(mode_options):
            selected = mode == config.selected_mode
            color = self.selected_color if selected else self.text_color
            marker = "●" if selected else "○"
            RMS.draw(
                self.font_small.render(f"{marker} {name}", True, color),
                (x + 50, option_y + i * 45),
            )

    def _render_player_config(self, config: StartMenuConfig, x: int, y: int) -> None:
        self._render_text_with_style(
            "Player Topology",
            self.font_medium,
            self.text_color,
            x + 30,
            y,
            shadow=True,
        )
        option_y = y + 60
        for i, (players, name) in enumerate(START_PLAYER_OPTIONS):
            selected = self._compare_player_configs(config.selected_players, players)
            color = self.selected_color if selected else self.text_color
            marker = "●" if selected else "○"
            RMS.draw(
                self.font_small.render(f"{marker} {name}", True, color),
                (x + 50, option_y + i * 45),
            )

    def _render_controller_config(
        self, config: StartMenuConfig, x: int, geom: Dict[str, int]
    ) -> None:
        y = geom["controller_y"]
        self._render_text_with_style(
            "AI Controller Backend",
            self.font_medium,
            self.text_color,
            x + 30,
            y,
            shadow=True,
        )
        option_y = geom["controller_option_y"]
        spacing = geom["controller_spacing"]
        for i, (backend, name) in enumerate(START_CONTROLLER_OPTIONS):
            selected = backend == config.selected_controller_backend
            color = self.selected_color if selected else self.text_color
            marker = "●" if selected else "○"
            RMS.draw(
                self.font_small.render(f"{marker} {name}", True, color),
                (x + 50, option_y + i * spacing),
            )

    def _render_scenario_config(self, config: StartMenuConfig, geom: Dict[str, int]) -> None:
        x = geom["panel_x"]
        y = geom["scenario_y"]
        self._render_text_with_style(
            "Map Scenario",
            self.font_medium,
            self.text_color,
            x + 30,
            y,
            shadow=True,
        )

        option_y = geom["scenario_option_y"]
        visible_rows = geom["scenario_visible_rows"]
        catalog = config.scenario_catalog or []
        scroll = clamp_scenario_scroll(config.scenario_scroll, len(catalog), geom)
        for i, item in enumerate(catalog):
            vis_row = i // START_SCENARIO_COLS - scroll
            if vis_row < 0 or vis_row >= visible_rows:
                continue
            scenario_id = item["scenario"]
            label = f"{item['name']} {item['width']}×{item['height']}"
            selected = config.selected_scenario == scenario_id or (
                config.selected_scenario in ("default", "three_kingdoms")
                and scenario_id == "river_split"
            )
            color = self.selected_color if selected else self.text_color
            marker = "●" if selected else "○"
            col = i % START_SCENARIO_COLS
            RMS.draw(
                self.font_small.render(f"{marker} {label}", True, color),
                (
                    x + 50 + col * START_SCENARIO_COL_W,
                    option_y + vis_row * START_SCENARIO_ROW_H,
                ),
            )

    def _compare_player_configs(
        self, config1: Dict[Faction, PlayerType], config2: Dict[Faction, PlayerType]
    ) -> bool:
        return config1 == config2

    def _render_buttons(self) -> None:
        button_component = self.world.get_singleton_component(StartMenuButtons)
        if not button_component:
            return

        for button in button_component.buttons.values():
            is_hover = bool(button.get("hover"))
            button_color = self.button_hover_color if is_hover else self.button_color
            button_surface = pygame.Surface(
                (button["rect"].width, button["rect"].height)
            )
            button_surface.fill(button_color)
            RMS.draw(button_surface, (button["rect"].x, button["rect"].y))

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

            text_color = self.accent_color if is_hover else self.text_color
            text_surface = self.font_button.render(button["text"], True, text_color)
            RMS.draw(
                text_surface,
                (
                    button["rect"].centerx - text_surface.get_width() // 2,
                    button["rect"].centery - text_surface.get_height() // 2,
                ),
            )
