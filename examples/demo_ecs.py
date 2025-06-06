"""
Framework V2 使用示例
"""

import time
from framework_v2 import World, System
from examples.data_components import Position, Velocity, Health, Name
from framework_v2.systems import MovementSystem, HealthSystem, SimplePhysicsSystem
from framework_v2.ecs.builder import (
    EntityBuilder,
    create_entity_with_components,
    print_world_stats,
)


def example_basic_usage():
    """基本使用示例"""
    print("=== 基本使用示例 ===")

    # 获取世界单例
    world = World()
    world.clear()  # 清空之前的数据

    # 创建实体的几种方式

    # 方式1: 分步创建
    player = world.create_entity()
    world.add_component(player, Position(10, 20, 0))
    world.add_component(player, Velocity(1, 0, 0))
    world.add_component(player, Health(100, 100))
    world.add_component(player, Name("玩家"))

    # 方式2: 使用EntityBuilder
    enemy = (
        EntityBuilder(world)
        .with_component(Position(50, 30, 0))
        .with_component(Velocity(-0.5, 0, 0))
        .with_component(Health(80, 80))
        .with_component(Name("敌人"))
        .build()
    )

    # 方式3: 使用便利函数
    npc = create_entity_with_components(Position(0, 0, 0), Name("NPC"), world=world)

    print(f"创建了 {len(world._entities)} 个实体")

    # 查询示例
    print("\n=== 查询示例 ===")

    # 查询所有有位置的实体
    positioned_entities = world.query(Position).entities()
    print(f"有位置组件的实体: {len(positioned_entities)}")

    # 查询可移动的实体（有位置和速度）
    movable_entities = world.query(Position, Velocity)
    print(f"可移动的实体: {len(movable_entities)}")

    # 迭代实体和组件
    print("\n移动实体状态:")
    for entity, pos, vel in movable_entities.with_components():
        name_comp = world.get_component(entity, Name)
        name = name_comp.value if name_comp else f"实体{entity}"
        print(
            f"  {name}: 位置({pos.x:.1f}, {pos.y:.1f}) 速度({vel.x:.1f}, {vel.y:.1f})"
        )


def example_system_usage():
    """系统使用示例"""
    print("\n=== 系统使用示例 ===")

    world = World()

    # 添加系统
    world.add_system(MovementSystem(priority=1))
    world.add_system(HealthSystem(priority=2))
    world.add_system(SimplePhysicsSystem(gravity=-1.0, drag=0.99, priority=0))

    print("已添加移动、生命值和物理系统")

    # 模拟游戏循环
    print("\n模拟游戏循环...")
    delta_time = 0.1

    for frame in range(5):
        print(f"\n帧 {frame + 1}:")

        # 更新所有系统
        world.update(delta_time)

        # 显示状态
        for entity, pos, vel in world.query(Position, Velocity).with_components():
            name_comp = world.get_component(entity, Name)
            name = name_comp.value if name_comp else f"实体{entity}"
            print(
                f"  {name}: 位置({pos.x:.1f}, {pos.y:.1f}) 速度({vel.x:.2f}, {vel.y:.2f})"
            )


def example_custom_system():
    """自定义系统示例"""
    print("\n=== 自定义系统示例 ===")

    class CollisionSystem(System):
        """简单碰撞检测系统"""

        def update(self, delta_time: float) -> None:
            entities_with_pos = list(self.world.query(Position).with_components())

            # 简单的距离碰撞检测
            for i, (entity1, pos1) in enumerate(entities_with_pos):
                for entity2, pos2 in entities_with_pos[i + 1 :]:
                    distance = ((pos1.x - pos2.x) ** 2 + (pos1.y - pos2.y) ** 2) ** 0.5
                    if distance < 5.0:  # 碰撞距离阈值
                        name1 = self.world.get_component(entity1, Name)
                        name2 = self.world.get_component(entity2, Name)
                        n1 = name1.value if name1 else f"实体{entity1}"
                        n2 = name2.value if name2 else f"实体{entity2}"
                        print(f"  碰撞检测: {n1} 与 {n2} 距离 {distance:.1f}")

    world = World()
    world.add_system(CollisionSystem(priority=10))

    # 运行一次更新来测试碰撞
    world.update(0.1)


def performance_test():
    """性能测试"""
    print("\n=== 性能测试 ===")

    world = World()
    world.clear()

    # 创建大量实体进行测试
    print("创建1000个测试实体...")
    start_time = time.time()

    for i in range(1000):
        EntityBuilder(world).with_components(
            Position(i % 100, i // 100, 0),
            Velocity((i % 3) - 1, (i % 5) - 2, 0),
            Health(100, 100),
            Name(f"测试实体{i}"),
        ).build()

    create_time = time.time() - start_time
    print(f"创建耗时: {create_time:.3f}s")

    # 添加系统
    world.add_system(MovementSystem())
    world.add_system(HealthSystem())

    # 测试更新性能
    print("测试100次更新...")
    start_time = time.time()

    for _ in range(100):
        world.update(0.016)  # ~60 FPS

    update_time = time.time() - start_time
    print(f"更新耗时: {update_time:.3f}s ({update_time/100*1000:.2f}ms/frame)")

    print_world_stats(world)


if __name__ == "__main__":
    example_basic_usage()
    example_system_usage()
    example_custom_system()
    performance_test()
