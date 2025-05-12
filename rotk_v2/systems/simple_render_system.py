import pygame
from typing import List, Type
from framework_v2.ecs.system import System
from framework_v2.ecs.component import Component
from rotk_v2.components.transform_component import TransformComponent
from rotk_v2.components.render_component import RenderComponent
from rotk_v2.components.camera_component import CameraComponent, MainCameraTagComponent

class SimpleRenderSystem(System):
    """
    简化版渲染系统，负责渲染所有具有 TransformComponent 和 RenderComponent 的实体
    """
    def __init__(self, required_components: List[Type[Component]] = None, priority: int = 0):
        if required_components is None:
            required_components = [TransformComponent, RenderComponent]
        super().__init__(required_components, priority)
        self._debug_counter = 0

    def initialize(self):
        """初始化渲染系统"""
        print("初始化简化版渲染系统...")

    def update(self, delta_time: float) -> None:
        """更新系统逻辑"""
        # 更新调试计数器
        self._debug_counter += 1
            
        # 获取主相机
        camera = self._get_primary_camera()
        if not camera:
            print("SimpleRenderSystem: 找不到主相机")
            return
            
        if not self.context or not self.context.engine or not self.context.engine.screen:
            print("SimpleRenderSystem: 上下文或屏幕未初始化")
            return
        
        # 清空屏幕
        self.context.engine.screen.fill((0, 0, 0))
        
        # 获取所有可渲染实体
        entities = self.component_manager.get_all_entities_with_components(self.required_components)
        
        # 按层级排序实体
        sorted_entities = sorted(entities, key=lambda e: self.component_manager.get_component(e, RenderComponent).layer)
        
        # 渲染所有实体
        rendered_count = 0
        for entity in sorted_entities:
            transform = self.component_manager.get_component(entity, TransformComponent)
            render = self.component_manager.get_component(entity, RenderComponent)
            
            if not render.visible:
                continue
                
            # 计算相对于相机的位置
            screen_x = (transform.x - camera.x) * camera.zoom + self.context.engine.width // 2
            screen_y = (transform.y - camera.y) * camera.zoom + self.context.engine.height // 2
            
            # 应用缩放
            scaled_width = render.width * camera.zoom
            scaled_height = render.height * camera.zoom
            
            # 创建矩形
            rect = pygame.Rect(
                int(screen_x - scaled_width // 2),
                int(screen_y - scaled_height // 2),
                int(scaled_width),
                int(scaled_height)
            )
            
            # 视口裁剪 - 如果实体在屏幕外，跳过渲染
            if (rect.right < 0 or rect.left > self.context.engine.width or
                rect.bottom < 0 or rect.top > self.context.engine.height):
                continue
            
            # 渲染实体
            pygame.draw.rect(self.context.engine.screen, render.color, rect)
            rendered_count += 1
        
        # 在屏幕中心绘制一个红色标记，用于调试
        pygame.draw.circle(
            self.context.engine.screen, 
            (255, 0, 0), 
            (self.context.engine.width // 2, self.context.engine.height // 2), 
            5
        )
        
        # 每60帧输出一次渲染信息
        if self._debug_counter % 60 == 0:
            print(f"相机位置: ({camera.x}, {camera.y}), 缩放: {camera.zoom}")
            print(f"渲染了 {rendered_count} 个实体")
    
    def _get_primary_camera(self):
        """获取主相机"""
        # 首先尝试使用标签组件查找
        camera_entities = self.context.with_all(CameraComponent, MainCameraTagComponent).result()
        if not camera_entities:
            # 如果没有找到带标签的相机，尝试获取任何相机
            camera_entities = self.context.with_all(CameraComponent).result()
            if not camera_entities:
                return None
        
        # 获取相机组件
        camera_comp = self.context.component_manager.get_component(camera_entities[0], CameraComponent)
        return camera_comp