from typing import Set, Type, Optional, Any, Dict, List, Tuple, Iterator
import hashlib


from .core import Entity, Component, ComponentType, QueryKey


class EntityBuilder:
    """实体构建器 - 链式API"""

    def __init__(self, world: "World" = None):  # type: ignore
        self.world = world
        self.entity: Entity = self.world.create_entity()

    def with_component(self, component: Component) -> "EntityBuilder":
        """添加组件"""
        self.world.add_component(self.entity, component)
        return self

    def with_components(self, *components: Component) -> "EntityBuilder":
        """添加多个组件"""
        for component in components:
            self.world.add_component(self.entity, component)
        return self

    def build(self) -> Entity:
        """构建并返回实体"""
        return self.entity


def create_entity_with_components(
    *components: Component, world: "World" = None  # type: ignore
) -> Entity:
    """便利函数：创建带组件的实体"""
    w = world
    entity = w.create_entity()
    for component in components:
        w.add_component(entity, component)
    return entity


# 查询器类 - 链式查询
class QueryBuilder:
    """
    链式查询器 - 用于查询实体和组件

    支持链式操作，高效查询实体和组件，包含智能缓存机制
    """

    def __init__(self, world: "World"):  # type: ignore
        self._world = world
        self._entities: Optional[Set[Entity]] = None  # 延迟计算
        self._required_components: Set[Type[Component]] = set()
        self._excluded_components: Set[Type[Component]] = set()
        self._cache_key: Optional[QueryKey] = None
        self._is_cached = False

    def _generate_cache_key(self) -> QueryKey:
        """生成查询的缓存键"""
        if self._cache_key is not None:
            return self._cache_key

        # 创建组件类型的稳定排序
        required_names = sorted([comp.__name__ for comp in self._required_components])
        excluded_names = sorted([comp.__name__ for comp in self._excluded_components])

        # 生成缓存键
        key_parts = [
            "req:" + ",".join(required_names),
            "exc:" + ",".join(excluded_names),
        ]
        key_string = "|".join(key_parts)

        # 使用哈希来生成简短的键
        self._cache_key = hashlib.md5(key_string.encode()).hexdigest()
        return self._cache_key

    def _compute_entities(self) -> Set[Entity]:
        """计算匹配的实体集合（带缓存）"""
        if self._entities is not None:
            return self._entities

        # 尝试从缓存获取
        cache_key = self._generate_cache_key()
        cached_result = self._world._get_cached_query_result(cache_key)

        if cached_result is not None:
            self._entities = cached_result
            self._is_cached = True
            return self._entities

        # 计算新结果
        result_entities = set(self._world.entities.keys())

        # 应用required组件过滤
        for component_type in self._required_components:
            if component_type in self._world._component_to_entities:
                component_entities = self._world._component_to_entities[component_type]
                result_entities &= component_entities
            else:
                result_entities.clear()
                break

        # 应用excluded组件过滤
        for component_type in self._excluded_components:
            if component_type in self._world._component_to_entities:
                component_entities = self._world._component_to_entities[component_type]
                result_entities -= component_entities

        # 缓存结果
        self._entities = result_entities
        self._world._cache_query_result(cache_key, result_entities)

        return self._entities

    def with_component(self, component_type: Type[ComponentType]) -> "QueryBuilder":
        """添加必须包含的组件类型"""
        new_query = QueryBuilder(self._world)
        new_query._required_components = self._required_components.copy()
        new_query._excluded_components = self._excluded_components.copy()

        new_query._required_components.add(component_type)

        return new_query

    def with_all(self, *component_types: Type[Component]) -> "QueryBuilder":
        """添加必须包含的多个组件类型（一次性添加多个组件）"""
        new_query = QueryBuilder(self._world)
        new_query._required_components = self._required_components.copy()
        new_query._excluded_components = self._excluded_components.copy()

        # 添加所有组件类型到需求列表
        for component_type in component_types:
            new_query._required_components.add(component_type)

        return new_query

    def without_component(self, component_type: Type[Component]) -> "QueryBuilder":
        """添加必须排除的组件类型"""
        new_query = QueryBuilder(self._world)
        new_query._required_components = self._required_components.copy()
        new_query._excluded_components = self._excluded_components.copy()

        new_query._excluded_components.add(component_type)

        return new_query

    def entities(self) -> Set[Entity]:
        """获取所有匹配的实体ID"""
        return self._compute_entities().copy()

    def first(self) -> Optional[Entity]:
        """获取第一个匹配的实体"""
        entities = self._compute_entities()
        return next(iter(entities)) if entities else None

    def count(self) -> int:
        """获取匹配实体的数量"""
        return len(self._compute_entities())

    def is_empty(self) -> bool:
        """检查是否没有匹配的实体"""
        return len(self._compute_entities()) == 0

    def for_each(self, func) -> None:
        """对每个匹配的实体执行函数"""
        for entity in self._compute_entities():
            func(entity)

    def get_components(self, entity: Entity) -> List[Component]:
        """获取指定实体的所有组件"""
        entities = self._compute_entities()
        if entity not in entities:
            return []
        return self._world.get_components(entity)

    def get_component(
        self, entity: Entity, component_type: Type[ComponentType]
    ) -> Optional[ComponentType]:
        """获取指定实体的特定类型组件"""
        entities = self._compute_entities()
        if entity not in entities:
            return None
        return self._world.get_component(entity, component_type)

    def iter_entities_with_all_components(
        self,
    ) -> Iterator[Tuple[Entity, List[Component]]]:
        """迭代所有匹配的实体和其组件"""
        for entity in self._compute_entities():
            components = self._world.get_all_components(entity)
            yield entity, components

    def iter_entities_with_component(
        self, component_type: Type[ComponentType]
    ) -> Iterator[Tuple[Entity, ComponentType]]:
        """迭代所有匹配的实体和指定类型的组件"""
        for entity in self._compute_entities():
            component = self._world.get_component(entity, component_type)
            if component:
                yield entity, component

    def iter_components(
        self, *component_types: Type[Component]
    ) -> Iterator[Tuple[Entity, Tuple[Component, ...]]]:
        """迭代所有匹配实体的指定类型组件

        Args:
            *component_types: 要迭代的组件类型

        Yields:
            Tuple[Entity, Tuple[Component, ...]]: 实体ID和对应的组件元组

        示例:
            for entity, (pos, vel) in query.with_all(Position, Velocity).iter_components(Position, Velocity):
                # 处理位置和速度组件
                pass
        """
        for entity in self._compute_entities():
            components = []
            skip_entity = False

            # 获取所有请求的组件
            for component_type in component_types:
                component = self._world.get_component(entity, component_type)
                if component is None:
                    skip_entity = True
                    break
                components.append(component)

            # 只有当实体拥有所有请求的组件时才yield
            if not skip_entity:
                yield entity, tuple(components)

    def iter_only_components(
        self, *component_types: Type[Component]
    ) -> Iterator[Tuple[Component, ...]]:
        """迭代所有匹配实体的指定类型组件（只返回组件，不返回实体ID）

        Args:
            *component_types: 要迭代的组件类型

        Yields:
            Tuple[Component, ...]: 组件元组
        """
        for entity, components in self.iter_components(*component_types):
            yield components

    def get_cache_info(self) -> Dict[str, Any]:
        """获取缓存信息（用于调试和性能分析）"""
        return {
            "cache_key": self._cache_key,
            "is_cached": self._is_cached,
            "required_components": [
                comp.__name__ for comp in self._required_components
            ],
            "excluded_components": [
                comp.__name__ for comp in self._excluded_components
            ],
        }
