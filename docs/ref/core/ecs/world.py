"""
游戏世界模块

提供游戏世界的核心功能，包括实体-组件管理和系统调度
"""

from typing import Dict, List, Set, Type, Any, Optional, Callable, Tuple
import logging
import time
from collections import defaultdict

from ..events.event_manager import EventManager, Event
from ..events.event_types import EventType
from .system_scheduler import SystemScheduler
from .query_builder import QueryBuilder
from .system import System


class World:
    """游戏世界，管理所有实体、组件和系统"""
    
    def __init__(self):
        """初始化游戏世界"""
        # 实体管理
        self._next_entity_id = 1
        self._entities: Set[int] = set()
        self._free_entity_ids: List[int] = []
        
        # 组件存储: 组件类型 -> (实体ID -> 组件实例)
        self._components: Dict[Type, Dict[int, Any]] = defaultdict(dict)
        
        # 实体与组件的索引: 实体ID -> 组件类型集合
        self._entity_components: Dict[int, Set[Type]] = defaultdict(set)
        
        # 事件管理器
        self._event_manager = EventManager()
        
        # 系统调度器
        self._system_scheduler = SystemScheduler()
        
        # 日志
        self._logger = logging.getLogger("World")
        
        # 实体标签: 标签 -> 实体ID集合
        self._entity_tags: Dict[str, Set[int]] = defaultdict(set)
        
        # 实体名称映射: 名称 -> 实体ID
        self._entity_names: Dict[str, int] = {}
        
    def create_entity(self, name: str = None, tags: List[str] = None) -> int:
        """
        创建实体
        
        Args:
            name: 实体名称（可选）
            tags: 实体标签列表（可选）
            
        Returns:
            int: 新实体的ID
        """
        # 从空闲ID池中获取ID，如果没有则生成新ID
        if self._free_entity_ids:
            entity_id = self._free_entity_ids.pop()
        else:
            entity_id = self._next_entity_id
            self._next_entity_id += 1
        
        # 添加到实体集合
        self._entities.add(entity_id)
        
        # 设置实体名称
        if name:
            if name in self._entity_names:
                self._logger.warning(f"Entity name '{name}' already exists, overwriting")
            self._entity_names[name] = entity_id
            
        # 添加标签
        if tags:
            for tag in tags:
                self._entity_tags[tag].add(entity_id)
                
        # 发布实体创建事件
        self._event_manager.publish(Event(
            type=EventType.ENTITY_CREATED,
            data={"entity_id": entity_id, "name": name, "tags": tags}
        ))
        
        return entity_id
        
    def destroy_entity(self, entity_id: int) -> bool:
        """
        销毁实体
        
        Args:
            entity_id: 实体ID
            
        Returns:
            bool: 是否成功销毁
        """
        if entity_id not in self._entities:
            return False
            
        # 发布实体销毁事件，让所有系统响应
        self._event_manager.publish(Event(
            type=EventType.ENTITY_DESTROYED,
            data={"entity_id": entity_id}
        ))
        
        # 移除所有组件
        for component_type in list(self._entity_components.get(entity_id, set())):
            self.remove_component(entity_id, component_type)
            
        # 从标签中移除
        for tag, entities in self._entity_tags.items():
            if entity_id in entities:
                entities.remove(entity_id)
                
        # 从名称映射中移除
        for name, eid in list(self._entity_names.items()):
            if eid == entity_id:
                del self._entity_names[name]
                
        # 从实体集合中移除
        self._entities.remove(entity_id)
        
        # 加入空闲ID池
        self._free_entity_ids.append(entity_id)
        
        # 清理实体组件索引
        if entity_id in self._entity_components:
            del self._entity_components[entity_id]
            
        return True
        
    def add_component(self, entity_id: int, component_type: Type, component: Any) -> bool:
        """
        添加组件到实体
        
        Args:
            entity_id: 实体ID
            component_type: 组件类型
            component: 组件实例
            
        Returns:
            bool: 是否成功添加
        """
        if entity_id not in self._entities:
            self._logger.warning(f"Attempt to add component to non-existent entity {entity_id}")
            return False
            
        # 添加组件
        self._components[component_type][entity_id] = component
        self._entity_components[entity_id].add(component_type)
        
        # 发布组件添加事件
        self._event_manager.publish(Event(
            type=EventType.COMPONENT_ADDED,
            data={
                "entity_id": entity_id,
                "component_type": component_type.__name__
            }
        ))
        
        return True
        
    def remove_component(self, entity_id: int, component_type: Type) -> bool:
        """
        从实体移除组件
        
        Args:
            entity_id: 实体ID
            component_type: 组件类型
            
        Returns:
            bool: 是否成功移除
        """
        if (entity_id not in self._entities or
            component_type not in self._components or
            entity_id not in self._components[component_type]):
            return False
            
        # 发布组件移除事件
        self._event_manager.publish(Event(
            type=EventType.COMPONENT_REMOVED,
            data={
                "entity_id": entity_id,
                "component_type": component_type.__name__
            }
        ))
        
        # 移除组件
        del self._components[component_type][entity_id]
        self._entity_components[entity_id].remove(component_type)
        
        return True
        
    def get_component(self, entity_id: int, component_type: Type) -> Optional[Any]:
        """
        获取实体的组件
        
        Args:
            entity_id: 实体ID
            component_type: 组件类型
            
        Returns:
            Optional[Any]: 组件实例，如果不存在则返回None
        """
        if (component_type not in self._components or
            entity_id not in self._components[component_type]):
            return None
            
        return self._components[component_type][entity_id]
        
    def has_component(self, entity_id: int, component_type: Type) -> bool:
        """
        检查实体是否拥有指定组件
        
        Args:
            entity_id: 实体ID
            component_type: 组件类型
            
        Returns:
            bool: 是否拥有组件
        """
        return (component_type in self._components and
                entity_id in self._components[component_type])
                
    def get_entities_with_component(self, component_type: Type) -> List[int]:
        """
        获取拥有指定组件的所有实体
        
        Args:
            component_type: 组件类型
            
        Returns:
            List[int]: 实体ID列表
        """
        if component_type not in self._components:
            return []
            
        return list(self._components[component_type].keys())
        
    def get_entities_with_components(self, *component_types: Type) -> List[int]:
        """
        获取同时拥有多个指定组件的所有实体
        
        Args:
            *component_types: 组件类型列表
            
        Returns:
            List[int]: 实体ID列表
        """
        if not component_types:
            return list(self._entities)
            
        # 找出第一个组件类型的实体集合
        component_type = component_types[0]
        if component_type not in self._components:
            return []
            
        entities = set(self._components[component_type].keys())
        
        # 对其他组件类型求交集
        for component_type in component_types[1:]:
            if component_type not in self._components:
                return []
                
            entities &= set(self._components[component_type].keys())
            
        return list(entities)
        
    def get_all_entity_ids(self) -> List[int]:
        """
        获取所有实体ID
        
        Returns:
            List[int]: 实体ID列表
        """
        return list(self._entities)
        
    def get_entity_count(self) -> int:
        """
        获取实体数量
        
        Returns:
            int: 实体数量
        """
        return len(self._entities)
        
    def get_all_components(self, entity_id: int) -> Dict[Type, Any]:
        """
        获取实体的所有组件
        
        Args:
            entity_id: 实体ID
            
        Returns:
            Dict[Type, Any]: 组件类型 -> 组件实例的字典
        """
        result = {}
        if entity_id not in self._entity_components:
            return result
            
        for component_type in self._entity_components[entity_id]:
            result[component_type] = self._components[component_type][entity_id]
            
        return result
        
    def get_component_count(self, component_type: Type = None) -> int:
        """
        获取组件数量
        
        Args:
            component_type: 组件类型，为None则返回所有组件数量
            
        Returns:
            int: 组件数量
        """
        if component_type is None:
            # 计算所有组件数量
            return sum(len(components) for components in self._components.values())
        elif component_type in self._components:
            return len(self._components[component_type])
        else:
            return 0
            
    def set_entity_tag(self, entity_id: int, tag: str) -> bool:
        """
        为实体设置标签
        
        Args:
            entity_id: 实体ID
            tag: 标签
            
        Returns:
            bool: 是否成功设置
        """
        if entity_id not in self._entities:
            return False
            
        self._entity_tags[tag].add(entity_id)
        return True
        
    def remove_entity_tag(self, entity_id: int, tag: str) -> bool:
        """
        移除实体标签
        
        Args:
            entity_id: 实体ID
            tag: 标签
            
        Returns:
            bool: 是否成功移除
        """
        if tag not in self._entity_tags or entity_id not in self._entity_tags[tag]:
            return False
            
        self._entity_tags[tag].remove(entity_id)
        return True
        
    def get_entities_with_tag(self, tag: str) -> List[int]:
        """
        获取拥有指定标签的所有实体
        
        Args:
            tag: 标签
            
        Returns:
            List[int]: 实体ID列表
        """
        return list(self._entity_tags.get(tag, set()))
        
    def set_entity_name(self, entity_id: int, name: str) -> bool:
        """
        设置实体名称
        
        Args:
            entity_id: 实体ID
            name: 名称
            
        Returns:
            bool: 是否成功设置
        """
        if entity_id not in self._entities:
            return False
            
        # 如果名称已存在，先移除旧映射
        if name in self._entity_names:
            self._logger.warning(f"Entity name '{name}' already exists, overwriting")
            
        self._entity_names[name] = entity_id
        return True
        
    def get_entity_by_name(self, name: str) -> Optional[int]:
        """
        通过名称获取实体ID
        
        Args:
            name: 实体名称
            
        Returns:
            Optional[int]: 实体ID，如果不存在则返回None
        """
        return self._entity_names.get(name)
        
    def query(self) -> QueryBuilder:
        """
        创建实体查询构建器
        
        Returns:
            QueryBuilder: 查询构建器实例
        """
        return QueryBuilder(self)
        
    def get_event_manager(self) -> EventManager:
        """
        获取事件管理器
        
        Returns:
            EventManager: 事件管理器实例
        """
        return self._event_manager
        
    def get_system_scheduler(self) -> SystemScheduler:
        """
        获取系统调度器
        
        Returns:
            SystemScheduler: 系统调度器实例
        """
        return self._system_scheduler
        
    def add_system(self, system: System, group_name: str = None) -> System:
        """
        添加系统
        
        Args:
            system: 系统实例
            group_name: 分组名称，为None则使用默认分组
            
        Returns:
            System: 系统实例
        """
        self._system_scheduler.add_system(system, group_name)
        return system
        
    def get_system(self, system_type: Type) -> Optional[System]:
        """
        获取系统
        
        Args:
            system_type: 系统类型
            
        Returns:
            Optional[System]: 系统实例，如果不存在则返回None
        """
        return self._system_scheduler.get_system(system_type)
        
    def remove_system(self, system: System) -> bool:
        """
        移除系统
        
        Args:
            system: 系统实例
            
        Returns:
            bool: 是否成功移除
        """
        return self._system_scheduler.remove_system(system)
        
    def initialize_systems(self, **kwargs) -> None:
        """
        初始化所有系统
        
        Args:
            **kwargs: 传递给系统的额外参数
        """
        self._system_scheduler.initialize_all(self, self._event_manager, **kwargs)
        
    def update(self, delta_time: float) -> None:
        """
        更新游戏世界
        
        Args:
            delta_time: 帧时间间隔
        """
        self._system_scheduler.update(self, delta_time)
        
    def clear(self) -> None:
        """清空游戏世界"""
        # 销毁所有实体
        for entity_id in list(self._entities):
            self.destroy_entity(entity_id)
            
        self._entities.clear()
        self._free_entity_ids.clear()
        self._components.clear()
        self._entity_components.clear()
        self._entity_tags.clear()
        self._entity_names.clear()
        
        # 重置实体ID计数器
        self._next_entity_id = 1 