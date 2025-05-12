import pygame
import time
from typing import Dict, Optional


class Scene:
    """场景基类，所有游戏场景都应继承此类"""

    def __init__(self, engine):
        """初始化场景

        Args:
            engine: 游戏引擎实例
        """
        self.engine = engine
        self.world = engine.world

    def enter(self) -> None:
        """场景进入时调用"""
        pass

    def exit(self) -> None:
        """场景退出时调用"""
        pass

    def update(self, delta_time: float) -> None:
        """更新场景逻辑

        Args:
            delta_time: 帧间隔时间
        """
        pass

    def render(self, render_manager) -> None:
        """渲染场景

        Args:
            render_manager: 渲染管理器实例
        """
        pass


class SceneManager:
    """场景管理器，负责管理游戏场景的生命周期"""

    def __init__(self):
        """初始化场景管理器"""
        self._scenes: Dict[str, Scene] = {}
        self._current_scene: Optional[Scene] = None
        self._current_scene_name: Optional[str] = None

        # 过渡效果相关属性
        self._is_transitioning = False
        self._transition_alpha = 0
        self._transition_surface = None
        self._transition_direction = None  # "in" 表示淡入，"out" 表示淡出
        self._transition_speed = 50  # 过渡速度，降低以使过渡更平滑
        self._next_scene_name = None  # 过渡结束后要切换到的场景名称
        self._scene_switch_delay = (
            0.3  # 场景切换延迟时间（秒），增加延迟确保场景完全退出
        )
        self._delay_start_time = 0  # 延迟开始的时间
        self._is_delaying = False  # 是否正在延迟

    def register_scene(self, name: str, scene: Scene) -> None:
        """注册场景

        Args:
            name: 场景名称
            scene: 场景实例
        """
        self._scenes[name] = scene

    def unregister_scene(self, name: str) -> None:
        """注销场景

        Args:
            name: 场景名称
        """
        if name in self._scenes:
            if self._current_scene_name == name:
                self.switch_scene(None)
            del self._scenes[name]

    def switch_scene(self, name: Optional[str]) -> None:
        """切换场景

        Args:
            name: 要切换到的场景名称，如果为None则退出当前场景
        """
        if name is None:
            # 直接退出当前场景，不使用过渡
            if self._current_scene:
                self._current_scene.exit()
                self._current_scene = None
                self._current_scene_name = None
            return

        if name not in self._scenes:
            return

        # 开始淡出过渡
        self._start_transition(name)

    def get_current_scene(self) -> Optional[Scene]:
        """获取当前场景

        Returns:
            当前场景实例，如果没有活动场景则返回None
        """
        return self._current_scene

    def get_current_scene_name(self) -> Optional[str]:
        """获取当前场景名称

        Returns:
            当前场景名称，如果没有活动场景则返回None
        """
        return self._current_scene_name

    def _start_transition(self, next_scene_name: str) -> None:
        """开始场景过渡

        Args:
            next_scene_name: 过渡结束后要切换到的场景名称
        """
        self._is_transitioning = True
        self._next_scene_name = next_scene_name
        self._transition_direction = "out"  # 先淡出
        self._transition_alpha = 0

        # 创建过渡表面
        if not self._transition_surface:
            from pygame import display

            screen_size = display.get_surface().get_size()
            self._transition_surface = pygame.Surface(screen_size, pygame.SRCALPHA)

    def _update_transition(self) -> None:
        """更新过渡效果"""
        if not self._is_transitioning:
            return

        if self._transition_direction == "out":
            # 淡出当前场景
            self._transition_alpha += self._transition_speed
            if self._transition_alpha >= 255:
                self._transition_alpha = 255
                self._transition_direction = "in"

                # 开始延迟，等待当前场景循环运行完毕
                self._is_delaying = True
                self._delay_start_time = time.time()
                return
        elif self._is_delaying:
            # 检查延迟是否结束
            current_time = time.time()
            if current_time - self._delay_start_time >= self._scene_switch_delay:
                self._is_delaying = False

                # 延迟结束后切换场景
                if self._current_scene:
                    self._current_scene.exit()

                self._current_scene = self._scenes[self._next_scene_name]
                self._current_scene_name = self._next_scene_name
                self._current_scene.enter()
                print(f"切换到场景：{self._next_scene_name}")
            else:
                # 延迟未结束，继续等待
                return
        else:
            # 淡入新场景
            self._transition_alpha -= self._transition_speed
            if self._transition_alpha <= 0:
                self._transition_alpha = 0
                self._is_transitioning = False
                self._next_scene_name = None

        # 更新过渡表面
        self._transition_surface.fill((0, 0, 0, self._transition_alpha))

    def update(self, delta_time: float) -> None:
        """更新当前场景

        Args:
            delta_time: 帧间隔时间
        """
        if self._is_transitioning:
            self._update_transition()

        if self._current_scene and not self._is_delaying:
            self._current_scene.update(delta_time)

    def render(self, render_manager) -> None:
        """渲染当前场景

        Args:
            render_manager: 渲染管理器实例
        """
        if self._current_scene:
            self._current_scene.render(render_manager)

        # 渲染过渡效果
        if self._is_transitioning and self._transition_surface:
            # 设置最高层级确保过渡效果在最上层
            original_layer = render_manager.current_layer
            render_manager.set_layer(9999)
            render_manager.draw(
                self._transition_surface, self._transition_surface.get_rect()
            )
            render_manager.set_layer(original_layer)
