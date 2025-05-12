"""
实体查询系统

提供高效的实体查询功能，支持组件过滤和批量操作。
"""

from typing import List, Dict, Set, Tuple, Type, Any, Iterable, Optional, TypeVar, Generic, Iterator, Callable
import itertools


T = TypeVar('T')


class ComponentFilter:
    """组件过滤器，用于定义查询条件"""
    
    def __init__(self):
        self.required_components: Set[Type] = set()
        self.excluded_components: Set[Type] = set()
        self.any_components: Set[Type] = set()
        
    def with_all(self, *component_types: Type) -> 'ComponentFilter':
        """
        添加必须包含的组件类型
        
        Args:
            *component_types: 要包含的组件类型
            
        Returns:
            self: 当前过滤器实例，支持链式调用
        """
        for comp_type in component_types:
            self.required_components.add(comp_type)
        return self
        
    def without_any(self, *component_types: Type) -> 'ComponentFilter':
        """
        添加必须排除的组件类型
        
        Args:
            *component_types: 要排除的组件类型
            
        Returns:
            self: 当前过滤器实例，支持链式调用
        """
        for comp_type in component_types:
            self.excluded_components.add(comp_type)
        return self
        
    def with_any(self, *component_types: Type) -> 'ComponentFilter':
        """
        添加至少包含其中一个的组件类型
        
        Args:
            *component_types: 至少包含其中一个的组件类型
            
        Returns:
            self: 当前过滤器实例，支持链式调用
        """
        for comp_type in component_types:
            self.any_components.add(comp_type)
        return self
        
    def matches(self, entity_components: Set[Type]) -> bool:
        """
        检查实体组件是否匹配过滤条件
        
        Args:
            entity_components: 实体拥有的组件类型集合
            
        Returns:
            bool: 是否匹配过滤条件
        """
        # 检查必须包含的组件
        if not self.required_components.issubset(entity_components):
            return False
            
        # 检查必须排除的组件
        if self.excluded_components.intersection(entity_components):
            return False
            
        # 检查至少包含其中一个的组件
        if self.any_components and not self.any_components.intersection(entity_components):
            return False
            
        return True


class Query:
    """实体查询类，用于高效查询满足条件的实体"""
    
    def __init__(self, world, component_filter: Optional[ComponentFilter] = None):
        """
        初始化查询对象
        
        Args:
            world: 游戏世界实例
            component_filter: 组件过滤器
        """
        self.world = world
        self.filter = component_filter or ComponentFilter()
        self._result_cache = None
        self._cache_valid = False
        
    def select(self, *component_types: Type) -> 'Query':
        """
        选择要包含的组件类型
        
        Args:
            *component_types: 要包含的组件类型
            
        Returns:
            self: 当前查询实例，支持链式调用
        """
        self.filter.with_all(*component_types)
        self._cache_valid = False
        return self
        
    def exclude(self, *component_types: Type) -> 'Query':
        """
        排除特定组件类型
        
        Args:
            *component_types: 要排除的组件类型
            
        Returns:
            self: 当前查询实例，支持链式调用
        """
        self.filter.without_any(*component_types)
        self._cache_valid = False
        return self
        
    def any_of(self, *component_types: Type) -> 'Query':
        """
        至少包含其中一个组件类型
        
        Args:
            *component_types: 至少包含其中一个的组件类型
            
        Returns:
            self: 当前查询实例，支持链式调用
        """
        self.filter.with_any(*component_types)
        self._cache_valid = False
        return self
        
    def _execute_query(self) -> Set[int]:
        """
        执行查询，返回匹配的实体ID集合
        
        Returns:
            Set[int]: 匹配的实体ID集合
        """
        result = set()
        
        # 获取所有实体
        all_entities = self.world.get_all_entities()
        
        for entity_id in all_entities:
            # 获取实体拥有的组件类型
            entity_components = set(type(comp) for comp in self.world.get_all_components_for_entity(entity_id))
            
            # 检查是否匹配过滤条件
            if self.filter.matches(entity_components):
                result.add(entity_id)
                
        return result
        
    def result(self) -> List[int]:
        """
        获取查询结果，返回匹配的实体ID列表
        
        Returns:
            List[int]: 匹配的实体ID列表
        """
        if not self._cache_valid or self._result_cache is None:
            self._result_cache = list(self._execute_query())
            self._cache_valid = True
            
        return self._result_cache
        
    def iter(self) -> Iterator[Tuple[int, Tuple]]:
        """
        迭代查询结果，返回实体ID和对应的组件元组
        
        Yields:
            Tuple[int, Tuple]: 实体ID和对应的组件元组
        """
        required_types = list(self.filter.required_components)
        
        for entity_id in self.result():
            # 获取所需的组件
            components = tuple(self.world.get_component(entity_id, comp_type) for comp_type in required_types)
            yield entity_id, components
            
    def iter_components(self, *component_types: Type) -> Iterator[Tuple[int, Tuple]]:
        """
        迭代查询结果，返回实体ID和指定的组件元组
        
        Args:
            *component_types: 要获取的组件类型
            
        Yields:
            Tuple[int, Tuple]: 实体ID和对应的组件元组
        """
        # 确保所有指定的组件类型都在必须包含的组件中
        for comp_type in component_types:
            if comp_type not in self.filter.required_components:
                self.filter.with_all(comp_type)
                self._cache_valid = False
                
        for entity_id in self.result():
            # 获取所需的组件
            components = tuple(self.world.get_component(entity_id, comp_type) for comp_type in component_types)
            yield entity_id, components
            
    def count(self) -> int:
        """
        获取匹配实体的数量
        
        Returns:
            int: 匹配实体的数量
        """
        return len(self.result())
        
    def first(self) -> Optional[int]:
        """
        获取第一个匹配的实体ID
        
        Returns:
            Optional[int]: 第一个匹配的实体ID，如果没有匹配则返回None
        """
        results = self.result()
        return results[0] if results else None
        
    def for_each(self, func: Callable[[int, Tuple], None]) -> None:
        """
        对每个匹配的实体执行指定的函数
        
        Args:
            func: 要执行的函数，接收实体ID和组件元组作为参数
        """
        for entity_id, components in self.iter():
            func(entity_id, components)
            
    def invalidate_cache(self) -> None:
        """使查询缓存失效，强制下次查询重新执行"""
        self._cache_valid = False


class QueryBuilder:
    """查询构建器，用于创建新的查询"""
    
    def __init__(self, world):
        """
        初始化查询构建器
        
        Args:
            world: 游戏世界实例
        """
        self.world = world
        
    def create(self) -> Query:
        """
        创建新的查询对象
        
        Returns:
            Query: 新的查询对象
        """
        return Query(self.world)
        
    def select(self, *component_types: Type) -> Query:
        """
        创建包含指定组件类型的查询
        
        Args:
            *component_types: 要包含的组件类型
            
        Returns:
            Query: 新的查询对象
        """
        query = self.create()
        return query.select(*component_types) 