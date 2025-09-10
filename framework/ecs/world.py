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
    ECS World - manages entities, components, and systems.

    Optimized storage with reverse indices and a lightweight query cache
    enables efficient lookups.
    """

    def __init__(self):
        # Mapping: entity -> { component_type -> component_instance }
        self.entities: Dict[Entity, Dict[Type[Component], Component]] = {}

        # Reverse index: component_type -> set(entity)
        self._component_to_entities: Dict[Type[Component], Set[Entity]] = defaultdict(
            set
        )

        # Singleton components storage
        self._singleton_components: Dict[
            Type[SingletonComponent], SingletonComponent
        ] = {}

        # Query cache
        self._query_cache: Dict[QueryKey, Set[Entity]] = {}
        self._cache_version = 0  # cache version for invalidation tracking
        self._last_cache_cleanup = time.time()
        self._cache_hit_count = 0
        self._cache_miss_count = 0
        self._max_cache_size = 1000  # maximum number of cached entries

        # Systems list
        self.systems: List[System] = []

        # Entity ID counter
        self.entity_counter = 0

    def _invalidate_cache(self, component_types: Set[Type[Component]] = None) -> None:
        """Invalidate query cache.

        Args:
            component_types: If provided, clear only entries related to these types.
        """
        if component_types is None:
            # Global invalidation
            self._query_cache.clear()
            self._cache_version += 1
        else:
            # Selective invalidation — remove queries involving specified components
            keys_to_remove = []
            for cache_key in self._query_cache.keys():
                # Note: requires cache key structure awareness; simplified here
                keys_to_remove.append(cache_key)

            for key in keys_to_remove:
                del self._query_cache[key]

            self._cache_version += 1

    def _cleanup_cache_if_needed(self) -> None:
        """Cleanup cache periodically and enforce size limits."""
        current_time = time.time()

        # Check every 5 seconds
        if current_time - self._last_cache_cleanup > 5.0:
            if len(self._query_cache) > self._max_cache_size:
                # Simple LRU-ish strategy: remove half of entries
                keys_to_remove = list(self._query_cache.keys())[ 
                    : len(self._query_cache) // 2
                ]
                for key in keys_to_remove:
                    del self._query_cache[key]

            self._last_cache_cleanup = current_time

    def _get_cached_query_result(self, cache_key: QueryKey) -> Optional[Set[Entity]]:
        """Get cached query result if present."""
        if cache_key in self._query_cache:
            self._cache_hit_count += 1
            return self._query_cache[cache_key].copy()

        self._cache_miss_count += 1
        return None

    def _cache_query_result(self, cache_key: QueryKey, result: Set[Entity]) -> None:
        """Store query result in cache."""
        self._cleanup_cache_if_needed()
        self._query_cache[cache_key] = result.copy()

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
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
        """Manually clear query cache."""
        self._query_cache.clear()
        self._cache_version += 1

    def set_max_cache_size(self, size: int) -> None:
        """Set maximum cache size."""
        self._max_cache_size = max(1, size)
        self._cleanup_cache_if_needed()
        self.systems: List[System] = []
        self.entity_counter = 0
        
    def create_entity(self) -> Entity:
        """Create a new entity and return its ID."""
        entity_id = self.entity_counter
        self.entities[entity_id] = {}
        self.entity_counter += 1

        # Creating an empty entity doesn't impact most cached queries,
        # so cache invalidation is not required here.

        return entity_id

    def has_entity(self, entity: Entity) -> bool:
        """Check whether an entity exists."""
        return entity in self.entities

    def destroy_entity(self, entity: Entity) -> None:
        """Destroy an entity and all of its components."""
        if entity not in self.entities:
            return

        # Collect component types for this entity
        component_types = set(self.entities[entity].keys())

        # Remove from reverse index
        for component_type in component_types:
            self._component_to_entities[component_type].discard(entity)

        # Delete entity
        del self.entities[entity]

        # Invalidate caches involving these component types
        self._invalidate_cache(component_types)

    def add_component(self, entity: Entity, component: Component) -> None:
        """Add a component instance to an entity."""
        if entity not in self.entities:
            raise ValueError(f"Entity {entity} does not exist.")

        component_type = type(component)

        # Prevent singleton components from being added to entities
        if isinstance(component, SingletonComponent):
            raise ValueError(
                "Cannot add singleton component to entity. Use add_singleton_component instead."
            )

        # Add component
        self.entities[entity][component_type] = component

        # Update reverse index
        self._component_to_entities[component_type].add(entity)

        # Invalidate caches involving this component type
        self._invalidate_cache({component_type})

    def remove_component(self, entity: Entity, component_type: Type[Component]) -> bool:
        """Remove a component type from an entity."""
        if entity not in self.entities or component_type not in self.entities[entity]:
            return False

        # Remove component
        del self.entities[entity][component_type]

        # Update reverse index
        self._component_to_entities[component_type].discard(entity)

        # Invalidate caches involving this component type
        self._invalidate_cache({component_type})

        return True

    def get_component(
        self, entity: Entity, component_type: Type[ComponentType]
    ) -> Optional[ComponentType]:
        """Get a component of the specified type from an entity."""
        if entity not in self.entities:
            return None
        return self.entities[entity].get(component_type)

    def get_all_components(self, entity: Entity) -> List[Component]:
        """Get all components attached to an entity."""
        if entity not in self.entities:
            return []
        return list(self.entities[entity].values())

    def has_component(self, entity: Entity, component_type: Type[Component]) -> bool:
        """Check if an entity has a component of a given type."""
        if entity not in self.entities:
            return False
        return component_type in self.entities[entity]

    def add_singleton_component(self, component: SingletonComponent) -> None:
        """Add a singleton component instance to the world."""
        component_type = type(component)
        self._singleton_components[component_type] = component

    def get_singleton_component(
        self, component_type: Type[ComponentType]
    ) -> Optional[ComponentType]:
        """Get a singleton component instance by type."""
        return self._singleton_components.get(component_type)

    def remove_singleton_component(
        self, component_type: Type[SingletonComponent]
    ) -> bool:
        """Remove a singleton component instance by type."""
        if component_type in self._singleton_components:
            del self._singleton_components[component_type]
            return True
        return False

    def has_singleton_component(self, component_type: Type[SingletonComponent]) -> bool:
        """Check whether a singleton component of the given type exists."""
        return component_type in self._singleton_components

    def query(self) -> QueryBuilder:
        """Create a query builder bound to this world."""
        return QueryBuilder(self)

    def add_system(self, system: System) -> None:
        """Add a system, initialize/subscribe it, then sort by priority."""
        system.initialize(self)
        system.subscribe_events()
        self.systems.append(system)
        # Sort by priority (ascending)
        self.systems.sort(key=lambda s: s.priority)

    def update(self, delta_time: float) -> None:
        """Update all systems once with the provided delta time."""
        for system in self.systems:
            system_name = system.__class__.__name__
            with profiler.time_system(system_name):
                system.update(delta_time)

    def get_entities_with_component(
        self, component_type: Type[Component]
    ) -> Set[Entity]:
        """Get all entity IDs that have a given component type."""
        return self._component_to_entities[component_type].copy()

    def get_entity_count(self) -> int:
        """Total number of entities."""
        return len(self.entities)

    def get_component_count(self, component_type: Type[Component]) -> int:
        """Number of entities that currently have the given component type."""
        return len(self._component_to_entities[component_type])

    def print_world_stats(self) -> None:
        """Print world statistics (entities, component types, systems)."""
        print("=== World Statistics ===")
        print(f"Entities: {len(self.entities)}")
        print(f"Component types: {len(self._component_to_entities)}")
        print(f"Systems: {len(self.systems)}")

        for comp_type, entities in self._component_to_entities.items():
            print(f"  {comp_type.__name__}: {len(entities)} instances")

    def reset(self) -> None:
        """Reset world state and gracefully cleanup systems if supported."""
        # Shutdown: call cleanup() on systems if available
        for system in self.systems:
            if hasattr(system, 'cleanup'):
                try:
                    system.cleanup()
                except Exception as e:
                    print(f"Error during system cleanup for {system.__class__.__name__}: {e}")

        self.entities.clear()
        self._component_to_entities.clear()
        self._singleton_components.clear()
        self._query_cache.clear()
        self.systems.clear()
        self.entity_counter = 0
        self._cache_version = 0
        print("World has been reset")
