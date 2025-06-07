import pygame
import time
import sys
from typing import Any, Optional

from .scenes import SceneManager
from .renders import RenderEngine
from .inputs import InputSystem
from .events import EventBus
from ..ecs.world import World
from .engine_event import QuitEvent


class GameEngine:
    """游戏引擎 - 负责游戏的主循环和核心管理"""

    _instance = None

    def __new__(cls, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self, title: str = "Game", width: int = 1200, height: int = 800, fps: int = 60
    ):
        """初始化游戏引擎"""
        if hasattr(self, "_initialized"):
            return

        # 基础配置
        self.title = title
        self.width = width
        self.height = height
        self.fps = fps
        self.running = False
        self.delta_time = 0.0

        # 初始化 Pygame
        self._init_pygame()

        # self._init_world()

        # 初始化管理器
        self._init_managers()

        self._initialized = True

    def _init_pygame(self) -> None:
        """初始化 Pygame"""
        pygame.init()
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption(self.title)
        self.clock = pygame.time.Clock()

    # def _init_world(self) -> None:
    #     """初始化世界"""
    #     # 如果需要 ECS 系统，可以在这里初始化
    #     self.world = World()

    def _init_managers(self) -> None:
        """初始化管理器"""
        # 获取单例管理器
        self.event_manager = EventBus()
        self.scene_manager = SceneManager(self)
        self.render_manager = RenderEngine()
        self.render_manager.screen = self.screen  # 设置渲染屏幕
        self.input_manager = InputSystem()

        self.subscribe_events()

    def start(self) -> None:
        """启动游戏引擎"""
        self.run()

    def run(self) -> None:
        """启动游戏主循环"""
        self.running = True
        last_time = time.time()

        try:
            while self.running:
                # 计算 delta time
                current_time = time.time()
                self.delta_time = current_time - last_time
                last_time = current_time

                # 主循环
                self._update()

                # 控制帧率
                self.clock.tick(self.fps)

        except KeyboardInterrupt:
            print("游戏被用户中断")
        finally:
            self.quit()

    def subscribe_events(self) -> None:
        """处理事件"""

        self.event_manager.subscribe(QuitEvent, self.stop)

    def _update(self) -> None:
        """更新游戏逻辑"""
        self.screen.fill((0, 0, 0))
        self.input_manager.update()
        # 更新场景
        self.scene_manager.update(self.delta_time)
        self.render_manager.update()
        # 刷新显示
        pygame.display.flip()

    def stop(self, event: Any) -> None:
        """停止游戏循环"""
        self.running = False

    def quit(self) -> None:
        """退出游戏"""
        # 清理场景管理器
        if self.scene_manager:
            self.scene_manager.shutdown()

        # 清理渲染管理器
        if self.render_manager:
            self.render_manager.clear()

        # 退出 Pygame
        pygame.quit()
        print("游戏已退出")

    @property
    def current_scene(self):
        """获取当前场景"""
        return self.scene_manager.current_scene if self.scene_manager else None

    @property
    def current_scene_name(self) -> Optional[str]:
        """获取当前场景名称"""
        return self.scene_manager.current_scene_name if self.scene_manager else None

    def get_fps(self) -> float:
        """获取当前 FPS"""
        return self.clock.get_fps()

    def get_delta_time(self) -> float:
        """获取 delta time"""
        return self.delta_time


GAMEENGINE = GameEngine()
