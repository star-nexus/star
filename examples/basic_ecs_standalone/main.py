"""
基础ECS示例 - 独立版本，展示ECS架构的基本用法

这个示例演示了：
1. 如何定义组件
2. 如何创建和管理实体
3. 如何实现基本系统
4. 如何查询和操作实体

注意：这是一个独立的ECS实现，用于演示概念，不依赖framework
"""

from dataclasses import dataclass
from abc import ABC, abstractmethod
from typing import Dict, List, Set, Type, Optional
import time


# 基础ECS定义
Entity = int


class Component(ABC):
    """组件基类"""

    pass


class System(ABC):
    """系统基类"""

    def __init__(self, required_components: List[Type[Component]]):
        self.required_components = required_components
        self.enabled = True
        self.context = None

    def initialize(self, context):
        self.context = context

    @abstractmethod
    def update(self, delta_time: float):
        pass


class EntityManager:
    """实体管理器"""

    def __init__(self):
        self.entities: Set[Entity] = set()
        self.next_id = 0

    def create_entity(self) -> Entity:
        entity = self.next_id
        self.entities.add(entity)
        self.next_id += 1
        return entity

    def destroy_entity(self, entity: Entity):
        self.entities.discard(entity)


class ComponentManager:
    """组件管理器"""

    def __init__(self):
        self.components: Dict[Type[Component], Dict[Entity, Component]] = {}

    def add_component(self, entity: Entity, component: Component):
        component_type = type(component)
        if component_type not in self.components:
            self.components[component_type] = {}
        self.components[component_type][entity] = component
        return component

    def get_component(self, entity: Entity, component_type: Type[Component]):
        if component_type in self.components:
            return self.components[component_type].get(entity)
        return None

    def has_component(self, entity: Entity, component_type: Type[Component]) -> bool:
        return (
            component_type in self.components
            and entity in self.components[component_type]
        )


class QueryManager:
    """查询管理器"""

    def __init__(
        self, entity_manager: EntityManager, component_manager: ComponentManager
    ):
        self.entity_manager = entity_manager
        self.component_manager = component_manager

    def query_entities(self, component_types: List[Type[Component]]) -> List[Entity]:
        """查询拥有指定组件的实体"""
        if not component_types:
            return list(self.entity_manager.entities)

        result = []
        for entity in self.entity_manager.entities:
            has_all = True
            for component_type in component_types:
                if not self.component_manager.has_component(entity, component_type):
                    has_all = False
                    break
            if has_all:
                result.append(entity)
        return result


class SystemManager:
    """系统管理器"""

    def __init__(self):
        self.systems: List[System] = []

    def add_system(self, system: System):
        self.systems.append(system)

    def update(self, delta_time: float):
        for system in self.systems:
            if system.enabled:
                system.update(delta_time)


class SimpleWorld:
    """简化的世界容器"""

    def __init__(self):
        self.entity_manager = EntityManager()
        self.component_manager = ComponentManager()
        self.system_manager = SystemManager()
        self.query_manager = QueryManager(self.entity_manager, self.component_manager)

        self.context = type(
            "Context",
            (),
            {
                "entity_manager": self.entity_manager,
                "component_manager": self.component_manager,
                "system_manager": self.system_manager,
                "query_manager": self.query_manager,
            },
        )()

    def create_entity(self):
        return self.entity_manager.create_entity()

    def add_component(self, entity, component):
        return self.component_manager.add_component(entity, component)

    def add_system(self, system):
        system.initialize(self.context)
        self.system_manager.add_system(system)

    def update(self, delta_time):
        self.system_manager.update(delta_time)


# 游戏组件定义
@dataclass
class NameComponent(Component):
    """名称组件"""

    name: str = "Unknown"


@dataclass
class HealthComponent(Component):
    """生命值组件"""

    max_health: int = 100
    current_health: int = 100

    def is_alive(self) -> bool:
        return self.current_health > 0

    def take_damage(self, damage: int):
        self.current_health = max(0, self.current_health - damage)

    def heal(self, amount: int):
        self.current_health = min(self.max_health, self.current_health + amount)


@dataclass
class LevelComponent(Component):
    """等级组件"""

    level: int = 1
    experience: int = 0
    experience_to_next: int = 100


# 游戏系统定义
class StatusDisplaySystem(System):
    """状态显示系统"""

    def __init__(self):
        super().__init__([NameComponent, HealthComponent, LevelComponent])

    def update(self, delta_time: float):
        entities = self.context.query_manager.query_entities(self.required_components)

        print("\n=== 角色状态 ===")
        for entity in entities:
            name = self.context.component_manager.get_component(entity, NameComponent)
            health = self.context.component_manager.get_component(
                entity, HealthComponent
            )
            level = self.context.component_manager.get_component(entity, LevelComponent)

            status = "存活" if health.is_alive() else "死亡"
            print(
                f"[{entity}] {name.name} - 等级{level.level} - "
                f"生命值:{health.current_health}/{health.max_health} - "
                f"经验:{level.experience}/{level.experience_to_next} - {status}"
            )


class ExperienceSystem(System):
    """经验系统"""

    def __init__(self):
        super().__init__([LevelComponent])
        self.update_counter = 0

    def update(self, delta_time: float):
        self.update_counter += delta_time
        if self.update_counter < 2.0:
            return

        self.update_counter = 0
        entities = self.context.query_manager.query_entities(self.required_components)

        for entity in entities:
            level_comp = self.context.component_manager.get_component(
                entity, LevelComponent
            )

            # 增加经验
            level_comp.experience += 25

            # 检查升级
            while level_comp.experience >= level_comp.experience_to_next:
                level_comp.experience -= level_comp.experience_to_next
                level_comp.level += 1
                level_comp.experience_to_next = level_comp.level * 100

                # 升级时恢复生命值
                health = self.context.component_manager.get_component(
                    entity, HealthComponent
                )
                if health:
                    health.heal(50)

                name = self.context.component_manager.get_component(
                    entity, NameComponent
                )
                if name:
                    print(f"🎉 {name.name} 升级到 {level_comp.level} 级!")


class CombatSimulationSystem(System):
    """战斗模拟系统"""

    def __init__(self):
        super().__init__([HealthComponent])
        self.update_counter = 0

    def update(self, delta_time: float):
        self.update_counter += delta_time
        if self.update_counter < 3.0:
            return

        self.update_counter = 0
        entities = self.context.query_manager.query_entities(self.required_components)

        for entity in entities:
            health = self.context.component_manager.get_component(
                entity, HealthComponent
            )

            if health.is_alive():
                damage = 15
                health.take_damage(damage)

                name = self.context.component_manager.get_component(
                    entity, NameComponent
                )
                if name:
                    print(f"⚔️ {name.name} 受到 {damage} 点伤害")
                    if not health.is_alive():
                        print(f"💀 {name.name} 死亡了!")


def main():
    print("=== 基础ECS示例（独立版本）===")
    print("这个示例展示了ECS架构的基本用法")
    print("将会创建几个角色，观察他们的状态变化、升级和战斗")
    print("按 Ctrl+C 退出\n")

    # 创建世界
    world = SimpleWorld()

    # 添加系统
    world.add_system(StatusDisplaySystem())
    world.add_system(ExperienceSystem())
    world.add_system(CombatSimulationSystem())

    # 创建角色实体
    heroes = [
        ("刘备", 120, 2),
        ("关羽", 150, 3),
        ("张飞", 140, 2),
        ("赵云", 130, 3),
    ]

    for name, max_hp, level in heroes:
        entity = world.create_entity()
        world.add_component(entity, NameComponent(name=name))
        world.add_component(
            entity, HealthComponent(max_health=max_hp, current_health=max_hp)
        )
        world.add_component(
            entity, LevelComponent(level=level, experience_to_next=level * 100)
        )
        print(f"创建角色: {name}")

    print(f"\n创建了 {len(heroes)} 个角色实体")

    # 游戏循环
    try:
        last_time = time.time()
        while True:
            current_time = time.time()
            delta_time = current_time - last_time
            last_time = current_time

            # 更新世界
            world.update(delta_time)

            # 控制更新频率
            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\n\n游戏结束!")


if __name__ == "__main__":
    main()
