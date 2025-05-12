import math
from typing import List, Type
from framework_v2.ecs.system import System
from framework_v2.ecs.component import Component
from framework_v2.engine.events import EventMessage
from rotk_v2.components.transform_component import TransformComponent
from rotk_v2.components.movable_component import MovableComponent

class MovementSystem(System):
    """
    移动系统，负责处理实体的移动
    """
    def __init__(self, required_components: List[Type[Component]] = None, priority: int = 0):
        if required_components is None:
            required_components = [TransformComponent, MovableComponent]
        super().__init__(required_components, priority)
        
    def update(self, delta_time: float) -> None:
        """
        更新系统逻辑
        
        参数:
            delta_time: 自上一帧以来经过的时间（秒）
        """
        if not self.context:
            return
            
        # 获取所有具有 TransformComponent 和 MovableComponent 的实体
        entities = self.context.with_all(*self.required_components).result()
        
        for entity in entities:
            transform = self.context.component_manager.get_component(entity, TransformComponent)
            movable = self.context.component_manager.get_component(entity, MovableComponent)
            
            if not movable.moving:
                continue
                
            if movable.target_x is not None and movable.target_y is not None:
                # 计算方向向量
                dx = movable.target_x - transform.x
                dy = movable.target_y - transform.y
                distance = math.sqrt(dx * dx + dy * dy)
                
                if distance < 1:
                    # 到达目标
                    transform.x = movable.target_x
                    transform.y = movable.target_y
                    movable.moving = False
                    movable.target_x = None
                    movable.target_y = None
                    
                    # 发布移动结束事件
                    if self.context.event_manager:
                        from framework_v2.engine.events import EventType
                        self.context.event_manager.publish(EventMessage(EventType.UNIT_MOVE_ENDED, {"entity": entity}))
                else:
                    # 移动
                    speed = movable.speed * delta_time
                    if distance <= speed:
                        transform.x = movable.target_x
                        transform.y = movable.target_y
                        movable.moving = False
                        movable.target_x = None
                        movable.target_y = None
                        
                        # 发布移动结束事件
                        if self.context.event_manager:
                            from framework_v2.engine.events import EventType
                            self.context.event_manager.publish(EventMessage(EventType.UNIT_MOVE_ENDED, {"entity": entity}))
                    else:
                        transform.x += dx / distance * speed
                        transform.y += dy / distance * speed
            elif movable.path:
                # 沿路径移动
                next_point = movable.path[0]
                movable.target_x, movable.target_y = next_point
                
                # 计算方向向量
                dx = movable.target_x - transform.x
                dy = movable.target_y - transform.y
                distance = math.sqrt(dx * dx + dy * dy)
                
                if distance < 1:
                    # 到达路径点
                    transform.x = movable.target_x
                    transform.y = movable.target_y
                    movable.path.pop(0)
                    
                    if not movable.path:
                        movable.moving = False
                        movable.target_x = None
                        movable.target_y = None
                        
                        # 发布移动结束事件
                        if self.context.event_manager:
                            from framework_v2.engine.events import EventType
                            self.context.event_manager.publish(EventType.UNIT_MOVE_ENDED, {"entity": entity})
                else:
                    # 移动
                    speed = movable.speed * delta_time
                    if distance <= speed:
                        transform.x = movable.target_x
                        transform.y = movable.target_y
                        movable.path.pop(0)
                        
                        if not movable.path:
                            movable.moving = False
                            movable.target_x = None
                            movable.target_y = None
                            
                            # 发布移动结束事件
                            if self.context.event_manager:
                                from framework_v2.engine.events import EventType
                                self.context.event_manager.publish(EventType.UNIT_MOVE_ENDED, {"entity": entity})
                    else:
                        transform.x += dx / distance * speed
                        transform.y += dy / distance * speed