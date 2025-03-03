import pygame
from framework.scene.scene import Scene
from framework.ui.ui_text import UIText
from framework.ui.ui_button import UIButton


class GameOverScene(Scene):
    """
    游戏结束场景
    """

    def __init__(self, game):
        super().__init__(game)
        self.title = None
        self.restart_button = None
        self.menu_button = None
        self.result_text = None
        # 初始化默认值，这些值可能被传递的参数覆盖
        self.result = "defeat"  # 默认失败
        self.score = 0

    def load(self):
        """加载场景"""
        # 创建UI元素
        font_large = pygame.font.SysFont("arial", 48)
        font_normal = pygame.font.SysFont("arial", 24)

        # 根据结果选择标题和颜色
        if self.result == "victory":
            title_text = "YOU WIN!"
            title_color = (0, 200, 0)  # 绿色表示胜利
            subtitle_text = f"Great job! Your score: {self.score}"
        else:  # defeat
            title_text = "GAME OVER"
            title_color = (255, 50, 50)  # 红色表示失败
            subtitle_text = f"Try again! Your score: {self.score}"

        # 标题
        self.title = self.add_ui_element(
            UIText(
                self.game.width // 2,
                100,
                title_text,
                font_large,
                title_color,
                centered=True,
            )
        )

        # 结果文本
        self.result_text = self.add_ui_element(
            UIText(
                self.game.width // 2,
                180,
                subtitle_text,
                font_normal,
                (255, 255, 255),
                centered=True,
            )
        )

        # 重新开始按钮
        self.restart_button = self.add_ui_element(
            UIButton(self.game.width // 2 - 100, 250, 200, 50, "Restart Game")
        )
        self.restart_button.set_font(font_normal)
        self.restart_button.callback = self.restart_game

        # 返回主菜单按钮
        self.menu_button = self.add_ui_element(
            UIButton(self.game.width // 2 - 100, 320, 200, 50, "Main Menu")
        )
        self.menu_button.set_font(font_normal)
        self.menu_button.callback = self.return_to_menu

    def restart_game(self):
        """重新开始游戏"""
        self.game.scene_manager.change_scene("game")

    def return_to_menu(self):
        """返回主菜单"""
        self.game.scene_manager.change_scene("main_menu")
