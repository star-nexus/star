import pygame
from framework.ui.ui_text import UIText
from framework.ui.ui_button import UIButton
from examples.components import HealthComponent, PositionComponent


class GameSceneUI:
    """
    管理游戏内的UI元素
    """

    def __init__(self, game, scene):
        self.game = game
        self.scene = scene
        self.timer_text = None
        self.score_text = None
        self.health_text = None
        self.position_text = None
        self.pause_button = None

    def create_game_ui(self, player, initial_timer=30.0, initial_score=0):
        """创建游戏UI元素"""
        font = pygame.font.SysFont("arial", 24)

        # 左侧对齐的UI元素
        # 时间显示
        self.timer_text = self.scene.add_ui_element(
            UIText(
                10,
                10,
                f"Time: {int(initial_timer)}s",
                font,
                (255, 255, 255),
                centered=False,
            )
        )

        # 分数显示
        self.score_text = self.scene.add_ui_element(
            UIText(
                10,
                40,
                f"Score: {initial_score}",
                font,
                (255, 255, 255),
                centered=False,
            )
        )

        # 健康显示
        player_health = player.get_component(HealthComponent)
        self.health_text = self.scene.add_ui_element(
            UIText(
                10,
                70,
                f"Health: {int(player_health.current_health)}/{player_health.max_health}",
                font,
                (255, 255, 255),
                centered=False,
            )
        )

        # 位置显示
        position = player.get_component(PositionComponent)
        self.position_text = self.scene.add_ui_element(
            UIText(
                10,
                100,
                f"Position: ({int(position.x)}, {int(position.y)})",
                font,
                (200, 200, 200),
                centered=False,
            )
        )

        # 暂停按钮 - 右上角
        self.pause_button = self.scene.add_ui_element(
            UIButton(self.game.width - 90, 10, 80, 30, "Pause")
        )
        self.pause_button.set_font(font)

        return self.pause_button

    def update_ui(self, timer, score, player):
        """更新UI显示"""
        if self.timer_text:
            self.timer_text.set_text(f"Time: {max(0, int(timer))}s")

        if self.score_text:
            self.score_text.set_text(f"Score: {score}")

        if self.health_text and player:
            player_health = player.get_component(HealthComponent)
            if player_health:
                self.health_text.set_text(
                    f"Health: {int(player_health.current_health)}/{player_health.max_health}"
                )

        if self.position_text and player:
            position = player.get_component(PositionComponent)
            if position:
                self.position_text.set_text(
                    f"Position: ({int(position.x)}, {int(position.y)})"
                )
