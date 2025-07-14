import pygame
import asyncio
import time
from typing import Any, Optional

from .scenes import SceneManager
from .renders import RenderEngine
from .inputs import InputSystem
from .events import EventBus
from ..ecs.world import World
from .engine_event import QuitEvent


class AsyncGameEngine:
    """异步游戏引擎 - 支持pygbag的Web部署"""

    _instance = None

    def __new__(cls, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self, title: str = "Game", width: int = 800, height: int = 600, fps: int = 60
    ):
        """初始化异步游戏引擎"""
        if hasattr(self, "_initialized"):
            return

        # 基础配置
        self.title = title
        self.width = width
        self.height = height
        self.fps = fps
        self.running = False
        self.delta_time = 0.0
        self.frame_duration = 1.0 / self.fps

        # 初始化 Pygame
        self._init_pygame()
        self._init_world()
        self._init_managers()

        self._initialized = True

    def _init_pygame(self) -> None:
        """初始化 Pygame"""
        pygame.init()
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption(self.title)
        self.clock = pygame.time.Clock()

    def _init_world(self) -> None:
        """初始化世界"""
        self.world = World()

    def _init_managers(self) -> None:
        """初始化管理器"""
        self.event_manager = EventBus()
        self.scene_manager = SceneManager(self)
        self.render_manager = RenderEngine(self.screen)
        self.input_manager = InputSystem()
        self.subscribe_events()

    async def start(self) -> None:
        """启动异步游戏引擎"""
        await self.run()

    async def run(self) -> None:
        """异步游戏主循环"""
        self.running = True
        last_time = time.time()

        try:
            while self.running:
                # 计算 delta time
                current_time = time.time()
                self.delta_time = current_time - last_time
                last_time = current_time

                # 主循环更新
                await self._async_update()

                # 控制帧率 - 重要：为pygbag提供异步等待点
                frame_time = time.time() - current_time
                if frame_time < self.frame_duration:
                    await asyncio.sleep(self.frame_duration - frame_time)

        except KeyboardInterrupt:
            print("游戏被用户中断")
        finally:
            await self.quit()

    def subscribe_events(self) -> None:
        """订阅事件"""
        self.event_manager.subscribe(QuitEvent, self.stop)

    async def _async_update(self) -> None:
        """异步更新游戏逻辑"""
        # 清屏
        self.screen.fill((0, 0, 0))

        # 更新输入系统
        self.input_manager.update()

        # 异步更新场景
        await self._async_scene_update()

        # 更新渲染
        self.render_manager.update()

        # 刷新显示
        pygame.display.flip()

    async def _async_scene_update(self) -> None:
        """异步更新场景"""
        if hasattr(self.scene_manager, "async_update"):
            await self.scene_manager.async_update(self.delta_time)
        else:
            # 兼容同步场景管理器
            self.scene_manager.update(self.delta_time)
            # 提供异步等待点
            await asyncio.sleep(0)

    def stop(self, event: Any) -> None:
        """停止游戏循环"""
        self.running = False

    async def quit(self) -> None:
        """异步退出游戏"""
        # 清理场景管理器
        if self.scene_manager:
            if hasattr(self.scene_manager, "async_shutdown"):
                await self.scene_manager.async_shutdown()
            else:
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

    # pygbag专用方法
    async def pygbag_main(self) -> None:
        """pygbag主函数入口"""

        # 初始化完成后开始游戏循环
        await self.start()


def async_game_engine() -> AsyncGameEngine:
    """获取异步游戏引擎单例"""
    return AsyncGameEngine()


# pygbag兼容性函数
async def main():
    """pygbag入口函数"""
    engine = async_game_engine()
    await engine.pygbag_main()


if __name__ == "__main__":
    # 本地运行
    asyncio.run(main())
