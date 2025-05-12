from typing import Dict, List, Set, Type, Optional, Any
import logging

from framework.ecs.entity import Entity
from framework.ecs.component import Component
from framework.ecs.system import System


class EntityManager:
    """
    实体管理器，负责创建和销毁实体
    """

    def __init__(self):
        self.entities: Set[Entity] = set()
        self.uuid: int = 0
        self.logger = logging.getLogger("EntityManager")

    def create_entity(self) -> Entity:
        """
        创建一个新的实体

        返回:
            Entity: 新创建的实体
        """
        entity = Entity(self.uuid)
        self.entities.add(entity)
        self.uuid += 1
        return entity

    def destroy_entity(self, entity: Entity) -> None:
        """
        移除一个实体

        参数:
            entity: 要移除的实体
        """
        self.entities.discard(entity)

    def get_entity_count(self) -> int:
        """
        获取实体数量

        返回:
            int: 实体数量
        """
        return len(self.entities)

    def is_entity_exists(self, entity: Entity) -> bool:
        """
        检查实体是否存在

        参数:
            entity: 要检查的实体
        返回:
            bool: 如果实体存在则返回True，否则返回False
        """
        return entity in self.entities

    def get_all_entity(self) -> List[Entity]:
        """
        获取所有实体
        返回:
            List[Entity]: 所有实体的列表
        """
        return list(self.entities)

    def clear_entities(self) -> None:
        """清除所有实体"""
        self.entities.clear()
        self.logger.info("已清除所有实体")


class ComponentManager:
    """
    组件管理器，负责管理实体的组件
    """

    def __init__(self):
        self.components: Dict[Type[Component], Dict[Entity, Component]] = {}
        self.logger = logging.getLogger("ComponentManager")

    def add_component(self, entity: Entity, component: Component) -> Component:
        """
        为实体添加一个组件

        参数:
            entity: 要添加组件的实体
            component: 要添加的组件

        返回:
            Component: 添加的组件
        """
        component_type = type(component)
        if component_type not in self.components:
            self.components[component_type] = {}
        self.components[component_type][entity] = component
        return component

    def remove_component(self, entity: Entity, component_type: Type[Component]) -> None:
        """
        移除实体的一个组件

        参数:
            entity: 要移除组件的实体
            component_type: 要移除的组件类型
        """
        if component_type in self.components:
            self.components[component_type].pop(entity, None)

    def get_component(
        self, entity: Entity, component_type: Type[Component]
    ) -> Optional[Component]:
        """
        获取实体的一个组件

        参数:
            entity: 要获取组件的实体
            component_type: 要获取的组件类型

        返回:
            Optional[Component]: 获取到的组件，如果实体没有该组件则返回None
        """
        return self.components.get(component_type, {}).get(entity)

    def has_component(self, entity: Entity, component_type: Type[Component]) -> bool:
        """
        检查实体是否拥有一个组件

        参数:
            entity: 要检查的实体
            component_type: 要检查的组件类型

        返回:
            bool: 如果实体拥有该组件则返回True，否则返回False
        """
        return (
            component_type in self.components
            and entity in self.components[component_type]
        )

    def get_all_component(self, entity: Entity) -> List[Component]:
        """
        获取实体的所有组件

        参数:
            entity: 要获取组件的实体

        返回:
            List[Component]: 实体拥有的所有组件
        """
        return [
            component
            for component_dict in self.components.values()
            for entity_id, component in component_dict.items()
            if entity_id == entity
        ]

    def remove_all_component(self, entity: Entity) -> None:
        """
        移除实体的所有组件

        参数:
            entity: 要移除组件的实体
        """
        for component_type in list(self.components.keys()):
            if entity in self.components[component_type]:
                del self.components[component_type][entity]

    def clear_components(self) -> None:
        """清除所有组件"""
        self.components.clear()
        self.logger.info("已清除所有组件")


class SystemManager:
    """
    系统管理器，负责管理和更新系统
    """

    def __init__(self):
        self.systems: List[System] = []
        self.system_types: Dict[Type[System], System] = {}
        self.logger = logging.getLogger("SystemManager")

    def add_system(self, system: System) -> None:
        """
        添加一个系统到系统管理器

        参数:
            system: 要添加的系统
        """
        if system not in self.systems:
            self.systems.append(system)
            # 存储系统类型到系统实例的映射，用于快速查找
            self.system_types[type(system)] = system
            # 按优先级排序
            self.systems.sort(key=lambda s: s.priority)
            self.logger.debug(f"添加系统: {type(system).__name__}")

    def remove_system(self, system: System) -> bool:
        """
        从系统管理器中移除一个系统

        参数:
            system: 要移除的系统

        返回:
            bool: 如果成功移除则返回True，否则返回False
        """
        if system in self.systems:
            self.systems.remove(system)
            # 移除系统类型映射
            if type(system) in self.system_types:
                del self.system_types[type(system)]
            self.logger.debug(f"移除系统: {type(system).__name__}")
            return True
        return False

    def get_system_count(self) -> int:
        """
        获取系统数量

        返回:
            int: 系统数量
        """
        return len(self.systems)

    def get_system(self, system_type: Type[System]) -> Optional[System]:
        """
        根据系统类型获取系统实例

        参数:
            system_type: 系统类型

        返回:
            Optional[System]: 系统实例，如果不存在则返回None
        """
        return self.system_types.get(system_type)

    def update(self, delta_time: float) -> None:
        """
        更新所有系统

        参数:
            delta_time: 时间增量
        """
        for system in self.systems:
            system.update(delta_time)
            self.logger.debug(f"更新系统 {system.__class__.__name__}")

    def clear_all_systems(self) -> None:
        """清除所有系统"""
        self.systems.clear()
        self.system_types.clear()
        self.logger.info("已清除所有系统")
