import pygame
from typing import Dict
from .base_controller import BaseController


class InputHandler(BaseController):
    """处理游戏场景的输入事件"""

    def __init__(self, scene):
        super().__init__(scene)

    def initialize(self) -> None:
        """初始化输入控制器"""
        super().initialize()

        # 注册事件监听器
        self.engine.event_manager.add_listener("key_down", self.on_key_down)
        self.engine.event_manager.add_listener("key_up", self.on_key_up)

    def on_key_down(self, key: int) -> None:
        """处理按键按下事件

        Args:
            key: 按键代码
        """
        # 检查游戏状态，而不仅仅是game_over标志
        game_over_states = ["victory", "game_over", "defeat"]
        is_game_ended = self.scene.game_over

        if hasattr(self.engine, "game_state_manager"):
            current_state = self.engine.game_state_manager.current_state
            is_game_ended = is_game_ended or current_state in game_over_states

        if is_game_ended:
            self._handle_game_over_keys(key)
            return

        # 如果游戏暂停，只处理特定按键
        if (
            hasattr(self.engine, "game_state_manager")
            and self.engine.game_state_manager.current_state == "paused"
        ):
            if key == pygame.K_ESCAPE:
                self.scene.toggle_pause()  # 取消暂停
            return

        # 首先尝试让玩家控制器处理按键
        if hasattr(self.scene, "player_controller"):
            if self.scene.player_controller.handle_key_down(key):
                return

        # 处理游戏全局按键
        self._handle_global_keys(key)

    def on_key_up(self, key: int) -> None:
        """处理按键释放事件

        Args:
            key: 按键代码
        """
        # 转发给玩家控制器处理
        if hasattr(self.scene, "player_controller"):
            self.scene.player_controller.handle_key_up(key)

    def _handle_game_over_keys(self, key: int) -> None:
        """处理游戏结束时的按键

        Args:
            key: 按键代码
        """
        if key == pygame.K_ESCAPE:
            self.engine.scene_manager.change_scene("menu")
        elif key == pygame.K_r:
            # 重新初始化场景
            self.engine.scene_manager.change_scene("game")

    def _handle_global_keys(self, key: int) -> None:
        """处理游戏全局按键

        Args:
            key: 按键代码
        """
        if key == pygame.K_ESCAPE:
            self.engine.scene_manager.change_scene("menu")

    def cleanup(self) -> None:
        """清理资源"""
        # 移除事件监听器
        self.engine.event_manager.remove_listener("key_down", self.on_key_down)
        self.engine.event_manager.remove_listener("key_up", self.on_key_up)
