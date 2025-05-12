import pygame
from framework_v2.ecs.system import System
from framework_v2.engine.events import EventType
from rotk_v2.components.camera_component import CameraComponent, MainCameraTagComponent
import logging

class SimpleCameraSystem(System):
    """
    简化版相机系统 - 处理相机移动和缩放
    """
    def __init__(self, required_components=None, priority=0):
        if required_components is None:
            required_components = [CameraComponent]
        super().__init__(required_components, priority)
        self.min_zoom = 0.5    # 最小缩放值
        self.max_zoom = 2.0    # 最大缩放值
        self.keys_pressed = {
            pygame.K_UP: False,
            pygame.K_DOWN: False,
            pygame.K_LEFT: False,
            pygame.K_RIGHT: False,
            pygame.K_EQUALS: False,  # 放大
            pygame.K_MINUS: False,   # 缩小
        }
        self.logger = logging.getLogger("SimpleCameraSystem")
        
    def initialize(self):
        """初始化相机系统"""
        print("初始化简化版相机系统...")
        
        # 创建主相机实体
        camera_entity = self.entity_manager.create_entity()
        
        # 添加相机组件
        camera_component = CameraComponent(
            x=0,
            y=0,
            zoom=1.0,
            move_speed=300.0,
            zoom_speed=0.5
        )
        self.component_manager.add_component(camera_entity, camera_component)
        
        # 添加主相机标签组件
        self.component_manager.add_component(camera_entity, MainCameraTagComponent())
        
        # 注册事件处理函数
        self.context.event_manager.subscribe(EventType.KEY_DOWN, self.handle_key_down)
        self.context.event_manager.subscribe(EventType.KEY_UP, self.handle_key_up)
        
        print(f"相机创建完成: 位置({camera_component.x}, {camera_component.y}), 缩放: {camera_component.zoom}")

    def update(self, delta_time):
        """更新相机状态"""
        # 获取相机组件
        camera_entities = self.context.with_all(CameraComponent, MainCameraTagComponent).result()
        if not camera_entities:
            return
            
        camera = self.component_manager.get_component(camera_entities[0], CameraComponent)
        
        # 处理移动
        dx, dy = 0, 0
        zoom_change = 0
        
        # 计算移动方向
        if self.keys_pressed[pygame.K_UP]:
            dy -= camera.move_speed * delta_time
        if self.keys_pressed[pygame.K_DOWN]:
            dy += camera.move_speed * delta_time
        if self.keys_pressed[pygame.K_LEFT]:
            dx -= camera.move_speed * delta_time
        if self.keys_pressed[pygame.K_RIGHT]:
            dx += camera.move_speed * delta_time
            
        # 计算缩放变化
        if self.keys_pressed[pygame.K_EQUALS]:
            zoom_change = camera.zoom_speed * delta_time
        if self.keys_pressed[pygame.K_MINUS]:
            zoom_change = -camera.zoom_speed * delta_time
            
        # 应用移动
        if dx != 0 or dy != 0:
            camera.x += dx
            camera.y += dy
            
        # 应用缩放
        if zoom_change != 0:
            camera.zoom = max(self.min_zoom, min(self.max_zoom, camera.zoom + zoom_change))
            
        # 每60帧输出一次相机信息
        if hasattr(self, '_debug_counter'):
            self._debug_counter += 1
        else:
            self._debug_counter = 0
            
        if self._debug_counter % 60 == 0:
            print(f"相机位置: ({camera.x}, {camera.y}), 缩放: {camera.zoom}")
    
    def handle_key_down(self, event):
        """处理按键按下事件"""
        key = event.data.get("key")
        if key in self.keys_pressed:
            self.keys_pressed[key] = True
            
        # 额外处理 = 键（与 + 相同）和 _ 键（与 - 相同）
        if key == pygame.K_PLUS or key == pygame.K_EQUALS:
            self.keys_pressed[pygame.K_EQUALS] = True
        elif key == pygame.K_UNDERSCORE or key == pygame.K_MINUS:
            self.keys_pressed[pygame.K_MINUS] = True
    
    def handle_key_up(self, event):
        """处理按键释放事件"""
        key = event.data.get("key")
        if key in self.keys_pressed:
            self.keys_pressed[key] = False
            
        # 额外处理 = 键（与 + 相同）和 _ 键（与 - 相同）
        if key == pygame.K_PLUS or key == pygame.K_EQUALS:
            self.keys_pressed[pygame.K_EQUALS] = False
        elif key == pygame.K_UNDERSCORE or key == pygame.K_MINUS:
            self.keys_pressed[pygame.K_MINUS] = False