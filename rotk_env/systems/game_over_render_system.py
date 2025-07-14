"""
游戏结束统计渲染系统
Game Over Statistics Render System
"""

from pathlib import Path
import pygame
from typing import Dict, Any
from framework import World, System, RMS
from ..prefabs.config import Faction, GameConfig
from ..components.game_over import Winner, GameStatistics, GameOverButtons


class GameOverRenderSystem(System):
    """游戏结束统计渲染系统"""

    def __init__(self):
        super().__init__()
        self.priority = 1  # 高优先级确保最后渲染

        # 字体
        pygame.font.init()
        file_path = Path("rotk_env/assets/fonts/sh.otf")
        self.font_large = pygame.font.Font(file_path, 48)
        self.font_medium = pygame.font.Font(file_path, 32)
        self.font_small = pygame.font.Font(file_path, 24)

        # 颜色配置
        self.background_color = (20, 20, 30)
        self.text_color = (255, 255, 255)
        self.winner_color = (255, 215, 0)  # 金色
        self.panel_color = (40, 40, 60, 180)

    def initialize(self, world: World) -> None:
        """初始化系统"""
        self.world = world

    def subscribe_events(self) -> None:
        """订阅事件"""

        pass

    def update(self, dt: float) -> None:
        """更新系统"""
        # 清空屏幕
        # RMS.clear()

        # 渲染各个部分
        self._render_background()
        self._render_title()
        self._render_winner_info()
        self._render_statistics()
        self._render_buttons()

        # 执行渲染
        # RMS.present()

    def _render_background(self) -> None:
        """渲染背景面板"""
        screen_width = GameConfig.WINDOW_WIDTH
        screen_height = GameConfig.WINDOW_HEIGHT

        # 填充背景色
        background_surface = pygame.Surface((screen_width, screen_height))
        background_surface.fill(self.background_color)
        RMS.draw(background_surface, (0, 0))

        # 创建主面板
        panel_width = min(800, screen_width - 100)
        panel_height = min(600, screen_height - 100)
        panel_x = (screen_width - panel_width) // 2
        panel_y = (screen_height - panel_height) // 2

        # 创建半透明面板
        panel_surface = pygame.Surface((panel_width, panel_height), pygame.SRCALPHA)
        panel_surface.fill(self.panel_color)
        RMS.draw(panel_surface, (panel_x, panel_y))

        # # 绘制边框
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
        """渲染标题"""
        # 获取屏幕尺寸
        screen_width = GameConfig.WINDOW_WIDTH
        screen_height = GameConfig.WINDOW_HEIGHT

        title_text = "游戏结束"
        title_surface = self.font_large.render(title_text, True, self.text_color)
        title_x = (screen_width - title_surface.get_width()) // 2
        RMS.draw(title_surface, (title_x, 120))

    def _render_winner_info(self) -> None:
        """渲染获胜者信息"""
        # 获取屏幕尺寸
        screen_width = GameConfig.WINDOW_WIDTH

        # 从世界获取获胜者数据
        winner_component = self.world.get_singleton_component(Winner)
        winner = winner_component.faction if winner_component else None

        y_offset = 180

        if winner:
            winner_names = {
                Faction.WEI: "魏国",
                Faction.SHU: "蜀国",
                Faction.WU: "吴国",
            }
            winner_text = f"获胜者: {winner_names.get(winner, str(winner))}"
            winner_surface = self.font_medium.render(
                winner_text, True, self.winner_color
            )
            winner_x = (screen_width - winner_surface.get_width()) // 2
            RMS.draw(winner_surface, (winner_x, y_offset))
        else:
            draw_text = "平局"
            draw_surface = self.font_medium.render(draw_text, True, self.text_color)
            draw_x = (screen_width - draw_surface.get_width()) // 2
            RMS.draw(draw_surface, (draw_x, y_offset))

    def _render_statistics(self) -> None:
        """渲染统计信息"""
        # 获取屏幕尺寸
        screen_width = GameConfig.WINDOW_WIDTH
        screen_height = GameConfig.WINDOW_HEIGHT

        # 从世界获取统计数据
        stats_component = self.world.get_singleton_component(GameStatistics)
        if not stats_component:
            return

        statistics = stats_component.data
        winner_component = self.world.get_singleton_component(Winner)
        winner = winner_component.faction if winner_component else None

        y_offset = 240
        line_height = 30

        # 渲染总体统计
        stats_lines = [
            f"游戏总回合数: {statistics.get('total_turns', 0)}",
            f"游戏时长: {statistics.get('game_duration', 0):.1f}秒",
            f"总单位数: {statistics.get('total_units', 0)}",
            f"存活单位数: {statistics.get('surviving_units', 0)}",
            "",
        ]

        for line in stats_lines:
            if line:
                text_surface = self.font_small.render(line, True, self.text_color)
                text_x = (screen_width - text_surface.get_width()) // 2
                RMS.draw(text_surface, (text_x, y_offset))
            y_offset += line_height

        # 渲染各阵营统计
        faction_names = {Faction.WEI: "魏国", Faction.SHU: "蜀国", Faction.WU: "吴国"}
        faction_stats = statistics.get("faction_stats", {})

        for faction, stats in faction_stats.items():
            faction_name = faction_names.get(faction, str(faction))
            faction_text = f"{faction_name}: {stats.get('surviving_units', 0)}/{stats.get('total_units', 0)} 存活"

            color = self.winner_color if faction == winner else self.text_color
            text_surface = self.font_small.render(faction_text, True, color)
            text_x = (screen_width - text_surface.get_width()) // 2
            RMS.draw(text_surface, (text_x, y_offset))
            y_offset += line_height

    def _render_buttons(self) -> None:
        """渲染按钮"""
        # 从世界获取按钮数据
        button_component = self.world.get_singleton_component(GameOverButtons)
        if not button_component:
            return

        for button_name, button in button_component.buttons.items():
            # 按钮背景
            button_color = (
                button["hover_color"] if button["hover"] else button["default_color"]
            )

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

            # 按钮文字
            text_surface = self.font_medium.render(
                button["text"], True, self.text_color
            )
            text_x = button["rect"].centerx - text_surface.get_width() // 2
            text_y = button["rect"].centery - text_surface.get_height() // 2
            RMS.draw(text_surface, (text_x, text_y))

    def set_button_hover(self, button_name: str) -> None:
        """设置按钮悬停状态"""
        self.button_hover = button_name
