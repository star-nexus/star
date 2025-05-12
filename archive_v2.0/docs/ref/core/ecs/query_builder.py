"""
查询构建器模块

提供高效灵活的实体查询机制
"""

from typing import List, Set, Dict, Any, Optional, Type, Callable, Tuple, Union, Iterable


class QueryBuilder:
    """实体查询构建器，提供流式API构建查询条件"""
    
    def __init__(self, world):
        """
        初始化查询构建器
        
        Args:
            world: 游戏世界实例
        """
        self.world = world
        self._all_components: List[Type] = []
        self._any_components: List[Type] = []
        self._none_components: List[Type] = []
        self._component_filters: Dict[Type, Callable[[Any], bool]] = {}
        
    def all(self, *component_types: Type) -> 'QueryBuilder':
        """
        添加必须拥有的组件类型
        
        Args:
            *component_types: 组件类型
            
        Returns:
            QueryBuilder: 查询构建器实例，用于链式调用
        """
        self._all_components.extend(component_types)
        return self
        
    def any(self, *component_types: Type) -> 'QueryBuilder':
        """
        添加至少拥有一个的组件类型
        
        Args:
            *component_types: 组件类型
            
        Returns:
            QueryBuilder: 查询构建器实例，用于链式调用
        """
        self._any_components.extend(component_types)
        return self
        
    def none(self, *component_types: Type) -> 'QueryBuilder':
        """
        添加不能拥有的组件类型
        
        Args:
            *component_types: 组件类型
            
        Returns:
            QueryBuilder: 查询构建器实例，用于链式调用
        """
        self._none_components.extend(component_types)
        return self
        
    def where(self, component_type: Type, filter_func: Callable[[Any], bool]) -> 'QueryBuilder':
        """
        添加组件属性过滤条件
        
        Args:
            component_type: 组件类型
            filter_func: 过滤函数，接收组件实例，返回布尔值
            
        Returns:
            QueryBuilder: 查询构建器实例，用于链式调用
        """
        if component_type not in self._all_components:
            self._all_components.append(component_type)
            
        self._component_filters[component_type] = filter_func
        return self
        
    def build(self) -> List[int]:
        """
        构建查询并返回符合条件的实体ID列表
        
        Returns:
            List[int]: 符合条件的实体ID列表
        """
        # 首先找到拥有所有必需组件的实体
        if not self._all_components:
            result_entities = set(self.world.get_all_entity_ids())
        else:
            result_entities = set(self.world.get_entities_with_components(*self._all_components))
            
        # 应用any条件：至少有一个组件
        if self._any_components:
            any_entities = set()
            for component_type in self._any_components:
                any_entities.update(self.world.get_entities_with_component(component_type))
                
            if not self._all_components:  # 如果没有all条件，直接使用any结果
                result_entities = any_entities
            else:  # 否则取交集
                result_entities &= any_entities
                
        # 应用none条件：排除拥有特定组件的实体
        for component_type in self._none_components:
            excluded_entities = set(self.world.get_entities_with_component(component_type))
            result_entities -= excluded_entities
            
        # 应用组件属性过滤条件
        filtered_entities = result_entities.copy()
        for entity_id in result_entities:
            for component_type, filter_func in self._component_filters.items():
                component = self.world.get_component(entity_id, component_type)
                if not component or not filter_func(component):
                    filtered_entities.remove(entity_id)
                    break
                    
        return list(filtered_entities)
        
    def count(self) -> int:
        """
        计算符合条件的实体数量
        
        Returns:
            int: 实体数量
        """
        return len(self.build())
        
    def first(self) -> Optional[int]:
        """
        获取符合条件的第一个实体ID
        
        Returns:
            Optional[int]: 实体ID，如果没有则返回None
        """
        entities = self.build()
        return entities[0] if entities else None
        
    def exists(self) -> bool:
        """
        检查是否存在符合条件的实体
        
        Returns:
            bool: 是否存在
        """
        return self.first() is not None
        
    def iterate(self) -> Iterable[Tuple[int, Dict[Type, Any]]]:
        """
        迭代所有符合条件的实体及其组件
        
        Returns:
            迭代器，产生(实体ID, 组件字典)元组
            组件字典的键为组件类型，值为组件实例
        """
        entity_ids = self.build()
        
        for entity_id in entity_ids:
            # 收集所有请求的组件
            components = {}
            for component_type in self._all_components:
                component = self.world.get_component(entity_id, component_type)
                if component:
                    components[component_type] = component
                    
            # 收集any中的组件
            for component_type in self._any_components:
                if component_type not in components:
                    component = self.world.get_component(entity_id, component_type)
                    if component:
                        components[component_type] = component
                        
            yield entity_id, components
            
    def each(self, callback: Callable[[int, Dict[Type, Any]], None]) -> int:
        """
        对每个符合条件的实体执行回调
        
        Args:
            callback: 回调函数，接收实体ID和组件字典
            
        Returns:
            int: 处理的实体数量
        """
        count = 0
        for entity_id, components in self.iterate():
            callback(entity_id, components)
            count += 1
        return count 