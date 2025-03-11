import pygame
from typing import Dict, Any
from engine.scene_base import BaseScene


class VictoryScene(BaseScene):
    """游戏胜利场景"""

    def __init__(self, engine):
        super().__init__(engine)
        self.title_font = None
        self.info_font = None
        self.score = 0

    def initialize(self) -> None:
        """初始化胜利场景"""
        # 调用父类初始化
        super().initialize()

        # 设置特定字体
        self.title_font = self.fonts["title"]
        self.info_font = self.fonts["default_large"]

        # 从游戏状态管理器获取分数
        game_data = self.get_game_data()
        self.score = game_data.get("score", 0)

        # 添加事件监听器
        self.engine.event_manager.add_listener("key_down", self.on_key_down)

    def setup_ui(self) -> None:
        """设置胜利场景UI"""
        if not hasattr(self.engine, "ui_manager"):
            return

        ui_manager = self.engine.ui_manager
        screen_width, screen_height = self.engine.screen.get_size()

        # 创建胜利面板
        victory_panel = ui_manager.create_panel(
            "victory", 0, 0, screen_width, screen_height, color=(0, 0, 0), alpha=180
        )

        # 添加胜利标题
        ui_manager.create_text_label(
            "victory",
            screen_width // 2,
            screen_height // 2 - 50,
            "Victory!",
            font_name="title",
            color=(255, 215, 0),
            align="center",
        )

        # 添加得分显示
        ui_manager.create_text_label(
            "victory",
            screen_width // 2,
            screen_height // 2 + 20,
            f"Score: {self.score}",
            font_name="default_large",
            color=(255, 255, 255),
            align="center",
        )

        # 添加返回菜单按钮
        ui_manager.create_button(
            "victory",
            screen_width // 2 - 100,
            screen_height // 2 + 70,
            200,
            40,
            "Return to Menu",
            font_name="default_large",
            normal_color=(80, 80, 80),
            hover_color=(100, 100, 100),
            on_click=self.return_to_menu,
        )

        # 添加重新开始按钮
        ui_manager.create_button(
            "victory",
            screen_width // 2 - 100,
            screen_height // 2 + 120,
            200,
            40,
            "Restart Game",
            font_name="default_large",
            normal_color=(80, 80, 80),
            hover_color=(100, 100, 100),
            on_click=self.restart_game,
        )

    def return_to_menu(self) -> None:
        """返回主菜单"""
        if hasattr(self.engine, "game_state_manager"):
            self.engine.game_state_manager.change_state("menu")
        else:
            self.engine.scene_manager.change_scene("menu")

    def restart_game(self) -> None:
        """重新开始游戏"""
        if hasattr(self.engine, "game_state_manager"):
            self.engine.game_state_manager.reset_game_data()
            self.engine.game_state_manager.change_state("playing")
        else:
            self.engine.scene_manager.change_scene("game")

    def on_key_down(self, key) -> None:
        """处理按键事件"""
        if key == pygame.K_RETURN:
            self.return_to_menu()
        elif key == pygame.K_r:
            self.restart_game()

    def render(self, surface: pygame.Surface) -> None:
        """渲染胜利场景"""
        # 当使用UI管理器时，不需要在这里渲染UI元素
        # 如果没有UI管理器，则使用传统方式渲染
        if not hasattr(self.engine, "ui_manager"):
            # 调用父类渲染方法渲染实体和地图
            super().render(surface)

            # 创建半透明背景
            overlay = pygame.Surface((surface.get_width(), surface.get_height()))
            overlay.set_alpha(180)
            overlay.fill((0, 0, 0))
            surface.blit(overlay, (0, 0))

            # 渲染标题
            title_text = self.title_font.render("Victory!", True, (255, 215, 0))
            title_rect = title_text.get_rect(
                center=(surface.get_width() // 2, surface.get_height() // 2 - 50)
            )
            surface.blit(title_text, title_rect)

            # 渲染得分
            score_text = self.info_font.render(
                f"Score: {self.score}", True, (255, 255, 255)
            )
            score_rect = score_text.get_rect(
                center=(surface.get_width() // 2, surface.get_height() // 2 + 20)
            )
            surface.blit(score_text, score_rect)

            # 渲染选项
            menu_text = self.info_font.render(
                "Press ENTER for Menu", True, (200, 200, 200)
            )
            menu_rect = menu_text.get_rect(
                center=(surface.get_width() // 2, surface.get_height() // 2 + 70)
            )
            surface.blit(menu_text, menu_rect)

            restart_text = self.info_font.render(
                "Press R to Restart", True, (200, 200, 200)
            )
            restart_rect = restart_text.get_rect(
                center=(surface.get_width() // 2, surface.get_height() // 2 + 120)
            )
            surface.blit(restart_text, restart_rect)

    def on_exit(self) -> None:
        """离开场景时清理资源"""
        self.engine.event_manager.remove_listener("key_down", self.on_key_down)

        # 移除UI面板
        if hasattr(self.engine, "ui_manager"):
            self.engine.ui_manager.remove_panel("victory")
