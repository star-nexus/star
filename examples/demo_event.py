"""
事件系统使用示例
"""

import sys

sys.path.append(".")

from framework_v2 import World, EntityBuilder
from examples.data_components import Position, Health, Name
from framework_v2.engine.events import EventBus, Event
from dataclasses import dataclass
from typing import Any


@dataclass
class EntityCreatedEvent(Event):
    """实体创建事件"""

    entity: int


@dataclass
class EntityDestroyedEvent(Event):
    """实体销毁事件"""

    entity: int


@dataclass
class ComponentAddedEvent(Event):
    """组件添加事件"""

    entity: int
    component_type: type
    component: Any


def on_entity_created(event: EntityCreatedEvent):
    """实体创建事件处理器"""
    print(f"✨ 实体 {event.entity} 已创建")


def on_entity_destroyed(event: EntityDestroyedEvent):
    """实体销毁事件处理器"""
    print(f"💀 实体 {event.entity} 已销毁")


def on_component_added(event: ComponentAddedEvent):
    """组件添加事件处理器"""
    component_name = event.component_type.__name__
    print(f"🔧 实体 {event.entity} 添加了组件 {component_name}")


def main():
    print("=== 事件系统示例 ===")

    # 获取事件总线和世界
    event_bus = EventBus()
    world = World()
    world.reset()
    event_bus.clear()

    # 订阅事件
    event_bus.subscribe(EntityCreatedEvent, on_entity_created)
    event_bus.subscribe(EntityDestroyedEvent, on_entity_destroyed)
    event_bus.subscribe(ComponentAddedEvent, on_component_added)

    print("已订阅事件监听器")

    # 创建实体（会触发事件）
    print("\n1. 创建实体...")
    player = world.create_entity()
    event_bus.publish(EntityCreatedEvent(entity=player))

    # 添加组件（会触发事件）
    print("\n2. 添加组件...")
    world.add_component(player, Position(10, 20, 0))
    world.add_component(player, Health(100, 100))
    world.add_component(player, Name("玩家"))
    event_bus.publish(
        ComponentAddedEvent(
            entity=player, component_type=Position, component=Position(10, 20, 0)
        )
    )

    # 使用EntityBuilder创建另一个实体
    print("\n3. 使用EntityBuilder创建实体...")
    enemy = (
        EntityBuilder(world)
        .with_component(Position(50, 30, 0))
        .with_component(Health(80, 80))
        .with_component(Name("敌人"))
        .build()
    )
    event_bus.publish(EntityCreatedEvent(entity=enemy))
    event_bus.publish(
        ComponentAddedEvent(
            entity=enemy, component_type=Position, component=Position(50, 30, 0)
        )
    )

    # 销毁实体（会触发事件）
    print("\n4. 销毁实体...")
    world.destroy_entity(enemy)
    event_bus.publish(EntityDestroyedEvent(entity=enemy))

    print("\n✅ 事件系统演示完成")


if __name__ == "__main__":
    main()
