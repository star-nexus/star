import sys
import pygame
import time
from framework.core.ecs.world import World
from framework.managers.events import EventManager
from framework.managers.inputs import InputManager
from framework.managers.renders import RenderManager
from framework.managers.scenes import SceneManager
from framework.managers.resources import ResourceManager
from framework.managers.audio import AudioManager
from framework.ui import UIManager


class Engine:
    """游戏引擎类，负责主循环和管理各个子系统"""

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
        pygame.init()
        self.title = title
        self.width = width
        self.height = height
        self.fps = fps
        self.screen = pygame.display.set_mode((width, height))
        pygame.display.set_caption(title)

        self.clock = pygame.time.Clock()
        self.running = False
        self.delta_time = 0.0

        # 创建ECS世界 - 用于游戏逻辑
        self.world = World()

        # 创建各个管理器
        self.event_manager = EventManager()
        self.input_manager = InputManager(self.event_manager)
        self.scene_manager = SceneManager()
        self.resource_manager = ResourceManager()
        self.render_manager = RenderManager()
        self.audio_manager = AudioManager()

        # UI管理器现在使用自己的World
        self.ui_manager = UIManager(self.event_manager)

    def start(self) -> None:
        """启动游戏引擎"""
        self.running = True
        self._main_loop()

    def stop(self) -> None:
        """停止游戏引擎"""
        self.running = False

    def quit(self) -> None:
        """退出游戏"""
        pygame.quit()
        sys.exit()

    def _main_loop(self) -> None:
        """游戏主循环"""
        last_time = time.time()

        while self.running:
            # 计算帧间隔时间
            current_time = time.time()
            self.delta_time = current_time - last_time
            last_time = current_time

            # 处理事件
            self._process_events()

            # 更新游戏逻辑
            self._update()

            # 渲染游戏画面
            self._render()

            # 控制帧率
            self.clock.tick(self.fps)

        # 游戏结束，清理资源
        self._cleanup()

    def _process_events(self) -> None:
        """处理游戏事件"""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.stop()

            # 将事件传递给输入管理器处理
            self.input_manager.process_event(event)

    def _update(self) -> None:
        """更新游戏逻辑"""
        # 检查场景管理器是否正在进行场景切换
        is_scene_transitioning = (
            self.scene_manager._is_transitioning and self.scene_manager._is_delaying
        )

        # 只有在不切换场景时才更新游戏世界
        if not is_scene_transitioning:
            self.world.update(self.delta_time)

        # 总是更新UI世界
        self.ui_manager.update(self.delta_time)

        # 更新当前场景
        self.scene_manager.update(self.delta_time)

    def _render(self) -> None:
        """渲染游戏画面"""
        # 清空屏幕
        self.screen.fill((0, 0, 0))

        # 渲染当前场景
        self.scene_manager.render(self.render_manager)

        # 调用所有游戏渲染系统
        self.world.render(self.render_manager)

        # 调用UI渲染系统
        self.ui_manager.world.render(self.render_manager)

        # 将渲染管理器的内容绘制到屏幕
        self.render_manager.render(self.screen)

        # 更新屏幕显示
        pygame.display.flip()

    def _cleanup(self) -> None:
        """清理游戏资源"""
        self.resource_manager.clear()
        self.audio_manager.clear()
        pygame.quit()

    def register_scene(self, name: str, scene) -> None:
        """注册场景

        Args:
            name: 场景名称
            scene: 场景对象
        """
        self.scene_manager.register_scene(name, scene)

    def switch_scene(self, name: str) -> None:
        """切换场景

        Args:
            name: 要切换到的场景名称
        """
        self.scene_manager.switch_scene(name)
