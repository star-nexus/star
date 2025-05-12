import pygame
from typing import List, Type
from framework_v2.ecs.system import System
from framework_v2.ecs.component import Component
from framework_v2.engine.events import EventType
from rotk_v2.components.transform_component import TransformComponent
from rotk_v2.components.render_component import RenderComponent
from rotk_v2.components.selectable_component import SelectableComponent

class SelectionSystem(System):
    """
    选择系统，负责处理实体的选择
    """
    def __init__(self, required_components: List[Type[Component]] = None, priority: int = 0):
        if required_components is None:
            required_components = [TransformComponent, RenderComponent, SelectableComponent]
        super().__init__(required_components, priority)
        self.selection_rect = None
        self.start_pos = None
        self.surface = None
        
    def update(self, delta_time: float) -> None:
        """
        更新系统逻辑
        
        参数:
            delta_time: 自上一帧以来经过的时间（秒）
        """
        # 选择系统主要通过事件处理，update方法可以为空
        # 或者在这里可以添加一些持续性的选择效果，如选择框闪烁等
        pass
        
    def initialize(self):
        """初始化系统"""
        super().initialize()
        
        # 订阅自定义输入事件
        if self.context and self.context.event_manager:
            self.context.event_manager.subscribe(EventType.CUSTOM, self.handle_custom_event)
            
    def handle_custom_event(self, event):
        """处理自定义事件"""
        event_data = event.data
        event_type = event_data.get("type")
        
        if event_type == pygame.MOUSEBUTTONDOWN and event_data.get("button") == 1:
            # 左键点击开始选择
            self.start_pos = event_data.get("pos")
            self.selection_rect = pygame.Rect(self.start_pos, (0, 0))
            
            # 单击选择
            self.select_at_position(event_data.get("pos"))
            
        elif event_type == pygame.MOUSEMOTION and event_data.get("buttons")[0]:
            # 拖动选择框
            if self.start_pos:
                current_pos = event_data.get("pos")
                self.selection_rect = pygame.Rect(
                    min(self.start_pos[0], current_pos[0]),
                    min(self.start_pos[1], current_pos[1]),
                    abs(current_pos[0] - self.start_pos[0]),
                    abs(current_pos[1] - self.start_pos[1])
                )
                
        elif event_type == pygame.MOUSEBUTTONUP and event_data.get("button") == 1:
            # 左键释放结束选择
            if self.selection_rect and self.selection_rect.width > 5 and self.selection_rect.height > 5:
                # 框选
                self.select_in_rect(self.selection_rect)
            
            self.selection_rect = None
            self.start_pos = None
            
    def select_at_position(self, pos):
        """
        在指定位置选择实体
        
        参数:
            pos: 鼠标位置 (x, y)
        """
        # 清除之前的选择
        self.clear_selection()
        
        # 获取所有具有 TransformComponent、RenderComponent 和 SelectableComponent 的实体
        query = self.context.query_manager.create_query()
        query.with_all(self.required_components)
        entities = query.execute()
        
        # 按照渲染层级倒序排序（先检查上层实体）
        entities.sort(key=lambda entity: self.context.component_manager.get_component(entity, RenderComponent).layer, reverse=True)
        
        for entity in entities:
            transform = self.context.component_manager.get_component(entity, TransformComponent)
            render = self.context.component_manager.get_component(entity, RenderComponent)
            selectable = self.context.component_manager.get_component(entity, SelectableComponent)
            
            if not selectable.selectable or not render.visible:
                continue
                
            # 检查点是否在实体内
            rect = pygame.Rect(
                transform.x - render.width // 2,
                transform.y - render.height // 2,
                render.width,
                render.height
            )
            
            if rect.collidepoint(pos):
                selectable.selected = True
                
                # 发布单位选择事件
                if self.context.event_manager:
                    self.context.event_manager.publish(EventType.UNIT_SELECTED, {"entity": entity})
                
                break  # 只选择一个实体
                
    def select_in_rect(self, rect):
        """
        在指定矩形区域内选择实体
        
        参数:
            rect: 选择矩形
        """
        # 清除之前的选择
        self.clear_selection()
        
        # 获取所有具有 TransformComponent、RenderComponent 和 SelectableComponent 的实体
        query = self.context.query_manager.create_query()
        query.with_all(self.required_components)
        entities = query.execute()
        
        selected_entities = []
        
        for entity in entities:
            transform = self.context.component_manager.get_component(entity, TransformComponent)
            render = self.context.component_manager.get_component(entity, RenderComponent)
            selectable = self.context.component_manager.get_component(entity, SelectableComponent)
            
            if not selectable.selectable or not render.visible:
                continue
                
            # 检查实体是否在选择框内
            entity_rect = pygame.Rect(
                transform.x - render.width // 2,
                transform.y - render.height // 2,
                render.width,
                render.height
            )
            
            if rect.colliderect(entity_rect):
                selectable.selected = True
                selected_entities.append(entity)
                
        # 发布单位选择事件
        if selected_entities and self.context.event_manager:
            for entity in selected_entities:
                self.context.event_manager.publish(EventType.UNIT_SELECTED, {"entity": entity})
                
    def clear_selection(self):
        """清除所有选择"""
        # 获取所有具有 SelectableComponent 的实体
        query = self.context.query_manager.create_query()
        query.with_component(SelectableComponent)
        entities = query.execute()
        
        for entity in entities:
            selectable = self.context.component_manager.get_component(entity, SelectableComponent)
            if selectable.selected:
                selectable.selected = False
                
                # 发布单位取消选择事件
                if self.context.event_manager:
                    self.context.event_manager.publish(EventType.UNIT_DESELECTED, {"entity": entity})
            
    def render(self, surface):
        """
        渲染选择框和选中高亮
        
        参数:
            surface: 渲染表面
        """
        self.surface = surface
        
        # 渲染选择框
        if self.selection_rect:
            pygame.draw.rect(surface, (255, 255, 255), self.selection_rect, 1)
            
        # 渲染选中实体的高亮
        query = self.context.query_manager.create_query()
        query.with_all(self.required_components)
        entities = query.execute()
        
        for entity in entities:
            transform = self.context.component_manager.get_component(entity, TransformComponent)
            render = self.context.component_manager.get_component(entity, RenderComponent)
            selectable = self.context.component_manager.get_component(entity, SelectableComponent)
            
            if selectable.selected and render.visible:
                # 绘制选中高亮
                rect = pygame.Rect(
                    transform.x - render.width // 2 - 2,
                    transform.y - render.height // 2 - 2,
                    render.width + 4,
                    render.height + 4
                )
                pygame.draw.rect(surface, (255, 255, 0), rect, 2)
                
    def set_surface(self, surface):
        """设置渲染表面"""
        self.surface = surface