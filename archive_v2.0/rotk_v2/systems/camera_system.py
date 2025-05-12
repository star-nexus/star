from math import log
from framework_v2.ecs.system import System
from framework_v2.engine.events import EventType
from rotk_v2.components.camera_component import CameraComponent
import pygame
import logging

class CameraSystem(System):
    """
    相机系统 - 纯逻辑处理
    处理相机移动、缩放等逻辑
    """
    def __init__(self,context):
        super().__init__(required_components=[CameraComponent], priority=90)
        self.min_zoom = 0.5    # 最小缩放值
        self.max_zoom = 2.0    # 最大缩放值
        self.target_x = None   # 目标X坐标
        self.target_y = None   # 目标Y坐标
        self.target_zoom = None # 目标缩放值
        self.smooth_factor = 5.0 # 平滑因子（越大越平滑）
        self.keys_pressed = {
            pygame.K_UP: False,
            pygame.K_DOWN: False,
            pygame.K_LEFT: False,
            pygame.K_RIGHT: False,
            pygame.K_EQUALS: False,
            pygame.K_MINUS: False,
        }
        self.context = context
        # 添加日志记录器
        self.system_subscribe()
        self.logger = logging.getLogger("CameraSystem")


    def system_subscribe(self):
        """初始化相机系统"""
        # 注册事件处理函数
        # 修正: self.context.subscribe 改为 self.context.event_manager.subscribe
        self.context.event_manager.subscribe(EventType.KEY_DOWN, self.handle_key_down)
        self.context.event_manager.subscribe(EventType.KEY_UP, self.handle_key_up)
        # self.context.event_manager.subscribe(EventType.CAMERA_MOVE, self.handle_camera_move)
        # self.context.event_manager.subscribe(EventType.CAMERA_ZOOM, self.handle_camera_zoom)
        

    def update(self, delta_time: float):
        """更新相机状态"""

            
        # 获取相机组件
        camera = self._get_primary_camera()
        
        # 添加调试输出
        if any(self.keys_pressed.values()):
            self.logger.info(f"按键状态: {self.keys_pressed}")
            self.logger.info(f"相机位置: ({camera.x}, {camera.y}), 缩放: {camera.zoom}")
        
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
            self.target_x = camera.x + dx
            self.target_y = camera.y + dy
            
        # 应用缩放
        if zoom_change != 0:
            new_zoom = camera.zoom + zoom_change
            self.target_zoom = max(self.min_zoom, min(self.max_zoom, new_zoom))
        
        # 平滑移动到目标位置
        if self.target_x is not None and self.target_y is not None:
            # 计算当前位置到目标位置的插值
            camera.x += (self.target_x - camera.x) * min(1.0, delta_time * self.smooth_factor)
            camera.y += (self.target_y - camera.y) * min(1.0, delta_time * self.smooth_factor)
            
            # 如果足够接近目标，则认为已到达
            if abs(camera.x - self.target_x) < 0.5 and abs(camera.y - self.target_y) < 0.5:
                camera.x = self.target_x
                camera.y = self.target_y
                self.target_x = None
                self.target_y = None
        
        # 平滑缩放到目标值
        if self.target_zoom is not None:
            # 计算当前缩放到目标缩放的插值
            camera.zoom += (self.target_zoom - camera.zoom) * min(1.0, delta_time * self.smooth_factor)
            
            # 如果足够接近目标，则认为已到达
            if abs(camera.zoom - self.target_zoom) < 0.01:
                camera.zoom = self.target_zoom
                self.target_zoom = None
    
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
    
    def handle_camera_move(self, event):
        """处理相机移动事件"""
        if not event.data:
            return
            
        # 从事件数据获取目标位置
        target_x = event.data.get("x")
        target_y = event.data.get("y")
        
        if target_x is not None and target_y is not None:
            self.target_x = target_x
            self.target_y = target_y
    
    def handle_camera_zoom(self, event):
        """处理相机缩放事件"""
        if not event.data:
            return
            
        # 从事件数据获取目标缩放值或缩放变化量
        zoom = event.data.get("zoom")
        zoom_delta = event.data.get("zoom_delta", 0)
        
        camera = self._get_primary_camera()
        if not camera:
            return
            
        # 应用绝对缩放值
        if zoom is not None:
            self.target_zoom = max(self.min_zoom, min(self.max_zoom, zoom))
        # 应用相对缩放变化
        elif zoom_delta != 0:
            new_zoom = camera.zoom + zoom_delta
            self.target_zoom = max(self.min_zoom, min(self.max_zoom, new_zoom))

    def _get_primary_camera(self):
        """获取主相机组件"""
        # 使用与update方法相同的查询方式
        camera_entities = self.context.query_manager.with_all(CameraComponent).result()
        
        if not camera_entities:
            return None
            
        # 简化处理，直接返回第一个相机组件
        return self.context.component_manager.get_component(camera_entities[0], CameraComponent)