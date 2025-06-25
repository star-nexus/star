"""
开始场景渲染系统
Start Scene Render System
"""

from pathlib import Path
import pygame
from typing import Dict, Any
from framework_v2 import World, System, RMS
from ..prefabs.config import Faction, GameConfig, PlayerType, GameMode
from ..components.start_menu import StartMenuConfig, StartMenuButtons, StartMenuOptions


class StartSceneRenderSystem(System):
    """开始场景渲染系统"""

    def __init__(self):
        super().__init__()
        self.priority = 1

        # 字体
        pygame.font.init()
        file_path = Path("rotk_env/assets/fonts/sh.otf")
        self.font_title = pygame.font.Font(file_path, 64)
        self.font_large = pygame.font.Font(file_path, 48)
        self.font_medium = pygame.font.Font(file_path, 32)
        self.font_small = pygame.font.Font(file_path, 24)

        # 颜色配置
        self.background_color = (15, 25, 35)
        self.panel_color = (30, 40, 60, 200)
        self.text_color = (255, 255, 255)
        self.accent_color = (255, 215, 0)
        self.selected_color = (100, 150, 255)
        self.button_color = (60, 80, 120)
        self.button_hover_color = (80, 100, 140)

        # 状态
        self.hover_button = None
        self.hover_option = None

    def initialize(self, world: World) -> None:
        """初始化系统"""
        self.world = world
        pass

    def subscribe_events(self) -> None:
        """订阅事件"""
        pass

    def update(self, dt: float) -> None:
        """更新系统"""
        # 清空屏幕

        # 渲染各个部分
        self._render_background()
        self._render_title()
        self._render_config_panel()
        self._render_buttons()

    def _render_background(self) -> None:
        """渲染背景"""
        # 获取屏幕尺寸
        screen_width = GameConfig.WINDOW_WIDTH
        screen_height = GameConfig.WINDOW_HEIGHT

        # 渲染渐变背景
        background_surface = pygame.Surface((screen_width, screen_height))

        # 简单的渐变效果
        for y in range(screen_height):
            color_factor = y / screen_height
            r = int(self.background_color[0] * (1 + color_factor * 0.3))
            g = int(self.background_color[1] * (1 + color_factor * 0.3))
            b = int(self.background_color[2] * (1 + color_factor * 0.3))
            color = (min(255, r), min(255, g), min(255, b))
            pygame.draw.line(background_surface, color, (0, y), (screen_width, y))

        RMS.draw(background_surface, (0, 0))

    def _render_title(self) -> None:
        """渲染标题"""
        # 获取屏幕尺寸
        screen_width = GameConfig.WINDOW_WIDTH
        screen_height = GameConfig.WINDOW_HEIGHT

        # 主标题
        title_text = "三国策略游戏"
        title_surface = self.font_title.render(title_text, True, self.accent_color)
        title_x = (screen_width - title_surface.get_width()) // 2
        RMS.draw(title_surface, (title_x, 60))

        # 副标题
        subtitle_text = "Romance of the Three Kingdoms"
        subtitle_surface = self.font_medium.render(subtitle_text, True, self.text_color)
        subtitle_x = (screen_width - subtitle_surface.get_width()) // 2
        RMS.draw(subtitle_surface, (subtitle_x, 130))

    def _render_config_panel(self) -> None:
        """渲染配置面板"""
        # 获取屏幕尺寸
        screen_width = GameConfig.WINDOW_WIDTH
        screen_height = GameConfig.WINDOW_HEIGHT

        config = self.world.get_singleton_component(StartMenuConfig)
        if not config:
            return

        # 面板位置和尺寸
        panel_width = 600
        panel_height = 400
        panel_x = (screen_width - panel_width) // 2
        panel_y = 200

        # 渲染面板背景
        panel_surface = pygame.Surface((panel_width, panel_height), pygame.SRCALPHA)
        panel_surface.fill(self.panel_color)
        RMS.draw(panel_surface, (panel_x, panel_y))

        # 渲染边框
        border_surface = pygame.Surface((panel_width, panel_height), pygame.SRCALPHA)
        pygame.draw.rect(
            border_surface, self.accent_color, (0, 0, panel_width, panel_height), 2
        )
        RMS.draw(border_surface, (panel_x, panel_y))

        # 渲染配置选项
        y_offset = panel_y + 30
        self._render_mode_config(config, panel_x, y_offset)

        y_offset += 100
        self._render_player_config(config, panel_x, y_offset)

        # y_offset += 150
        # self._render_scenario_config(config, panel_x, y_offset)

    def _render_mode_config(self, config: StartMenuConfig, x: int, y: int) -> None:
        """渲染游戏模式配置"""
        # 标题
        title_surface = self.font_large.render("游戏模式", True, self.text_color)
        RMS.draw(title_surface, (x + 30, y))

        # 模式选项
        mode_options = [(GameMode.TURN_BASED, "回合制"), (GameMode.REAL_TIME, "实时制")]

        option_x = x + 50
        option_y = y + 60
        for i, (mode, name) in enumerate(mode_options):
            color = (
                self.selected_color if mode == config.selected_mode else self.text_color
            )
            option_surface = self.font_small.render(f"○ {name}", True, color)
            if mode == config.selected_mode:
                option_surface = self.font_small.render(f"● {name}", True, color)

            RMS.draw(option_surface, (option_x + i * 150, option_y))

    def _render_player_config(self, config: StartMenuConfig, x: int, y: int) -> None:
        """渲染玩家配置"""
        # 标题
        title_surface = self.font_large.render("玩家配置", True, self.text_color)
        RMS.draw(title_surface, (x + 30, y))

        # 玩家配置选项
        player_configs = [
            ({Faction.WEI: PlayerType.HUMAN, Faction.SHU: PlayerType.AI}, "人机对战"),
            ({Faction.WEI: PlayerType.AI, Faction.SHU: PlayerType.AI}, "AI对战"),
            (
                {
                    Faction.WEI: PlayerType.HUMAN,
                    Faction.SHU: PlayerType.AI,
                    Faction.WU: PlayerType.AI,
                },
                "三国模式",
            ),
        ]

        option_y = y + 60
        for i, (players, name) in enumerate(player_configs):
            is_selected = self._compare_player_configs(config.selected_players, players)
            color = self.selected_color if is_selected else self.text_color
            option_surface = self.font_small.render(f"○ {name}", True, color)
            if is_selected:
                option_surface = self.font_small.render(f"● {name}", True, color)

            RMS.draw(option_surface, (x + 50, option_y + i * 30))

    def _render_scenario_config(self, config: StartMenuConfig, x: int, y: int) -> None:
        """渲染场景配置"""
        # 标题
        title_surface = self.font_large.render("地图场景", True, self.text_color)
        RMS.draw(title_surface, (x + 30, y))

        # 场景选项
        scenarios = [
            ("default", "默认地图"),
            ("plains", "平原之战"),
            ("mountains", "山地征战"),
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
        """比较两个玩家配置是否相同"""
        if len(config1) != len(config2):
            return False
        for faction, player_type in config1.items():
            if faction not in config2 or config2[faction] != player_type:
                return False
        return True

    def _render_buttons(self) -> None:
        """渲染按钮"""
        button_component = self.world.get_singleton_component(StartMenuButtons)
        if not button_component:
            return

        for button_name, button in button_component.buttons.items():
            # 按钮背景
            is_hover = button_name == self.hover_button
            button_color = self.button_hover_color if is_hover else self.button_color

            # 创建按钮背景surface
            button_surface = pygame.Surface(
                (button["rect"].width, button["rect"].height)
            )
            button_surface.fill(button_color)
            RMS.draw(button_surface, (button["rect"].x, button["rect"].y))

            # 创建边框surface
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

            # 按钮文字
            text_color = self.accent_color if is_hover else self.text_color
            text_surface = self.font_large.render(button["text"], True, text_color)
            text_x = button["rect"].centerx - text_surface.get_width() // 2
            text_y = button["rect"].centery - text_surface.get_height() // 2
            RMS.draw(text_surface, (text_x, text_y))

    def set_hover_button(self, button_name: str) -> None:
        """设置悬停按钮"""
        self.hover_button = button_name

    def set_hover_option(self, option_name: str) -> None:
        """设置悬停选项"""
        self.hover_option = option_name
