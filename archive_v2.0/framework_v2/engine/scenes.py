from typing import Dict, Optional


class Scene:
    def __init__(self, engine):
        self.is_active = False
        self.engine = engine
        # 修改这里，使用 getattr 安全地获取 world 属性
        self.world = engine.world

    def enter(self, **kwargs) -> None:
        """场景开始时调用"""
        self.is_active = True

    def exit(self) -> None:
        """场景结束时调用"""
        self.is_active = False

    def update(self, delta_time: float) -> None:
        """场景更新时调用"""
        pass


class SceneManager:
    def __init__(self,engine):
        self.scenes: Dict[str, Scene] = {}
        self.current_scene: Optional[Scene] = None
        self.engine = engine

    def add_scene(self, name, scene_class) -> None:
        """添加场景类（而不是实例）"""
        self.scenes[name] = scene_class

    def remove_scene(self, scene_name: str) -> None:
        """移除场景"""
        if scene_name in self.scenes:
            del self.scenes[scene_name]

    def load_scene(self, scene_name: str, kwargs = None) -> None:
        """加载场景"""
        if scene_name in self.scenes:
            if self.current_scene:
                self.current_scene.exit()
            
            # 修改这里：创建场景实例，而不是直接使用存储的值
            scene_class = self.scenes[scene_name]
            self.current_scene = scene_class(self.engine)
            
            # 调用 enter 方法
            if kwargs is None:
                self.current_scene.enter()
            else:
                self.current_scene.enter(**kwargs)

    def update(self, delta_time: float) -> None:
        """更新场景"""
        if self.current_scene:
            self.current_scene.update(delta_time)

    def render(self) -> None:
        """渲染场景"""
        if self.current_scene:
            self.current_scene.render(self.engine.screen)
