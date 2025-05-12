"""
系统基类

提供系统的基础实现，包括事件处理和组件过滤功能。
"""

from typing import List, Dict, Set, Type, Any, Optional, Callable
import logging
from ..events.event_manager import EventManager, Event
from ..events.event_types import EventType


class System:
    """系统基类，处理特定组件类型的实体"""
    
    def __init__(self, required_components: List[Type] = None, priority: int = 0, name: str = None):
        """
        初始化系统
        
        Args:
            required_components: 系统处理的必需组件类型列表
            priority: 系统优先级，值越高越先执行
            name: 系统名称，如果为None则使用类名
        """
        self.required_components = required_components or []
        self.priority = priority
        self.name = name or self.__class__.__name__
        self.world = None
        self.event_manager = None
        self.logger = logging.getLogger(self.name)
        self._event_handlers: Dict[EventType, List[Callable]] = {}
        
    def initialize(self, world, event_manager: EventManager, **kwargs) -> None:
        """
        初始化系统
        
        Args:
            world: 游戏世界实例
            event_manager: 事件管理器
            **kwargs: 其他参数
        """
        self.world = world
        self.event_manager = event_manager
        
        # 发布系统初始化事件
        if self.event_manager:
            self.event_manager.publish(Event(
                EventType.SYSTEM_INITIALIZED,
                {"system_name": self.name}
            ))
            
        # 注册事件处理器
        self._register_event_handlers()
        
    def shutdown(self) -> None:
        """关闭系统，清理资源"""
        # 取消注册事件处理器
        if self.event_manager:
            for event_type, handlers in self._event_handlers.items():
                for handler in handlers:
                    self.event_manager.unsubscribe(event_type, handler)
                    
            # 发布系统关闭事件
            self.event_manager.publish(Event(
                EventType.SYSTEM_SHUTDOWN,
                {"system_name": self.name}
            ))
            
    def update(self, world, delta_time: float) -> None:
        """
        更新系统，处理符合条件的实体
        
        Args:
            world: 游戏世界实例
            delta_time: 帧时间间隔
        """
        pass
        
    def process_entity(self, entity_id: int, delta_time: float) -> None:
        """
        处理单个实体
        
        Args:
            entity_id: 实体ID
            delta_time: 帧时间间隔
        """
        pass
        
    def _register_event_handlers(self) -> None:
        """注册事件处理器"""
        pass
        
    def register_event_handler(self, event_type: EventType, handler: Callable[[Event], None], priority: int = 0) -> None:
        """
        注册事件处理器
        
        Args:
            event_type: 事件类型
            handler: 处理函数
            priority: 优先级
        """
        if not self.event_manager:
            self.logger.warning(f"Cannot register event handler for {event_type} in system {self.name}. Event manager not set.")
            return
            
        # 保存处理器引用
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
            
        self._event_handlers[event_type].append(handler)
        
        # 注册到事件管理器
        self.event_manager.subscribe(event_type, handler, priority)
        
    def unregister_event_handler(self, event_type: EventType, handler: Callable[[Event], None]) -> bool:
        """
        取消注册事件处理器
        
        Args:
            event_type: 事件类型
            handler: 处理函数
            
        Returns:
            bool: 是否成功取消注册
        """
        if not self.event_manager:
            return False
            
        # 从本地列表中移除
        if event_type in self._event_handlers:
            if handler in self._event_handlers[event_type]:
                self._event_handlers[event_type].remove(handler)
                
        # 从事件管理器中取消注册
        return self.event_manager.unsubscribe(event_type, handler)
        
    def publish_event(self, event_type: EventType, data: Dict[str, Any] = None) -> None:
        """
        发布事件
        
        Args:
            event_type: 事件类型
            data: 事件数据
        """
        if not self.event_manager:
            self.logger.warning(f"Cannot publish event {event_type} from system {self.name}. Event manager not set.")
            return
            
        event = Event(
            type=event_type,
            data=data or {},
            sender=self.name
        )
        
        self.event_manager.publish(event)
        
    def get_required_entities(self, world) -> List[int]:
        """
        获取系统处理的实体列表
        
        Args:
            world: 游戏世界实例
            
        Returns:
            List[int]: 符合条件的实体ID列表
        """
        if not self.required_components:
            return []
            
        return world.get_entities_with_components(*self.required_components)


class SystemManager:
    """系统管理器，管理所有系统"""
    
    def __init__(self):
        """初始化系统管理器"""
        self.systems: List[System] = []
        self.logger = logging.getLogger("SystemManager")
        
    def add_system(self, system: System) -> None:
        """
        添加系统
        
        Args:
            system: 系统实例
        """
        self.systems.append(system)
        # 按优先级排序
        self.systems.sort(key=lambda s: s.priority, reverse=True)
        
    def remove_system(self, system: System) -> bool:
        """
        移除系统
        
        Args:
            system: 系统实例
            
        Returns:
            bool: 是否成功移除
        """
        if system in self.systems:
            self.systems.remove(system)
            return True
        return False
        
    def get_system(self, system_type: Type) -> Optional[System]:
        """
        获取指定类型的系统
        
        Args:
            system_type: 系统类型
            
        Returns:
            Optional[System]: 系统实例，如果不存在则返回None
        """
        for system in self.systems:
            if isinstance(system, system_type):
                return system
        return None
        
    def initialize_all(self, world, event_manager: EventManager) -> None:
        """
        初始化所有系统
        
        Args:
            world: 游戏世界实例
            event_manager: 事件管理器
        """
        for system in self.systems:
            system.initialize(world, event_manager)
            
    def shutdown_all(self) -> None:
        """关闭所有系统"""
        for system in self.systems:
            system.shutdown()
            
    def update_all(self, world, delta_time: float) -> None:
        """
        更新所有系统
        
        Args:
            world: 游戏世界实例
            delta_time: 帧时间间隔
        """
        for system in self.systems:
            system.update(world, delta_time) 