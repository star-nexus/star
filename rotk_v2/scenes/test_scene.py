import pygame
from framework_v2.engine.scenes import Scene
from framework_v2.engine.events import EventType

from rotk_v2.systems.simple_render_system import SimpleRenderSystem
from rotk_v2.systems.simple_map_system import SimpleMapSystem
from rotk_v2.systems.simple_camera_system import SimpleCameraSystem

from rotk_v2.components.transform_component import TransformComponent
from rotk_v2.components.render_component import RenderComponent
from rotk_v2.components.camera_component import CameraComponent, MainCameraTagComponent

class SimpleGameScene(Scene):
    """
    简化版游戏场景，只包含地图、相机和渲染系统
    """
    def __init__(self, engine):
        super().__init__(engine)
        self.ui_elements = []
        self.game_time = 0
        self.paused = False
        
    def enter(self, **kwargs):
        """场景开始时调用"""
        super().enter(**kwargs)
        print("进入简化版游戏场景...")
        
        # 初始化游戏状态
        self.game_time = 0
        self.paused = False

        # 注册系统（注意顺序很重要）
        self.register_systems()
        
        # 订阅事件
        self.subscribe_events()
        
    def exit(self):
        """场景结束时调用"""
        super().exit()
        
        # 取消订阅事件
        self.unsubscribe_events()
        
        # 清除 UI 元素
        self.ui_elements.clear()
        
    def register_systems(self):
        """注册系统"""
        print("注册简化版系统...")
        
        # 1. 首先创建相机系统并初始化
        camera_system = SimpleCameraSystem(priority=100)
        self.world.add_system(camera_system)
        
        # 2. 然后创建地图系统并初始化
        map_system = SimpleMapSystem(priority=90)
        self.world.add_system(map_system)
        
        # 3. 最后创建渲染系统
        render_system = SimpleRenderSystem([TransformComponent, RenderComponent], priority=80)
        self.world.add_system(render_system)
        
        print("系统注册完成")
        
    def subscribe_events(self):
        """订阅事件"""
        # 订阅退出事件
        self.engine.event_manager.subscribe(EventType.QUIT, self.handle_quit)
        # 订阅键盘事件
        self.engine.event_manager.subscribe(EventType.KEY_DOWN, self.handle_key_down)
        
    def unsubscribe_events(self):
        """取消订阅事件"""
        # 取消订阅退出事件
        self.engine.event_manager.unsubscribe(EventType.QUIT, self.handle_quit)
        # 取消订阅键盘事件
        self.engine.event_manager.unsubscribe(EventType.KEY_DOWN, self.handle_key_down)
        
    def handle_quit(self, event):
        """处理退出事件"""
        self.engine.stop()
        
    def handle_key_down(self, event):
        """处理键盘按下事件"""
        key = event.data.get("key")
        
        # ESC 键退出游戏
        if key == pygame.K_ESCAPE:
            self.engine.stop()
            
        # 空格键暂停/继续游戏
        elif key == pygame.K_SPACE:
            self.paused = not self.paused
            print(f"游戏{'暂停' if self.paused else '继续'}")
            
    def update(self, delta_time):
        """更新场景"""
        if self.paused:
            return
            
        # 更新游戏时间
        self.game_time += delta_time
        
        # 场景逻辑更新
        super().update(delta_time)
        
    def render(self, screen):
        """渲染场景"""
        # 场景渲染由渲染系统完成，这里不需要额外操作
        # 但必须实现此方法，因为基类Scene要求子类实现
        pass