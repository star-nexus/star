from typing import Dict, Optional, Type, Any
import pygame
import warnings

# 导入新的场景基类
from engine.scene_base import BaseScene


class SceneManager:
    """管理游戏场景的加载、切换和更新"""

    def __init__(self, engine):
        self.engine = engine
        self.scenes: Dict[str, BaseScene] = {}
        self.current_scene: Optional[BaseScene] = None

    def add_scene(self, name: str, scene: BaseScene) -> None:
        """添加场景到管理器"""
        self.scenes[name] = scene

    def change_scene(self, name: str) -> None:
        """切换到指定场景"""
        if name in self.scenes:
            # 如果当前场景存在，先调用退出方法
            if self.current_scene:
                self.current_scene.on_exit()

            # 判断是否切换到同一个场景（例如重新开始游戏）
            if self.current_scene and name == self._get_scene_name(self.current_scene):
                # 对于同一场景，重新创建一个场景实例而不是重用
                scene_type = type(self.current_scene)
                self.scenes[name] = scene_type(self.engine)

            # 设置当前场景
            self.current_scene = self.scenes[name]

            # 调用进入方法，这会处理初始化和UI设置
            self.current_scene.on_enter()
        else:
            print(f"场景 '{name}' 不存在")

    def _get_scene_name(self, scene: BaseScene) -> Optional[str]:
        """获取场景的名称"""
        for name, s in self.scenes.items():
            if s == scene:
                return name
        return None

    def update(self, delta_time: float) -> None:
        """更新当前场景"""
        if self.current_scene:
            self.current_scene.update(delta_time)

    def render(self, surface: pygame.Surface) -> None:
        """渲染当前场景"""
        if self.current_scene:
            self.current_scene.render(surface)
