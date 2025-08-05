from .core import (
    Entity,
    Component,
    System,
    SingletonComponent,
    QueryKey,
    ComponentType,
)
from .builder import QueryBuilder
from typing import Dict, Set, Type, List, Any, Optional
from collections import defaultdict
import time
from performance_profiler import profiler


class World:
    """
    世界类 - 管理实体、组件和系统

    优化的存储结构支持高效查询，包含智能缓存机制
    """

    def __init__(self):
        # 实体到组件的映射
        self.entities: Dict[Entity, Dict[Type[Component], Component]] = {}

        # 组件类型到实体集合的反向索引 - 用于高效查询
        self._component_to_entities: Dict[Type[Component], Set[Entity]] = defaultdict(
            set
        )

        # 单例组件存储
        self._singleton_components: Dict[
            Type[SingletonComponent], SingletonComponent
        ] = {}

        # 查询缓存系统
        self._query_cache: Dict[QueryKey, Set[Entity]] = {}
        self._cache_version = 0  # 缓存版本号，用于检测缓存失效
        self._last_cache_cleanup = time.time()
        self._cache_hit_count = 0
        self._cache_miss_count = 0
        self._max_cache_size = 1000  # 最大缓存条目数

        # 系统列表
        self.systems: List[System] = []

        # 实体ID计数器
        self.entity_counter = 0

    def _invalidate_cache(self, component_types: Set[Type[Component]] = None) -> None:
        """使缓存失效

        Args:
            component_types: 如果提供，只清理涉及这些组件类型的缓存
        """
        if component_types is None:
            # 全局缓存失效
            self._query_cache.clear()
            self._cache_version += 1
        else:
            # 选择性缓存失效 - 移除包含指定组件的查询缓存
            keys_to_remove = []
            for cache_key in self._query_cache.keys():
                # 这里需要一个更复杂的逻辑来检查缓存键是否涉及特定组件
                # 为了简化，我们暂时使用全局失效
                keys_to_remove.append(cache_key)

            for key in keys_to_remove:
                del self._query_cache[key]

            self._cache_version += 1

    def _cleanup_cache_if_needed(self) -> None:
        """如果需要，清理缓存"""
        current_time = time.time()

        # 每5秒检查一次缓存大小
        if current_time - self._last_cache_cleanup > 5.0:
            if len(self._query_cache) > self._max_cache_size:
                # 简单的LRU策略：删除一半的缓存
                keys_to_remove = list(self._query_cache.keys())[
                    : len(self._query_cache) // 2
                ]
                for key in keys_to_remove:
                    del self._query_cache[key]

            self._last_cache_cleanup = current_time

    def _get_cached_query_result(self, cache_key: QueryKey) -> Optional[Set[Entity]]:
        """获取缓存的查询结果"""
        if cache_key in self._query_cache:
            self._cache_hit_count += 1
            return self._query_cache[cache_key].copy()

        self._cache_miss_count += 1
        return None

    def _cache_query_result(self, cache_key: QueryKey, result: Set[Entity]) -> None:
        """缓存查询结果"""
        self._cleanup_cache_if_needed()
        self._query_cache[cache_key] = result.copy()

    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        total_requests = self._cache_hit_count + self._cache_miss_count
        hit_rate = (
            (self._cache_hit_count / total_requests) if total_requests > 0 else 0.0
        )

        return {
            "cache_size": len(self._query_cache),
            "cache_version": self._cache_version,
            "hit_count": self._cache_hit_count,
            "miss_count": self._cache_miss_count,
            "hit_rate": hit_rate,
            "max_cache_size": self._max_cache_size,
        }

    def clear_cache(self) -> None:
        """手动清空查询缓存"""
        self._query_cache.clear()
        self._cache_version += 1

    def set_max_cache_size(self, size: int) -> None:
        """设置最大缓存大小"""
        self._max_cache_size = max(1, size)
        self._cleanup_cache_if_needed()

        # 系统列表
        self.systems: List[System] = []

        # 实体ID计数器
        self.entity_counter = 0

    def create_entity(self) -> Entity:
        """创建新实体并返回其ID"""
        entity_id = self.entity_counter
        self.entities[entity_id] = {}
        self.entity_counter += 1

        # 实体创建可能影响查询结果，但由于新实体没有组件，
        # 大多数查询不会受到影响，所以这里不需要清空缓存

        return entity_id

    def has_entity(self, entity: Entity) -> bool:
        """检查实体是否存在"""
        return entity in self.entities

    def destroy_entity(self, entity: Entity) -> None:
        """销毁实体及其所有组件"""
        if entity not in self.entities:
            return

        # 收集该实体的所有组件类型
        component_types = set(self.entities[entity].keys())

        # 从反向索引中移除
        for component_type in component_types:
            self._component_to_entities[component_type].discard(entity)

        # 删除实体
        del self.entities[entity]

        # 实体销毁会影响所有相关的查询缓存
        self._invalidate_cache(component_types)

    def add_component(self, entity: Entity, component: Component) -> None:
        """向实体添加组件"""
        if entity not in self.entities:
            raise ValueError(f"Entity {entity} does not exist.")

        component_type = type(component)

        # 检查是否是单例组件
        if isinstance(component, SingletonComponent):
            raise ValueError(
                "Cannot add singleton component to entity. Use add_singleton_component instead."
            )

        # 添加组件
        self.entities[entity][component_type] = component

        # 更新反向索引
        self._component_to_entities[component_type].add(entity)

        # 添加组件会影响涉及该组件类型的查询
        self._invalidate_cache({component_type})

    def remove_component(self, entity: Entity, component_type: Type[Component]) -> bool:
        """从实体移除组件"""
        if entity not in self.entities or component_type not in self.entities[entity]:
            return False

        # 移除组件
        del self.entities[entity][component_type]

        # 更新反向索引
        self._component_to_entities[component_type].discard(entity)

        # 移除组件会影响涉及该组件类型的查询
        self._invalidate_cache({component_type})

        return True

    def get_component(
        self, entity: Entity, component_type: Type[ComponentType]
    ) -> Optional[ComponentType]:
        """获取实体的特定类型组件"""
        if entity not in self.entities:
            return None
        return self.entities[entity].get(component_type)

    def get_all_components(self, entity: Entity) -> List[Component]:
        """获取实体的所有组件"""
        if entity not in self.entities:
            return []
        return list(self.entities[entity].values())

    def has_component(self, entity: Entity, component_type: Type[Component]) -> bool:
        """检查实体是否有特定类型的组件"""
        if entity not in self.entities:
            return False
        return component_type in self.entities[entity]

    def add_singleton_component(self, component: SingletonComponent) -> None:
        """添加单例组件"""
        component_type = type(component)
        self._singleton_components[component_type] = component

    def get_singleton_component(
        self, component_type: Type[ComponentType]
    ) -> Optional[ComponentType]:
        """获取单例组件"""
        return self._singleton_components.get(component_type)

    def remove_singleton_component(
        self, component_type: Type[SingletonComponent]
    ) -> bool:
        """移除单例组件"""
        if component_type in self._singleton_components:
            del self._singleton_components[component_type]
            return True
        return False

    def has_singleton_component(self, component_type: Type[SingletonComponent]) -> bool:
        """检查是否有特定类型的单例组件"""
        return component_type in self._singleton_components

    def query(self) -> QueryBuilder:
        """创建查询器"""
        return QueryBuilder(self)

    def add_system(self, system: System) -> None:
        """添加系统"""
        system.initialize(self)
        system.subscribe_events()
        self.systems.append(system)
        # 按优先级排序
        self.systems.sort(key=lambda s: s.priority)

    def update(self, delta_time: float) -> None:
        """更新所有系统"""
        for system in self.systems:
            system_name = system.__class__.__name__
            with profiler.time_system(system_name):
                system.update(delta_time)

    def get_entities_with_component(
        self, component_type: Type[Component]
    ) -> Set[Entity]:
        """获取拥有特定组件类型的所有实体"""
        return self._component_to_entities[component_type].copy()

    def get_entity_count(self) -> int:
        """获取实体总数"""
        return len(self.entities)

    def get_component_count(self, component_type: Type[Component]) -> int:
        """获取特定类型组件的数量"""
        return len(self._component_to_entities[component_type])

    def print_world_stats(self) -> None:
        """打印世界统计信息"""
        print(f"=== 世界统计 ===")
        print(f"实体数量: {len(self._entities)}")
        print(f"组件类型数量: {len(self._components)}")
        print(f"系统数量: {len(self._systems)}")

        for comp_type, entities in self._components.items():
            print(f"  {comp_type.__name__}: {len(entities)} 个实例")

    def reset(self) -> None:
        """重置世界状态"""
        self.entities.clear()
        self._component_to_entities.clear()
        self._singleton_components.clear()
        self._query_cache.clear()
        self.systems.clear()
        self.entity_counter = 0
        self._cache_version = 0
        print("世界已重置")
