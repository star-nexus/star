"""
ECS 链式查询器使用示例

展示如何使用新的查询器 API 进行高效的实体和组件查询
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dataclasses import dataclass
from framework_v2.ecs.core import Component, SingletonComponent
from framework_v2.ecs.world import World


# 定义一些示例组件
@dataclass
class Position(Component):
    x: float
    y: float


@dataclass
class Velocity(Component):
    dx: float
    dy: float


@dataclass
class Health(Component):
    current: int
    maximum: int


@dataclass
class Damage(Component):
    value: int


@dataclass
class Player(Component):
    """玩家标记组件"""

    name: str


# 定义单例组件
@dataclass
class GameTime(SingletonComponent):
    elapsed: float
    delta: float


@dataclass
class GameSettings(SingletonComponent):
    difficulty: str
    sound_enabled: bool


def main():
    # 创建世界
    world = World()

    # 添加单例组件
    world.add_singleton_component(GameTime(elapsed=0.0, delta=0.016))
    world.add_singleton_component(GameSettings(difficulty="normal", sound_enabled=True))

    # 创建一些实体
    player = world.create_entity()
    world.add_component(player, Position(10.0, 20.0))
    world.add_component(player, Velocity(5.0, 0.0))
    world.add_component(player, Health(100, 100))
    world.add_component(player, Player("Hero"))

    enemy1 = world.create_entity()
    world.add_component(enemy1, Position(50.0, 30.0))
    world.add_component(enemy1, Velocity(-2.0, 0.0))
    world.add_component(enemy1, Health(50, 50))
    world.add_component(enemy1, Damage(25))

    enemy2 = world.create_entity()
    world.add_component(enemy2, Position(80.0, 40.0))
    world.add_component(enemy2, Health(30, 30))
    world.add_component(enemy2, Damage(15))

    static_object = world.create_entity()
    world.add_component(static_object, Position(100.0, 50.0))
    world.add_component(static_object, Health(200, 200))

    print("=== ECS 链式查询器示例 ===\n")

    # 1. 基本查询 - 查找所有有位置的实体
    print("1. 查找所有有位置的实体:")
    entities_with_position = world.query().with_component(Position).entities()
    print(f"   找到 {len(entities_with_position)} 个实体: {entities_with_position}")

    # 2. 多组件查询 - 查找同时有位置和速度的实体（可移动对象）
    print("\n2. 查找可移动对象（有位置和速度）:")
    movable_entities = (
        world.query().with_component(Position).with_component(Velocity).entities()
    )
    print(f"   找到 {len(movable_entities)} 个可移动实体: {movable_entities}")

    # 3. 排除查询 - 查找有生命值但没有伤害的实体（非攻击性）
    print("\n3. 查找非攻击性实体（有生命值但没有伤害）:")
    non_aggressive = (
        world.query().with_component(Health).without_component(Damage).entities()
    )
    print(f"   找到 {len(non_aggressive)} 个非攻击性实体: {non_aggressive}")

    # 4. 复杂链式查询 - 查找可移动的敌人（有位置、速度、伤害，但不是玩家）
    print("\n4. 查找可移动的敌人:")
    mobile_enemies = (
        world.query()
        .with_component(Position)
        .with_component(Velocity)
        .with_component(Damage)
        .without_component(Player)
        .entities()
    )
    print(f"   找到 {len(mobile_enemies)} 个可移动敌人: {mobile_enemies}")

    # 5. 查询单例组件
    print("\n5. 查询单例组件:")
    game_time = world.get_singleton_component(GameTime)
    game_settings = world.get_singleton_component(GameSettings)
    print(f"   游戏时间: {game_time.elapsed}s, 帧时间: {game_time.delta}s")
    print(
        f"   游戏设置: 难度={game_settings.difficulty}, 音效={game_settings.sound_enabled}"
    )

    # 6. 迭代查询结果
    print("\n6. 迭代有生命值的实体:")
    for entity, health in (
        world.query().with_component(Health).iter_entities_with_component(Health)
    ):
        position = world.get_component(entity, Position)
        pos_str = f"({position.x}, {position.y})" if position else "无位置"
        print(
            f"   实体 {entity}: 生命值 {health.current}/{health.maximum}, 位置 {pos_str}"
        )

    # 6.1. 使用 with_all 进行多组件查询
    print("\n6.1 使用 with_all 查询同时拥有位置和速度的实体:")
    movable_with_all = world.query().with_all(Position, Velocity).entities()
    print(
        f"   使用 with_all 找到 {len(movable_with_all)} 个可移动实体: {movable_with_all}"
    )

    # 6.2. 使用 iter_components 迭代多个组件
    print("\n6.2 使用 iter_components 迭代位置和速度组件:")
    for entity, (pos, vel) in (
        world.query().with_all(Position, Velocity).iter_components(Position, Velocity)
    ):
        print(f"   实体 {entity}: 位置({pos.x}, {pos.y}), 速度({vel.dx}, {vel.dy})")

    # 6.3. 使用 iter_components 处理三个组件
    print("\n6.3 使用 iter_components 迭代位置、速度和生命值:")
    for entity, (pos, vel, health) in (
        world.query()
        .with_all(Position, Velocity, Health)
        .iter_components(Position, Velocity, Health)
    ):
        print(
            f"   实体 {entity}: 位置({pos.x}, {pos.y}), 速度({vel.dx}, {vel.dy}), 生命值({health.current}/{health.maximum})"
        )

    # 6.4. 使用 iter_all_components 只获取组件（不要实体ID）
    print("\n6.4 使用 iter_all_components 只迭代组件:")
    for pos, health in (
        world.query().with_all(Position, Health).iter_only_components(Position, Health)
    ):
        print(f"   位置({pos.x}, {pos.y}), 生命值({health.current}/{health.maximum})")

    # 7. 查询统计
    print("\n7. 查询统计:")
    print(f"   总实体数: {world.get_entity_count()}")
    print(f"   有位置的实体数: {world.query().with_component(Position).count()}")
    print(
        f"   可移动实体数: {world.query().with_component(Position).with_component(Velocity).count()}"
    )
    print(
        f"   敌人数量: {world.query().with_component(Damage).without_component(Player).count()}"
    )

    # 8. 查找第一个匹配的实体
    print("\n8. 查找第一个玩家:")
    first_player = world.query().with_component(Player).first()
    if first_player is not None:
        player_comp = world.get_component(first_player, Player)
        print(f"   找到玩家实体 {first_player}: {player_comp.name}")

    # 9. 检查查询结果是否为空
    print("\n9. 检查是否有飞行单位（假设有Flying组件）:")

    @dataclass
    class Flying(Component):
        altitude: float

    has_flying = not world.query().with_component(Flying).is_empty()
    print(f"   是否有飞行单位: {has_flying}")

    # 10. 链式查询的性能测试模拟
    print("\n10. 性能测试模拟 - 创建更多实体:")

    # 创建大量实体进行性能测试
    for i in range(100):
        entity = world.create_entity()
        world.add_component(entity, Position(float(i), float(i * 2)))
        if i % 2 == 0:
            world.add_component(entity, Velocity(1.0, 1.0))
        if i % 3 == 0:
            world.add_component(entity, Health(100, 100))
        if i % 5 == 0:
            world.add_component(entity, Damage(10))

    print(f"   创建了额外的100个实体")
    print(f"   现在总实体数: {world.get_entity_count()}")
    print(f"   有位置的实体数: {world.get_component_count(Position)}")
    print(
        f"   可移动实体数: {world.query().with_component(Position).with_component(Velocity).count()}"
    )

    # 11. 展示查询器的链式特性
    print("\n11. 展示查询器链式特性:")
    query_builder = world.query()
    print(f"   初始查询实体数: {query_builder.count()}")

    query_builder = query_builder.with_component(Position)
    print(f"   添加Position组件后: {query_builder.count()}")

    query_builder = query_builder.with_component(Health)
    print(f"   添加Health组件后: {query_builder.count()}")

    query_builder = query_builder.without_component(Player)
    print(f"   排除Player组件后: {query_builder.count()}")

    # 12. 比较 with_component 链式调用 vs with_all 的性能和简洁性
    print("\n12. 比较不同查询方式:")

    # 方式1: 链式调用 with_component
    result1 = world.query().with_component(Position).with_component(Health).count()
    print(f"   链式调用方式: {result1} 个实体")

    # 方式2: 使用 with_all
    result2 = world.query().with_all(Position, Health).count()
    print(f"   with_all方式: {result2} 个实体")

    # 方式3: 复杂查询比较
    complex1 = (
        world.query()
        .with_component(Position)
        .with_component(Velocity)
        .with_component(Health)
        .without_component(Player)
        .count()
    )
    complex2 = (
        world.query()
        .with_all(Position, Velocity, Health)
        .without_component(Player)
        .count()
    )
    print(f"   复杂查询 - 链式: {complex1} 个实体")
    print(f"   复杂查询 - with_all: {complex2} 个实体")

    # 13. 高效的多组件迭代示例
    print("\n13. 高效的多组件迭代:")

    print("   使用 iter_components 批量处理移动系统:")
    for entity, (pos, vel) in (
        world.query().with_all(Position, Velocity).iter_components(Position, Velocity)
    ):
        # 模拟移动系统的更新逻辑
        new_x = pos.x + vel.dx * 0.016  # 假设delta_time = 0.016
        new_y = pos.y + vel.dy * 0.016
        if entity <= 5:  # 只打印前几个实体避免输出过多
            print(
                f"     实体 {entity}: ({pos.x:.1f}, {pos.y:.1f}) -> ({new_x:.1f}, {new_y:.1f})"
            )

    print("   使用 iter_all_components 进行统计:")
    total_health = 0
    entity_count = 0
    for (health,) in world.query().with_component(Health).iter_only_components(Health):
        total_health += health.current
        entity_count += 1
    if entity_count > 0:
        avg_health = total_health / entity_count
        print(f"     平均生命值: {avg_health:.1f} (总计 {entity_count} 个实体)")


if __name__ == "__main__":
    main()
