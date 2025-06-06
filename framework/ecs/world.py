from framework.ecs.query import QueryManager
from framework.ecs.entity import Entity
from framework.ecs.component import Component
from framework.ecs.system import System
from framework.ecs.manager import EntityManager, ComponentManager, SystemManager
from framework.ecs.context import ECSContext

from typing import Dict, List, Type, Set, Optional
import logging


class World:
    """
    ECS的世界容器，管理所有实体和系统
    是整个实体-组件-系统架构的中心点，负责协调实体和系统之间的交互
    使用嵌套字典存储组件数据，提高查询效率
    """

    def __init__(self):
        """初始化游戏世界（由于单例模式，只在第一次创建实例时调用）"""
        self.entity_manager = EntityManager()
        self.component_manager = ComponentManager()
        self.system_manager = SystemManager()
        self.query_manager = QueryManager(self.entity_manager, self.component_manager)

        self.context = ECSContext()
        self.context.init_ecs_managers(
            entity_manager=self.entity_manager,
            component_manager=self.component_manager,
            system_manager=self.system_manager,
            query_manager=self.query_manager,
        )

        self.logger = logging.getLogger("World")

    def update(self, delta_time: float) -> None:
        """
        更新游戏世界
        依次调用所有系统的update方法
        """
        self.system_manager.update(delta_time)

        # EntityManager 统一接口

    def create_entity(self) -> Entity:
        """创建一个新实体"""
        if self.entity_manager:
            return self.entity_manager.create_entity()
        self.logger.error("尝试创建实体，但实体管理器未设置")
        return None

    def destroy_entity(self, entity: Entity) -> None:
        """销毁一个实体"""
        if self.entity_manager:
            self.entity_manager.destroy_entity(entity)

            # 同时移除实体的所有组件
            if self.component_manager:
                self.component_manager.remove_all_component(entity)
        else:
            self.logger.error("尝试销毁实体，但实体管理器未设置")

    # ComponentManager 统一接口
    def add_component(self, entity: Entity, component: Component) -> Component:
        """为实体添加组件"""
        if self.component_manager:
            return self.component_manager.add_component(entity, component)
        self.logger.error("尝试添加组件，但组件管理器未设置")
        return component

    def remove_component(self, entity: Entity, component_type: Type[Component]) -> None:
        """从实体移除组件"""
        if self.component_manager:
            self.component_manager.remove_component(entity, component_type)
        else:
            self.logger.error("尝试移除组件，但组件管理器未设置")

    def get_component(
        self, entity: Entity, component_type: Type[Component]
    ) -> Optional[Component]:
        """获取实体的组件"""
        if self.component_manager:
            return self.component_manager.get_component(entity, component_type)
        self.logger.error("尝试获取组件，但组件管理器未设置")
        return None

    def has_component(self, entity: Entity, component_type: Type[Component]) -> bool:
        """检查实体是否有组件"""
        if self.component_manager:
            return self.component_manager.has_component(entity, component_type)
        self.logger.error("尝试检查组件，但组件管理器未设置")
        return False

    def get_all_components(self, entity: Entity) -> List[Component]:
        """获取实体的所有组件"""
        if self.component_manager:
            return self.component_manager.get_all_component(entity)
        self.logger.error("尝试获取所有组件，但组件管理器未设置")
        return []

    # SystemManager 统一接口
    def add_system(self, system: System) -> None:
        """添加系统"""
        if self.system_manager:
            # 设置系统的上下文
            system.initialize(self.context)
            system.subscribe_events()  # 订阅事件
            self.system_manager.add_system(system)
        else:
            self.logger.error("尝试添加系统，但系统管理器未设置")

    def remove_system(self, system: System) -> bool:
        """移除系统"""
        if self.system_manager:
            return self.system_manager.remove_system(system)
        self.logger.error("尝试移除系统，但系统管理器未设置")
        return False

    def get_system(self, system_type: Type[System]) -> Optional[System]:
        """获取系统"""
        if self.system_manager:
            return self.system_manager.get_system(system_type)
        self.logger.error("尝试获取系统，但系统管理器未设置")
        return None

    def update_systems(self, delta_time: float) -> None:
        """更新所有系统"""
        if self.system_manager:
            self.system_manager.update(delta_time)
        else:
            self.logger.error("尝试更新系统，但系统管理器未设置")
