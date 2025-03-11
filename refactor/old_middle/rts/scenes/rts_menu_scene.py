import pygame
from framework.scene.scene import Scene
from framework.ui.ui_text import UIText
from framework.ui.ui_button import UIButton


class RTSMenuScene(Scene):
    """
    RTS游戏菜单场景：提供开始游戏、设置和退出选项
    """

    def __init__(self, game):
        super().__init__(game)
        self.title = None
        self.start_button = None
        self.exit_button = None

    def load(self):
        """场景加载时调用"""
        # 创建UI元素
        font_large = pygame.font.SysFont("arial", 48)
        font_normal = pygame.font.SysFont("arial", 24)

        # 标题
        self.title = self.add_ui_element(
            UIText(
                self.game.width // 2,
                100,
                "COMMANDER",
                font_large,
                (255, 255, 255),
                centered=False,
            )
        )

        # 副标题
        subtitle = self.add_ui_element(
            UIText(
                self.game.width // 2,
                160,
                "RTS Game",
                font_normal,
                (200, 200, 200),
                centered=False,
            )
        )

        # 开始按钮
        self.start_button = self.add_ui_element(
            UIButton(self.game.width // 2 - 100, 250, 200, 50, "Start Game")
        )
        self.start_button.set_font(font_normal)
        self.start_button.callback = self.start_game

        # 退出按钮
        self.exit_button = self.add_ui_element(
            UIButton(self.game.width // 2 - 100, 320, 200, 50, "Exit")
        )
        self.exit_button.set_font(font_normal)
        self.exit_button.callback = self.exit_game

    def start_game(self):
        """开始游戏"""
        self.game.scene_manager.change_scene("rts_game")

    def exit_game(self):
        """退出游戏"""
        self.game.stop()
