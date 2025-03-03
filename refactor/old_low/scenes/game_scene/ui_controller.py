import pygame
from typing import Optional
from .base_controller import BaseController


class UIController(BaseController):
    """处理游戏场景的UI元素"""

    def __init__(self, scene):
        super().__init__(scene)
        # UI元素引用
        self.score_label = None
        self.enemies_label = None
        self.fps_label = None

    def initialize(self) -> None:
        """初始化UI控制器"""
        super().initialize()

        if not hasattr(self.engine, "ui_manager"):
            return

        # 设置UI元素
        self._setup_ui()

    def _setup_ui(self) -> None:
        """设置游戏UI元素"""
        ui_manager = self.engine.ui_manager
        screen_width, screen_height = self.engine.screen.get_size()

        # 创建状态面板
        status_panel = ui_manager.create_panel(
            "game_status", 10, 10, 200, 100, color=(0, 0, 0), alpha=150
        )

        # 添加分数显示
        self.score_label = ui_manager.create_text_label(
            "game_status",
            10,
            10,
            f"得分: {self.scene.score}",
            font_name="default_small",
        )

        # 添加敌人数量显示
        if hasattr(self.scene, "enemy_controller"):
            enemies_total = (
                self.scene.enemy_controller.get_enemy_count()
                + self.scene.enemy_controller.get_defeated_enemy_count()
            )
            defeated = self.scene.enemy_controller.get_defeated_enemy_count()
        else:
            enemies_total = 0
            defeated = 0

        self.enemies_label = ui_manager.create_text_label(
            "game_status",
            10,
            40,
            f"敌人: {defeated}/{enemies_total}",
            font_name="default_small",
        )

        # 添加FPS显示
        self.fps_label = ui_manager.create_text_label(
            "game_status",
            10,
            70,
            "FPS: 0",
            font_name="default_small",
            color=(255, 255, 0),
        )

        # 创建暂停按钮
        ui_manager.create_button(
            "game_status",
            screen_width - 110,
            10,
            100,
            30,
            "暂停",
            font_name="default_small",
            normal_color=(80, 80, 80),
            hover_color=(100, 100, 100),
            on_click=self.scene.toggle_pause,
        )

    def update(self, delta_time: float) -> None:
        """更新UI显示

        Args:
            delta_time: 帧间时间(秒)
        """
        # 更新分数显示
        if self.score_label:
            self.score_label.set_text(f"得分: {self.scene.score}")

        # 更新敌人数量显示 - 添加错误处理
        if self.enemies_label and hasattr(self.scene, "enemy_controller"):
            try:
                defeated = self.scene.enemy_controller.get_defeated_enemy_count()
                total = defeated + self.scene.enemy_controller.get_enemy_count()
                self.enemies_label.set_text(f"敌人: {defeated}/{total}")
            except Exception as e:
                if self.engine.debug_mode:
                    print(f"更新敌人UI时出错: {e}")

        # 更新FPS显示
        if self.fps_label:
            fps = int(self.engine.clock.get_fps())
            self.fps_label.set_text(f"FPS: {fps}")

    def render_game_over(self, surface: pygame.Surface) -> None:
        """渲染游戏结束的UI界面

        Args:
            surface: 渲染表面
        """
        # 创建半透明覆盖层
        overlay = pygame.Surface((surface.get_width(), surface.get_height()))
        overlay.set_alpha(180)  # 设置透明度
        overlay.fill((0, 0, 0))  # 黑色背景
        surface.blit(overlay, (0, 0))

        # 渲染胜利文本
        victory_text = self.scene.victory_font.render("胜利!", True, (255, 215, 0))
        victory_rect = victory_text.get_rect(
            center=(surface.get_width() // 2, surface.get_height() // 2 - 50)
        )
        surface.blit(victory_text, victory_rect)

        # 渲染得分文本
        score_text = self.scene.instruction_font.render(
            f"得分: {self.scene.score}", True, (255, 255, 255)
        )
        score_rect = score_text.get_rect(
            center=(surface.get_width() // 2, surface.get_height() // 2 + 20)
        )
        surface.blit(score_text, score_rect)

        # 渲染返回菜单提示
        menu_text = self.scene.instruction_font.render(
            "按 ESC 返回菜单", True, (200, 200, 200)
        )
        menu_rect = menu_text.get_rect(
            center=(surface.get_width() // 2, surface.get_height() // 2 + 70)
        )
        surface.blit(menu_text, menu_rect)

        # 渲染重新开始提示
        restart_text = self.scene.instruction_font.render(
            "按 R 重新开始", True, (200, 200, 200)
        )
        restart_rect = restart_text.get_rect(
            center=(surface.get_width() // 2, surface.get_height() // 2 + 120)
        )
        surface.blit(restart_text, restart_rect)

    def cleanup(self) -> None:
        """清理UI资源"""
        if hasattr(self.engine, "ui_manager"):
            # 清除所有可能的游戏UI面板
            panels_to_remove = ["game_status", "pause_overlay", "victory_overlay"]
            for panel_name in panels_to_remove:
                if panel_name in self.engine.ui_manager.panels:
                    self.engine.ui_manager.remove_panel(panel_name)
