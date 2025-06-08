"""
游戏结束统计场景
Game Over Statistics Scene
"""

import pygame
from typing import Dict, Any, Optional
from framework_v2 import (
    World,
    SMS,
    RMS,
    EBS,
    MouseButtonDownEvent,
    MouseMotionEvent,
    Event,
)
from framework_v2.engine.engine_event import QuitEvent
from framework_v2.engine.scenes import Scene
from ..components.game_over import Winner, GameStatistics, GameOverButtons
from ..systems.game_over_render_system import GameOverRenderSystem
from ..prefabs.config import Faction, GameConfig


class GameOverScene(Scene):
    """游戏结束统计场景"""

    def __init__(self, engine):
        super().__init__(engine)

    def enter(self, **kwargs) -> None:
        """进入场景时调用，接收传递的参数"""
        super().enter(**kwargs)
        self.world = World()

        # 从参数中获取数据并创建组件
        winner = kwargs.get("winner", None)
        statistics = kwargs.get("statistics", {})

        # 添加获胜者组件
        winner_component = Winner(faction=winner)
        self.world.add_singleton_component(winner_component)

        # 添加统计数据组件
        stats_component = GameStatistics(data=statistics)
        self.world.add_singleton_component(stats_component)

        # 创建按钮
        self._create_buttons()

        game_over_system = GameOverRenderSystem()
        # 初始化渲染系统
        self.world.add_system(game_over_system)

        self.subscribe_events()

    def _create_buttons(self) -> None:
        """创建按钮"""
        # 获取屏幕尺寸
        screen_width = GameConfig.WINDOW_WIDTH
        screen_height = GameConfig.WINDOW_HEIGHT

        button_width = 150
        button_height = 40
        button_spacing = 20
        total_width = 2 * button_width + button_spacing
        start_x = (screen_width - total_width) // 2
        button_y = screen_height - 150

        buttons = {
            "restart": {
                "rect": pygame.Rect(start_x, button_y, button_width, button_height),
                "text": "重新开始",
                "hover": False,
                "default_color": (60, 60, 80),
                "hover_color": (80, 80, 100),
                "action": self._restart_game,
            },
            "quit": {
                "rect": pygame.Rect(
                    start_x + button_width + button_spacing,
                    button_y,
                    button_width,
                    button_height,
                ),
                "text": "退出游戏",
                "hover": False,
                "default_color": (60, 60, 80),
                "hover_color": (80, 80, 100),
                "action": self._quit_game,
            },
        }

        # 添加按钮组件
        button_component = GameOverButtons(buttons=buttons)
        self.world.add_singleton_component(button_component)

    def subscribe_events(self) -> None:
        """订阅事件"""
        # 订阅鼠标点击和移动事件
        EBS.subscribe(MouseButtonDownEvent, self.handle_event)
        EBS.subscribe(MouseMotionEvent, self.handle_event)

    def update(self, dt: float) -> None:
        """更新场景"""
        if self.world:
            self.world.update(dt)

    def handle_event(self, event: Event) -> None:
        """处理事件"""
        if isinstance(event, MouseButtonDownEvent):
            if event.button == 1:  # 左键点击
                self._handle_mouse_click(event.pos)
        elif isinstance(event, MouseMotionEvent):
            self._handle_mouse_motion(event.pos)

    def _handle_mouse_click(self, pos: tuple) -> None:
        """处理鼠标点击"""
        button_component = self.world.get_singleton_component(GameOverButtons)
        if not button_component:
            return

        for button_name, button in button_component.buttons.items():
            if button["rect"].collidepoint(pos):
                button["action"]()

    def _handle_mouse_motion(self, pos: tuple) -> None:
        """处理鼠标移动（悬停效果）"""
        button_component = self.world.get_singleton_component(GameOverButtons)
        if not button_component:
            return

        hover_button = None
        for button_name, button in button_component.buttons.items():
            if button["rect"].collidepoint(pos):
                button["hover"] = True
            else:
                button["hover"] = False

    def exit(self):
        return super().exit()

    def _restart_game(self) -> None:
        """重新开始游戏"""
        SMS.switch_to("game")

    def _quit_game(self) -> None:
        """退出游戏"""
        EBS.publish(QuitEvent(sender=__name__, timestamp=pygame.time.get_ticks()))

    def cleanup(self) -> None:
        """清理场景"""
        if self.world:
            self.world.cleanup()
