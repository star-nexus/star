import sys
from turtle import Screen
import pygame
import time


from framework.ecs.world import World
from framework.engine.scenes import SceneManager
from framework.engine.renders import RenderManager
from framework.engine.events import EventManager, EventType
from framework.engine.inputs import InputManager

from concurrent.futures import ThreadPoolExecutor


class Engine:
    def __init__(
        self, title: str = "Game", width: int = 800, height: int = 600, fps: int = 60
    ):
        """初始化游戏引擎

        Args:
            title: 游戏窗口标题
            width: 游戏窗口宽度
            height: 游戏窗口高度
            fps: 游戏目标帧率
        """
        # 初始化pygame
        pygame.init()
        self.title = title
        self.width = width
        self.height = height
        self.fps = fps
        # 设置屏幕
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption(self.title)

        self.clock = pygame.time.Clock()
        self.running = False
        self.delta_time = 0

        # 创建世界和管理器
        self.world = World()

        # 先创建管理器，然后再设置引用关系
        self.event_manager = EventManager()
        self.input_manager = InputManager(self.event_manager)
        self.render_manager = RenderManager(self.screen)

        # 修改：确保 SceneManager 在最后创建，并传入 engine 引用
        self.scene_manager = SceneManager(self)

        self.executor = ThreadPoolExecutor(max_workers=5)

        self.world.context.executor = self.executor

        # 设置世界上下文
        self.world.context.scene_manager = self.scene_manager
        self.world.context.event_manager = self.event_manager
        # self.world.context.input_manager = self.input_manager
        self.world.context.render_manager = self.render_manager

    def start(self) -> None:
        """启动游戏引擎"""
        self.running = True
        # 订阅结束事件
        self.event_manager.subscribe(EventType.QUIT, self.quit)
        self._main_loop()

    def stop(self) -> None:
        """停止游戏引擎"""
        self.running = False

    def quit(self, event=None) -> None:
        """退出游戏"""
        self._quit()

    def _quit(self) -> None:
        """退出游戏"""

        self._cleanup()
        pygame.quit()
        sys.exit()

    def _main_loop(self) -> None:
        """游戏主循环"""
        last_time = time.time()
        while self.running:
            current_time = time.time()
            self.delta_time = current_time - last_time
            last_time = current_time

            # 处理更新
            self._update()

            self.clock.tick(self.fps)

        # 修改：将清理逻辑移到循环外，避免在每次退出时都调用
        self._cleanup()
        self.quit()

    def _update(self) -> None:
        """更新游戏逻辑"""

        self.screen.fill((0, 0, 0))
        self.input_manager.update()

        # 更新场景
        if self.scene_manager and hasattr(self.scene_manager, "update"):
            self.scene_manager.update(self.delta_time)
            # self.scene_manager.render()

        # 渲染管理器更新
        if self.render_manager and hasattr(self.render_manager, "update"):
            self.render_manager.update(self.screen)

        pygame.display.flip()

    def _cleanup(self) -> None:
        """清理资源"""
        # 修改：添加资源清理逻辑
        if (
            hasattr(self.scene_manager, "current_scene")
            and self.scene_manager.current_scene
        ):
            self.scene_manager.current_scene.exit()

        self.executor.shutdown()
