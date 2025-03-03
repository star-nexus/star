from framework.core.ecs.entity import Entity
from framework.core.ecs.component import Component
from typing import Dict, List, Type, Set


class World:
    """
    ECS的世界容器，管理所有实体和系统
    是整个实体-组件-系统架构的中心点，负责协调实体和系统之间的交互
    使用嵌套字典存储组件数据，提高查询效率
    """
    
    def __init__(self):
        """初始化游戏世界（由于单例模式，只在第一次创建实例时调用）"""
        self.entities = set()  # 存储所有实体ID的集合
        self.systems = []  # 存储所有系统的列表
        self.components = {}  # 组件存储：{组件类型: {实体ID: 组件实例}}

    def create_entity(self) -> Entity:
        """
        创建一个新实体

        返回:
            Entity: 新创建的实体对象
        """
        entity = Entity()
        self.entities.add(entity)
        return entity

    def remove_entity(self, entity: Entity) -> None:
        """
        移除一个实体及其所有组件

        参数:
            entity: 要移除的实体
        """

        # 从实体集合中移除
        self.entities.discard(entity)
        # 移除实体的所有组件
        for component_dict in self.components.values():
            component_dict.pop(entity, None)


    def add_component(self, entity: Entity, component: Component) -> None:
        """
        为实体添加组件

        参数:
            entity_id: 实体ID
            component: 要添加的组件实例
        """
        component_type = type(component)
        if component_type not in self.components:
            self.components[component_type] = {}
        self.components[component_type][entity] = component


    def remove_component(self, entity: Entity, component_type: Type) -> None:
        """
        移除实体的组件

        参数:
            entity_id: 实体ID
            component_type: 要移除的组件类型
        """
        if component_type in self.components:
            self.components[component_type].pop(entity,None)


    def get_component(self, entity: Entity, component_type: Type) -> object:
        """
        获取实体的指定类型组件

        参数:
            entity_id: 实体ID
            component_type: 组件类型

        返回:
            object: 组件实例，如果不存在则返回None
        """
        return self.components.get(component_type, {}).get(entity)

    def has_component(self, entity: Entity, component_type: Type) -> bool:
        """
        检查实体是否拥有指定类型的组件

        参数:
            entity_id: 实体ID
            component_type: 组件类型

        返回:
            bool: 如果实体拥有该类型组件则返回True
        """
        return component_type in self.components and entity in self.components[component_type]

    def add_system(self, system):
        """
        注册一个系统到世界中

        参数:
            system: 要注册的系统对象

        返回:
            System: 被注册的系统对象
        """
        self.systems.append(system)


        # 根据优先级排序系统
        self.systems.sort(key=lambda s: s.priority)
        return system

    def remove_system(self, system) -> None:
        """
        注销一个系统

        参数:
            system: 要注销的系统对象
        """
        if system in self.systems:
            self.systems.remove(system)

    def update(self, delta_time: float) -> None:
        """
        更新所有系统

        参数:
            delta_time: 帧间时间差（秒）
        """
        for system in self.systems:
            if system.is_enabled():
                system.update(self,delta_time)

    def get_entities_with_components(self, *component_types: Type) -> List[Entity]:
        """
        获取拥有指定组件类型的实体集合
        参数:
            *component_types: 要匹配的组件类型
        返回:
            List[Entity]: 拥有指定组件类型的实体集合
        """
        entities = []
        for entity in self.entities:
            if all(self.get_component(entity, ct) is not None for ct in component_types):
                entities.append(entity)
        return entities
