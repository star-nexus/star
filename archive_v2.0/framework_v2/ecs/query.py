from typing import Dict, List, Set, Type, Tuple, Optional, Callable, Iterator, TypeVar, Generic, Any, Union
from dataclasses import dataclass, field
from collections import defaultdict
import functools

from framework_v2.ecs.entity import Entity
from framework_v2.ecs.component import Component

T = TypeVar('T', bound=Component)
C = TypeVar('C', bound=Component)

@dataclass
class QueryFilter:
    """查询过滤器，用于定义查询条件"""
    required_components: Set[Type[Component]] = field(default_factory=set)
    excluded_components: Set[Type[Component]] = field(default_factory=set)
    any_of_components: Set[Type[Component]] = field(default_factory=set)
    
    def matches(self, entity_components: Set[Type[Component]]) -> bool:
        """检查实体的组件是否匹配过滤条件"""
        # 检查必须包含的组件
        if not all(comp_type in entity_components for comp_type in self.required_components):
            return False
        
        # 检查必须排除的组件
        if any(comp_type in entity_components for comp_type in self.excluded_components):
            return False
        
        # 检查至少包含其中一个的组件
        if self.any_of_components and not any(comp_type in entity_components for comp_type in self.any_of_components):
            return False
        
        return True


class Query:
    """查询类，用于构建和执行查询"""
    
    def __init__(self, entity_manager, component_manager):
        self.entity_manager = entity_manager
        self.component_manager = component_manager
        self.filter = QueryFilter()
        self._cache = None
        self._cache_valid = False
        self._order_by_func = None
        self._limit_count = None
        self._offset_count = 0
        self._custom_filter = None
        self._on_change_callbacks = []
        
    def result(self) -> List[Entity]:
        """
        执行查询并返回匹配的实体ID列表
        
        返回:
            List[Entity]: 匹配的实体ID列表
        """
        if not self._cache_valid or self._cache is None:
            self._execute_query()
        
        return self._cache
    
    def _execute_query(self) -> None:
        """执行查询并更新缓存"""
        results = []
        
        # 遍历所有实体
        for entity in self.entity_manager.entities:
            # 获取实体的所有组件类型
            component_types = set(type(comp) for comp in self.component_manager.get_all_component(entity))
            
            # 检查是否匹配过滤条件
            if self.filter.matches(component_types):
                # 如果有自定义过滤条件，则应用
                if self._custom_filter:
                    components = self.component_manager.get_all_component(entity)
                    if not self._custom_filter(entity, components):
                        continue
                
                results.append(entity)
        
        # 如果有排序函数，则排序
        if self._order_by_func:
            results.sort(key=lambda entity: self._order_by_func(
                entity, self.component_manager.get_all_component(entity)
            ))
        
        # 应用偏移量和限制
        if self._offset_count > 0:
            results = results[self._offset_count:]
        
        if self._limit_count is not None:
            results = results[:self._limit_count]
        
        old_cache = self._cache
        self._cache = results
        self._cache_valid = True
        
        # 如果结果变化，触发回调
        if old_cache != self._cache and self._on_change_callbacks:
            for callback in self._on_change_callbacks:
                callback(self._cache)
    
    def count(self) -> int:
        """
        获取匹配实体的数量
        
        返回:
            int: 匹配实体的数量
        """
        return len(self.result())
        
    def first(self) -> Optional[Entity]:
        """
        获取第一个匹配的实体ID
        
        返回:
            Optional[Entity]: 第一个匹配的实体ID，如果没有匹配则返回None
        """
        results = self.result()
        return results[0] if results else None
    
    def iter_entities(self) -> Iterator[Entity]:
        """
        迭代查询结果中的实体ID
        
        Yields:
            Entity: 实体ID
        """
        for entity in self.result():
            yield entity
    
    def iter_components(self, *component_types: Type[C]) -> Iterator[Tuple[Entity, Tuple[C, ...]]]:
        """
        迭代查询结果中的特定组件
        
        参数:
            *component_types: 要获取的组件类型
            
        Yields:
            Tuple[Entity, Tuple[Component, ...]]: 实体ID和对应的组件元组
        """
        for entity in self.result():
            # 获取所需的组件
            components = tuple(self.component_manager.get_component(entity, comp_type) for comp_type in component_types)
            yield entity, components
    
    def for_each(self, func: Callable[[Entity, List[Component]], None]) -> None:
        """
        对每个匹配的实体执行指定的函数
        
        参数:
            func: 要执行的函数，接收实体ID和组件列表作为参数
        """
        for entity in self.result():
            components = self.component_manager.get_all_component(entity)
            func(entity, components)
    
    def on_change(self, callback: Callable[[List[Entity]], None]) -> None:
        """
        注册查询结果变化时的回调函数
        
        参数:
            callback: 回调函数，接收新的实体ID列表作为参数
        """
        self._on_change_callbacks.append(callback)
    
    def invalidate_cache(self) -> None:
        """使查询缓存失效，强制下次查询重新执行"""
        self._cache_valid = False


class QueryBuilder:
    """查询构建器，用于构建查询"""
    
    def __init__(self, query_manager):
        self.query_manager = query_manager
        self.query = query_manager.create_query()
    
    def with_all(self, *component_types: Type[Component]) -> 'QueryBuilder':
        """
        添加必须包含的组件类型
        
        参数:
            *component_types: 组件类型
            
        返回:
            QueryBuilder: 查询构建器自身，用于链式调用
        """
        self.query.filter.required_components.update(component_types)
        self.query._cache_valid = False
        return self
    
    def without(self, *component_types: Type[Component]) -> 'QueryBuilder':
        """
        添加必须排除的组件类型
        
        参数:
            *component_types: 组件类型
            
        返回:
            QueryBuilder: 查询构建器自身，用于链式调用
        """
        self.query.filter.excluded_components.update(component_types)
        self.query._cache_valid = False
        return self
    
    def with_any(self, *component_types: Type[Component]) -> 'QueryBuilder':
        """
        添加至少包含其中一个的组件类型
        
        参数:
            *component_types: 组件类型
            
        返回:
            QueryBuilder: 查询构建器自身，用于链式调用
        """
        self.query.filter.any_of_components.update(component_types)
        self.query._cache_valid = False
        return self
    
    def where(self, predicate: Callable[[Entity, List[Component]], bool]) -> 'QueryBuilder':
        """
        添加自定义过滤条件
        
        参数:
            predicate: 过滤函数，接收实体ID和组件列表，返回布尔值
            
        返回:
            QueryBuilder: 查询构建器自身，用于链式调用
        """
        self.query._custom_filter = predicate
        self.query._cache_valid = False
        return self
    
    def order_by(self, key_func: Callable[[Entity, List[Component]], Any]) -> 'QueryBuilder':
        """
        设置结果排序方式
        
        参数:
            key_func: 排序键函数，接收实体ID和组件列表，返回排序键
            
        返回:
            QueryBuilder: 查询构建器自身，用于链式调用
        """
        self.query._order_by_func = key_func
        self.query._cache_valid = False
        return self
    
    def limit(self, count: int) -> 'QueryBuilder':
        """
        限制结果数量
        
        参数:
            count: 最大结果数量
            
        返回:
            QueryBuilder: 查询构建器自身，用于链式调用
        """
        self.query._limit_count = count
        self.query._cache_valid = False
        return self
    
    def offset(self, count: int) -> 'QueryBuilder':
        """
        设置结果偏移量
        
        参数:
            count: 偏移量
            
        返回:
            QueryBuilder: 查询构建器自身，用于链式调用
        """
        self.query._offset_count = count
        self.query._cache_valid = False
        return self
    
    def paginate(self, page: int, page_size: int) -> 'QueryBuilder':
        """
        设置分页
        
        参数:
            page: 页码，从1开始
            page_size: 每页大小
            
        返回:
            QueryBuilder: 查询构建器自身，用于链式调用
        """
        self.query._offset_count = (page - 1) * page_size
        self.query._limit_count = page_size
        self.query._cache_valid = False
        return self
    
    def build(self) -> Query:
        """
        构建查询
        
        返回:
            Query: 构建的查询
        """
        return self.query
    
    def result(self) -> List[Entity]:
        """
        执行查询并返回匹配的实体ID列表
        
        返回:
            List[Entity]: 匹配的实体ID列表
        """
        return self.query.result()
    
    def count(self) -> int:
        """
        获取匹配实体的数量
        
        返回:
            int: 匹配实体的数量
        """
        return self.query.count()
    
    def first(self) -> Optional[Entity]:
        """
        获取第一个匹配的实体ID
        
        返回:
            Optional[Entity]: 第一个匹配的实体ID，如果没有匹配则返回None
        """
        return self.query.first()
    
    def iter_entities(self) -> Iterator[Entity]:
        """
        迭代查询结果中的实体ID
        
        Yields:
            Entity: 实体ID
        """
        return self.query.iter_entities()
    
    def iter_components(self, *component_types: Type[C]) -> Iterator[Tuple[Entity, Tuple[C, ...]]]:
        """
        迭代查询结果中的特定组件
        
        参数:
            *component_types: 要获取的组件类型
            
        Yields:
            Tuple[Entity, Tuple[Component, ...]]: 实体ID和对应的组件元组
        """
        return self.query.iter_components(*component_types)
    
    def for_each(self, func: Callable[[Entity, List[Component]], None]) -> None:
        """
        对每个匹配的实体执行指定的函数
        
        参数:
            func: 要执行的函数，接收实体ID和组件列表作为参数
        """
        self.query.for_each(func)
    
    def on_change(self, callback: Callable[[List[Entity]], None]) -> None:
        """
        注册查询结果变化时的回调函数
        
        参数:
            callback: 回调函数，接收新的实体ID列表作为参数
        """
        self.query.on_change(callback)


class QueryManager:
    """查询管理器，负责管理和执行查询操作"""

    def __init__(self, entity_manager, component_manager):
        self.entity_manager = entity_manager
        self.component_manager = component_manager
        self._query_cache = {}
    
    def create_query(self) -> Query:
        """
        创建一个查询实例
        
        返回:
            Query: 新的查询实例
        """
        return Query(self.entity_manager, self.component_manager)
    
    def query(self) -> QueryBuilder:
        """
        创建一个查询构建器
        
        返回:
            QueryBuilder: 新的查询构建器
        """
        return QueryBuilder(self)
    
    def with_all(self, *component_types: Type[Component]) -> QueryBuilder:
        """
        创建包含指定组件类型的查询
        
        参数:
            *component_types: 要包含的组件类型
            
        返回:
            QueryBuilder: 查询构建器
        """
        return self.query().with_all(*component_types)
    
    def without(self, *component_types: Type[Component]) -> QueryBuilder:
        """
        创建排除指定组件类型的查询
        
        参数:
            *component_types: 要排除的组件类型
            
        返回:
            QueryBuilder: 查询构建器
        """
        return self.query().without(*component_types)
    
    def with_any(self, *component_types: Type[Component]) -> QueryBuilder:
        """
        创建至少包含其中一个组件类型的查询
        
        参数:
            *component_types: 组件类型
            
        返回:
            QueryBuilder: 查询构建器
        """
        return self.query().with_any(*component_types)
    
    def where(self, predicate: Callable[[Entity, List[Component]], bool]) -> QueryBuilder:
        """
        创建带有自定义过滤条件的查询
        
        参数:
            predicate: 过滤函数
            
        返回:
            QueryBuilder: 查询构建器
        """
        return self.query().where(predicate)
    
    def cache_query(self, cache_key: str, query: Query) -> None:
        """
        缓存查询
        
        参数:
            cache_key: 缓存键
            query: 要缓存的查询
        """
        self._query_cache[cache_key] = query
    
    def get_cached_query(self, cache_key: str) -> Optional[Query]:
        """
        获取缓存的查询
        
        参数:
            cache_key: 缓存键
            
        返回:
            Optional[Query]: 缓存的查询，如果不存在则返回None
        """
        return self._query_cache.get(cache_key)
    
    def invalidate_all_caches(self) -> None:
        """使所有查询缓存失效"""
        for query in self._query_cache.values():
            query.invalidate_cache()
    
    def clear_cache(self) -> None:
        """清除所有查询缓存"""
        self._query_cache.clear()
