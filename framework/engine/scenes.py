from typing import Dict, Optional, Callable
from enum import Enum


class SceneState(Enum):
    INACTIVE = 0  # 场景未激活
    ACTIVE = 1  # 场景正常运行中
    EXITING = 2  # 场景正在退出


class Scene:
    def __init__(self, engine):
        self.state = SceneState.INACTIVE
        self.engine = engine
        self.world = engine.world
        self._exit_callback = None

    def enter(self, **kwargs) -> None:
        """场景开始时调用"""
        self.state = SceneState.ACTIVE

    def prepare_exit(self, callback: Callable = None) -> None:
        """准备退出场景，设置退出回调"""
        self.state = SceneState.EXITING
        self._exit_callback = callback

    def exit(self) -> None:
        """场景结束时调用"""
        self.state = SceneState.INACTIVE
        # 调用退出完成回调
        if self._exit_callback:
            self._exit_callback()
            self._exit_callback = None

    def update(self, delta_time: float) -> None:
        """场景更新时调用"""
        pass

    def is_exiting_complete(self) -> bool:
        """检查场景是否已完成退出准备，子类可重写此方法实现自定义退出逻辑"""
        return True  # 默认实现立即完成退出


class SceneManager:
    def __init__(self, engine):
        self.scenes: Dict[str, Scene] = {}
        self.current_scene: Optional[Scene] = None
        self.engine = engine
        self.next_scene_info = None  # 存储下一个要加载的场景信息

    def add_scene(self, name, scene_class) -> None:
        """添加场景类（而不是实例）"""
        self.scenes[name] = scene_class

    def remove_scene(self, scene_name: str) -> None:
        """移除场景"""
        if scene_name in self.scenes:
            del self.scenes[scene_name]

    def load_scene(self, scene_name: str, **kwargs) -> None:
        """加载场景"""
        if scene_name not in self.scenes:
            return

        # 存储下一个场景的信息
        self.next_scene_info = (scene_name, kwargs)

        # 如果当前没有场景，直接加载新场景
        if not self.current_scene:
            self._load_next_scene()
            return

        # 如果当前场景存在，先准备退出当前场景
        self.current_scene.prepare_exit(self._load_next_scene)

    def _load_next_scene(self) -> None:
        """实际加载下一个场景的内部方法"""
        if not self.next_scene_info:
            return

        scene_name, kwargs = self.next_scene_info
        self.next_scene_info = None

        # 创建场景实例
        scene_class = self.scenes[scene_name]
        self.current_scene = scene_class(self.engine)

        # 调用 enter 方法
        if kwargs is None:
            self.current_scene.enter()
        else:
            self.current_scene.enter(**kwargs)

    def update(self, delta_time: float) -> None:
        """更新场景"""
        if not self.current_scene:
            return

        # 根据场景状态进行不同处理
        if self.current_scene.state == SceneState.ACTIVE:
            # 正常更新场景
            self.current_scene.update(delta_time)
        elif self.current_scene.state == SceneState.EXITING:
            # 检查场景是否完成退出准备
            if self.current_scene.is_exiting_complete():
                self.current_scene.exit()
            else:
                # 场景退出过程中的更新
                self.current_scene.update(delta_time)
