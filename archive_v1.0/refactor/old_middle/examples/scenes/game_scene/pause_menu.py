import pygame
from framework.ui.ui_text import UIText
from framework.ui.ui_button import UIButton


class PauseMenuManager:
    """
    管理游戏暂停菜单
    """

    def __init__(self, game, scene):
        self.game = game
        self.scene = scene
        self.is_paused = False
        self.pause_overlay = None
        self.pause_title = None
        self.continue_button = None
        self.main_menu_button = None
        self.cancel_button = None

    def create_pause_menu(self):
        """创建暂停菜单UI元素"""
        font_large = pygame.font.SysFont("arial", 48)
        font_normal = pygame.font.SysFont("arial", 24)

        # 创建半透明背景覆盖层
        self.pause_overlay = pygame.Surface(
            (self.game.width, self.game.height), pygame.SRCALPHA
        )
        self.pause_overlay.fill((0, 0, 0, 128))  # 黑色半透明

        # 暂停标题
        self.pause_title = self.scene.add_ui_element(
            UIText(
                self.game.width // 2,
                150,
                "PAUSE",
                font_large,
                (255, 255, 255),
                centered=True,
            )
        )
        self.pause_title.visible = False

        # 继续游戏按钮
        self.continue_button = self.scene.add_ui_element(
            UIButton(self.game.width // 2 - 100, 250, 200, 50, "Continue")
        )
        self.continue_button.set_font(font_normal)
        self.continue_button.visible = False

        # 主菜单按钮
        self.main_menu_button = self.scene.add_ui_element(
            UIButton(self.game.width // 2 - 100, 320, 200, 50, "Main Menu")
        )
        self.main_menu_button.set_font(font_normal)
        self.main_menu_button.visible = False

        # 取消按钮
        self.cancel_button = self.scene.add_ui_element(
            UIButton(self.game.width // 2 - 100, 390, 200, 50, "Cancel")
        )
        self.cancel_button.set_font(font_normal)
        self.cancel_button.visible = False

    def toggle_pause(self, is_pause):
        """切换暂停状态"""
        self.is_paused = is_pause

        # 更新UI可见性
        self.pause_title.visible = is_pause
        self.continue_button.visible = is_pause
        self.main_menu_button.visible = is_pause
        self.cancel_button.visible = is_pause

    def render_overlay(self, screen):
        """渲染暂停菜单覆盖层"""
        if self.is_paused and self.pause_overlay:
            screen.blit(self.pause_overlay, (0, 0))
