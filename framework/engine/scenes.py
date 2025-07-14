from typing import Dict, Optional, Type, Any
from enum import Enum
from abc import ABC, abstractmethod


class SceneState(Enum):
    """场景状态枚举"""

    INACTIVE = 0
    ACTIVE = 1
    PAUSED = 2


class Scene(ABC):
    """场景基类"""

    def __init__(self, engine):
        self.engine = engine
        self.state = SceneState.INACTIVE
        self._name = ""

    @property
    def name(self) -> str:
        """获取场景名称"""
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        """设置场景名称"""
        self._name = value

    def enter(self, **kwargs) -> None:
        """场景进入时调用，子类可重写"""
        self.state = SceneState.ACTIVE

    def exit(self) -> None:
        """场景退出时调用，子类可重写"""
        self.state = SceneState.INACTIVE

    def pause(self) -> None:
        """暂停场景"""
        if self.state == SceneState.ACTIVE:
            self.state = SceneState.PAUSED

    def resume(self) -> None:
        """恢复场景"""
        if self.state == SceneState.PAUSED:
            self.state = SceneState.ACTIVE

    @abstractmethod
    def update(self, delta_time: float) -> None:
        """更新场景逻辑，子类必须实现"""
        pass

    @property
    def is_active(self) -> bool:
        """检查场景是否处于活动状态"""
        return self.state == SceneState.ACTIVE

    @property
    def is_paused(self) -> bool:
        """检查场景是否暂停"""
        return self.state == SceneState.PAUSED


class SceneManager:
    """场景管理器 - 负责场景的生命周期管理"""

    _instance = None

    def __new__(cls, engine: Optional[Any] = None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, engine: Optional[Any] = None):
        if hasattr(self, "_initialized"):
            return

        self.engine = engine
        self._scenes: Dict[str, Type[Scene]] = {}
        self._current_scene: Optional[Scene] = None
        self._scene_stack: list[Scene] = []
        self._initialized = True

    def set_engine(self, engine: Any) -> None:
        """设置引擎实例"""
        self.engine = engine

    def register_scene(self, name: str, scene_class: Type[Scene]) -> None:
        """注册场景类"""
        if not issubclass(scene_class, Scene):
            raise TypeError(f"场景类 {scene_class} 必须继承自 Scene")
        self._scenes[name] = scene_class

    def unregister_scene(self, name: str) -> None:
        """注销场景"""
        if name in self._scenes:
            del self._scenes[name]

    def switch_to(self, scene_name: str, **kwargs) -> bool:
        """切换到指定场景

        Args:
            scene_name: 场景名称
            **kwargs: 传递给场景enter方法的参数

        Returns:
            bool: 切换成功返回True，否则返回False
        """
        if scene_name not in self._scenes:
            print(f"警告: 场景 '{scene_name}' 未注册")
            return False

        # 退出当前场景
        if self._current_scene:
            self._current_scene.exit()

        # 创建并进入新场景
        scene_class = self._scenes[scene_name]
        self._current_scene = scene_class(self.engine)
        self._current_scene.name = scene_name
        self._current_scene.enter(**kwargs)

        return True

    def push_scene(self, scene_name: str, **kwargs) -> bool:
        """推入新场景到栈中（暂停当前场景）

        Args:
            scene_name: 场景名称
            **kwargs: 传递给场景enter方法的参数

        Returns:
            bool: 推入成功返回True，否则返回False
        """
        if scene_name not in self._scenes:
            print(f"警告: 场景 '{scene_name}' 未注册")
            return False

        # 暂停当前场景并推入栈中
        if self._current_scene:
            self._current_scene.pause()
            self._scene_stack.append(self._current_scene)

        # 创建并进入新场景
        scene_class = self._scenes[scene_name]
        self._current_scene = scene_class(self.engine)
        self._current_scene.name = scene_name
        self._current_scene.enter(**kwargs)

        return True

    def pop_scene(self) -> bool:
        """弹出当前场景，恢复栈中的上一个场景

        Returns:
            bool: 弹出成功返回True，否则返回False
        """
        if not self._scene_stack:
            return False

        # 退出当前场景
        if self._current_scene:
            self._current_scene.exit()

        # 恢复栈中的场景
        self._current_scene = self._scene_stack.pop()
        self._current_scene.resume()

        return True

    def update(self, delta_time: float) -> None:
        """更新当前场景"""
        if self._current_scene and self._current_scene.is_active:
            self._current_scene.update(delta_time)

    @property
    def current_scene(self) -> Optional[Scene]:
        """获取当前场景"""
        return self._current_scene

    @property
    def current_scene_name(self) -> Optional[str]:
        """获取当前场景名称"""
        return self._current_scene.name if self._current_scene else None

    def has_scene(self, scene_name: str) -> bool:
        """检查场景是否已注册"""
        return scene_name in self._scenes

    def get_scene_names(self) -> list[str]:
        """获取所有已注册的场景名称"""
        return list(self._scenes.keys())

    def clear_scene_stack(self) -> None:
        """清空场景栈"""
        for scene in self._scene_stack:
            scene.exit()
        self._scene_stack.clear()

    def shutdown(self) -> None:
        """关闭场景管理器，清理所有资源"""
        if self._current_scene:
            self._current_scene.exit()
            self._current_scene = None

        self.clear_scene_stack()
        self._scenes.clear()


SMS = SceneManager()
# Scene Manager System
