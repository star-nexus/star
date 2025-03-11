import pygame
from typing import Dict, Any
from engine.scene_base import BaseScene


class MainMenuScene(BaseScene):
    """主菜单场景"""

    def __init__(self, engine):
        super().__init__(engine)
        self.title_font = None
        self.menu_font = None

    def initialize(self) -> None:
        """初始化主菜单场景"""
        # 调用父类初始化
        super().initialize()

        # 设置特定字体
        self.title_font = self.fonts["title"]
        self.menu_font = self.fonts["default_large"]

        # 添加开始游戏事件监听器
        self.engine.event_manager.add_listener("key_down", self.on_key_down)

        # 如果有游戏状态管理器，重置游戏数据
        if hasattr(self.engine, "game_state_manager"):
            self.engine.game_state_manager.reset_game_data()

    def setup_ui(self) -> None:
        """设置菜单UI"""
        if not hasattr(self.engine, "ui_manager"):
            return

        ui_manager = self.engine.ui_manager
        screen_width, screen_height = self.engine.screen.get_size()

        # 创建菜单面板
        menu_panel = ui_manager.create_panel(
            "main_menu", 0, 0, screen_width, screen_height, color=None
        )

        # 添加标题
        ui_manager.create_text_label(
            "main_menu",
            screen_width // 2,
            200,
            "My Pygame Game",
            font_name="title",
            color=(255, 255, 255),
            align="center",
        )

        # 添加开始游戏按钮
        ui_manager.create_button(
            "main_menu",
            screen_width // 2 - 100,
            300,
            200,
            50,
            "Start Game",
            font_name="default_large",
            normal_color=(80, 80, 80),
            hover_color=(100, 100, 100),
            on_click=self.start_game,
        )

        # 添加退出游戏按钮
        ui_manager.create_button(
            "main_menu",
            screen_width // 2 - 100,
            380,
            200,
            50,
            "Exit Game",
            font_name="default_large",
            normal_color=(80, 80, 80),
            hover_color=(100, 100, 100),
            on_click=self.exit_game,
        )

    def start_game(self) -> None:
        """开始游戏"""
        if hasattr(self.engine, "game_state_manager"):
            self.engine.game_state_manager.change_state("playing")
        else:
            self.engine.scene_manager.change_scene("game")

    def exit_game(self) -> None:
        """退出游戏"""
        self.engine.running = False

    def on_key_down(self, key) -> None:
        """处理按键事件"""
        if key == pygame.K_RETURN:
            self.start_game()
        elif key == pygame.K_ESCAPE:
            self.exit_game()

    def render(self, surface: pygame.Surface) -> None:
        """渲染主菜单"""
        # 当使用UI管理器时，不需要在这里渲染UI元素
        # 如果没有UI管理器，则使用传统方式渲染
        if not hasattr(self.engine, "ui_manager"):
            # 调用父类渲染方法渲染实体和地图
            super().render(surface)

            # 渲染标题
            title_text = self.title_font.render("My Pygame Game", True, (255, 255, 255))
            title_rect = title_text.get_rect(center=(surface.get_width() // 2, 200))
            surface.blit(title_text, title_rect)

            # 渲染菜单选项
            start_text = self.menu_font.render(
                "Press ENTER to Start", True, (200, 200, 200)
            )
            start_rect = start_text.get_rect(center=(surface.get_width() // 2, 300))
            surface.blit(start_text, start_rect)

            exit_text = self.menu_font.render(
                "Press ESC to Exit", True, (200, 200, 200)
            )
            exit_rect = exit_text.get_rect(center=(surface.get_width() // 2, 350))
            surface.blit(exit_text, exit_rect)

    def on_exit(self) -> None:
        """离开场景时清理资源"""
        self.engine.event_manager.remove_listener("key_down", self.on_key_down)

        # 移除UI面板
        if hasattr(self.engine, "ui_manager"):
            self.engine.ui_manager.remove_panel("main_menu")
