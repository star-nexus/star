"""
基础ECS示例 - 展示ECS架构的基本用法

这个示例演示了：
1. 如何定义组件
2. 如何创建和管理实体
3. 如何实现基本系统
4. 如何查询和操作实体
"""

import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "../.."))

from dataclasses import dataclass
from framework.ecs.world import World
from framework.ecs.component import Component
from framework.ecs.system import System
from framework.ecs.entity import Entity
import time


# 定义组件
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


# 简化的World类，避免循环导入
# 删除 SimpleWorld 类，使用框架中的 World 类


# 定义系统
class StatusDisplaySystem(System):
    """状态显示系统 - 显示所有角色的状态"""

    def __init__(self):
        super().__init__([NameComponent, HealthComponent, LevelComponent])

    def update(self, delta_time: float):
        if not self.context:
            return

        entities = (
            self.context.query_manager.query()
            .with_all(*self.required_components)
            .result()
        )

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
    """经验系统 - 处理角色升级"""

    def __init__(self):
        super().__init__([LevelComponent])
        self.update_counter = 0

    def update(self, delta_time: float):
        if not self.context:
            return

        # 每2秒给所有角色增加经验
        self.update_counter += delta_time
        if self.update_counter < 2.0:
            return

        self.update_counter = 0
        entities = (
            self.context.query_manager.query()
            .with_all(*self.required_components)
            .result()
        )

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
    """战斗模拟系统 - 模拟角色受伤"""

    def __init__(self):
        super().__init__([HealthComponent])
        self.update_counter = 0

    def update(self, delta_time: float):
        if not self.context:
            return

        # 每3秒模拟一次战斗
        self.update_counter += delta_time
        if self.update_counter < 3.0:
            return

        self.update_counter = 0
        entities = (
            self.context.query_manager.query()
            .with_all(*self.required_components)
            .result()
        )

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
    print("=== 基础ECS示例 ===")
    print("这个示例展示了ECS架构的基本用法")
    print("将会创建几个角色，观察他们的状态变化、升级和战斗")
    print("按 Ctrl+C 退出\n")

    # 创建世界
    world = World()

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
