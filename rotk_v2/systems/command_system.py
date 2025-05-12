import pygame
from typing import List, Type
from framework_v2.ecs.system import System
from framework_v2.ecs.component import Component
from framework_v2.engine.events import EventType
from rotk_v2.components.transform_component import TransformComponent
from rotk_v2.components.render_component import RenderComponent
from rotk_v2.components.selectable_component import SelectableComponent
from rotk_v2.components.movable_component import MovableComponent

class CommandSystem(System):
    """
    命令系统，负责处理玩家对选中实体的命令
    """
    def __init__(self, required_components: List[Type[Component]] = None, priority: int = 0):
        if required_components is None:
            required_components = []  # 命令系统不需要特定组件，它会查询不同类型的实体
        super().__init__(required_components, priority)
        
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
        
        if event_type == pygame.MOUSEBUTTONDOWN and event_data.get("button") == 3:
            # 右键点击发出命令
            self.issue_command(event_data.get("pos"))
            
    def handle_event(self, event):
        """
        处理输入事件
        
        参数:
            event: Pygame 事件对象
        """
        if not self.context:
            return
            
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
            # 右键点击发出命令
            self.issue_command(event.pos)
            
    def issue_command(self, pos):
        """
        发出命令
        
        参数:
            pos: 鼠标位置 (x, y)
        """
        # 获取所有选中的实体
        selected_entities = []
        
        query = self.context.query_manager.create_query()
        query.with_component(SelectableComponent)
        entities = query.execute()
        
        for entity in entities:
            selectable = self.context.component_manager.get_component(entity, SelectableComponent)
            if selectable.selected:
                selected_entities.append(entity)
                
        if not selected_entities:
            return
            
        # 检查是否点击了其他实体
        target_entity = self.get_entity_at_position(pos)
        
        if target_entity:
            # 如果点击了其他实体，发出攻击或交互命令
            self.issue_attack_command(selected_entities, target_entity)
        else:
            # 如果点击了空地，发出移动命令
            self.issue_move_command(selected_entities, pos)
            
    def get_entity_at_position(self, pos):
        """
        获取指定位置的实体
        
        参数:
            pos: 鼠标位置 (x, y)
        
        返回:
            实体 ID 或 None
        """
        # 获取所有具有 TransformComponent 和 RenderComponent 的实体
        query = self.context.query_manager.create_query()
        query.with_all([TransformComponent, RenderComponent])
        entities = query.execute()
        
        # 按照渲染层级倒序排序（先检查上层实体）
        entities.sort(key=lambda entity: self.context.component_manager.get_component(entity, RenderComponent).layer, reverse=True)
        
        for entity in entities:
            transform = self.context.component_manager.get_component(entity, TransformComponent)
            render = self.context.component_manager.get_component(entity, RenderComponent)
            
            if not render.visible:
                continue
                
            # 检查点是否在实体内
            rect = pygame.Rect(
                transform.x - render.width // 2,
                transform.y - render.height // 2,
                render.width,
                render.height
            )
            
            if rect.collidepoint(pos):
                return entity
                
        return None
        
    def issue_move_command(self, entities, pos):
        """
        发出移动命令
        
        参数:
            entities: 要移动的实体列表
            pos: 目标位置 (x, y)
        """
        for entity in entities:
            if self.context.component_manager.has_component(entity, MovableComponent):
                movable = self.context.component_manager.get_component(entity, MovableComponent)
                movable.target_x, movable.target_y = pos
                movable.path = []
                movable.moving = True
                
                # 发布移动开始事件
                if self.context.event_manager:
                    self.context.event_manager.publish(EventType.UNIT_MOVE_STARTED, {
                        "entity": entity,
                        "target_x": pos[0],
                        "target_y": pos[1]
                    })
                
                # 发布命令发出事件
                if self.context.event_manager:
                    self.context.event_manager.publish(EventType.COMMAND_ISSUED, {
                        "entity": entity,
                        "command": "move",
                        "target_x": pos[0],
                        "target_y": pos[1]
                    })
                
    def issue_attack_command(self, entities, target):
        """
        发出攻击命令
        
        参数:
            entities: 要攻击的实体列表
            target: 目标实体
        """
        # 这里可以实现攻击逻辑
        if self.context.event_manager:
            for entity in entities:
                self.context.event_manager.publish(EventType.COMMAND_ISSUED, {
                    "entity": entity,
                    "command": "attack",
                    "target": target
                })
    # 在 CommandSystem 类中添加 update 方法
    def update(self, delta_time: float) -> None:
        """
        更新系统逻辑
        
        参数:
            delta_time: 自上一帧以来经过的时间（秒）
        """
        # 命令系统主要通过事件处理，update方法可以为空
        # 或者在这里可以添加一些持续性的命令效果，如命令执行进度等
        pass