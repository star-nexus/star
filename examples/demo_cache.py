"""
ECS 缓存机制测试示例

展示如何使用新的缓存功能来提高查询性能
"""

import sys
import os
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Dict

from dataclasses import dataclass
from framework_v2 import World, Component, SingletonComponent


# 定义示例组件
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
    name: str


def create_test_entities(world: World, count: int):
    """创建测试实体"""
    entities = []
    for i in range(count):
        entity = world.create_entity()
        entities.append(entity)

        # 所有实体都有位置
        world.add_component(entity, Position(float(i * 10), float(i * 20)))

        # 50% 有速度
        if i % 2 == 0:
            world.add_component(entity, Velocity(1.0, 0.5))

        # 33% 有生命值
        if i % 3 == 0:
            world.add_component(entity, Health(100, 100))

        # 20% 有伤害
        if i % 5 == 0:
            world.add_component(entity, Damage(25))

        # 1个玩家
        if i == 0:
            world.add_component(entity, Player("TestPlayer"))

    return entities


def performance_test():
    """性能测试"""
    print("=== ECS 缓存机制性能测试 ===\n")

    world = World()

    # 创建大量实体进行测试
    entity_count = 5000
    print(f"创建 {entity_count} 个测试实体...")
    entities = create_test_entities(world, entity_count)
    print(f"创建完成。总实体数: {world.get_entity_count()}")

    # 查询1：有位置和速度的实体
    print("\n1. 测试查询缓存机制:")

    # 第一次查询（应该是缓存未命中）
    start_time = time.time()
    query1 = world.query().with_all(Position, Velocity)
    result1 = query1.entities()
    first_query_time = time.time() - start_time

    print(f"   第一次查询 - 时间: {first_query_time:.6f}s, 结果数: {len(result1)}")
    print(f"   缓存信息: {query1.get_cache_info()}")

    # 第二次相同查询（应该命中缓存）
    start_time = time.time()
    query2 = world.query().with_all(Position, Velocity)
    result2 = query2.entities()
    second_query_time = time.time() - start_time

    print(f"   第二次相同查询 - 时间: {second_query_time:.6f}s, 结果数: {len(result2)}")
    print(f"   缓存信息: {query2.get_cache_info()}")

    # 验证结果一致性
    assert result1 == result2, "缓存结果应该与原始计算结果相同"

    # 性能提升比率
    if first_query_time > 0:
        speedup = (
            first_query_time / second_query_time
            if second_query_time > 0
            else float("inf")
        )
        print(f"   性能提升: {speedup:.2f}x")

    # 查看缓存统计
    cache_stats = world.get_cache_stats()
    print(f"\n   世界缓存统计: {cache_stats}")

    print("\n2. 测试缓存失效机制:")

    # 添加一个新组件，应该使相关缓存失效
    test_entity = entities[10]
    world.add_component(test_entity, Health(50, 50))

    # 再次执行查询
    start_time = time.time()
    query3 = world.query().with_all(Position, Velocity)
    result3 = query3.entities()
    third_query_time = time.time() - start_time

    print(f"   添加组件后查询 - 时间: {third_query_time:.6f}s, 结果数: {len(result3)}")
    print(f"   缓存信息: {query3.get_cache_info()}")

    # 缓存统计应该显示新的未命中
    cache_stats = world.get_cache_stats()
    print(f"   更新后的缓存统计: {cache_stats}")

    print("\n3. 测试多种查询模式:")

    queries_to_test = [
        ("有位置", lambda w: w.query().with_component(Position)),
        ("可移动", lambda w: w.query().with_all(Position, Velocity)),
        ("有战斗力", lambda w: w.query().with_all(Health, Damage)),
        ("玩家", lambda w: w.query().with_component(Player)),
        (
            "非玩家战斗单位",
            lambda w: w.query().with_all(Health, Damage).without_component(Player),
        ),
    ]

    for desc, query_func in queries_to_test:
        # 第一次查询
        start_time = time.time()
        query = query_func(world)
        count = query.count()
        first_time = time.time() - start_time

        # 第二次查询（缓存）
        start_time = time.time()
        query = query_func(world)
        count2 = query.count()
        second_time = time.time() - start_time

        speedup = first_time / second_time if second_time > 0 else float("inf")
        print(
            f"   {desc}: {count} 个实体, 首次: {first_time:.6f}s, 缓存: {second_time:.6f}s, 提升: {speedup:.2f}x"
        )

    print(f"\n3.5 benchmark_queries")
    benchmark_queries(world)

    print(f"\n4. 最终缓存统计:")
    final_stats = world.get_cache_stats()
    print(f"   {final_stats}")


def cache_correctness_test():
    """缓存正确性测试"""
    print("\n=== 缓存正确性测试 ===\n")

    world = World()

    # 创建一些实体
    entity1 = world.create_entity()
    world.add_component(entity1, Position(10, 20))
    world.add_component(entity1, Velocity(1, 0))

    entity2 = world.create_entity()
    world.add_component(entity2, Position(30, 40))

    entity3 = world.create_entity()
    world.add_component(entity3, Position(50, 60))
    world.add_component(entity3, Velocity(0, 1))
    world.add_component(entity3, Health(100, 100))

    print("创建了3个实体:")
    print(f"  实体1: Position + Velocity")
    print(f"  实体2: Position")
    print(f"  实体3: Position + Velocity + Health")

    # 测试1：基本查询
    print("\n1. 基本查询测试:")
    movable_entities = world.query().with_all(Position, Velocity).entities()
    print(
        f"   可移动实体: {sorted(movable_entities)} (应该是 {sorted([entity1, entity3])})"
    )
    assert movable_entities == {entity1, entity3}

    # 测试2：添加组件后缓存失效
    print("\n2. 添加组件测试:")
    world.add_component(entity2, Velocity(2, 2))
    movable_entities_after = world.query().with_all(Position, Velocity).entities()
    print(
        f"   添加速度组件后可移动实体: {sorted(movable_entities_after)} (应该是 {sorted([entity1, entity2, entity3])})"
    )
    assert movable_entities_after == {entity1, entity2, entity3}

    # 测试3：移除组件后缓存失效
    print("\n3. 移除组件测试:")
    world.remove_component(entity1, Velocity)
    movable_entities_after_remove = (
        world.query().with_all(Position, Velocity).entities()
    )
    print(
        f"   移除速度组件后可移动实体: {sorted(movable_entities_after_remove)} (应该是 {sorted([entity2, entity3])})"
    )
    assert movable_entities_after_remove == {entity2, entity3}

    # 测试4：销毁实体后缓存失效
    print("\n4. 销毁实体测试:")
    world.destroy_entity(entity2)
    movable_entities_after_destroy = (
        world.query().with_all(Position, Velocity).entities()
    )
    print(
        f"   销毁实体后可移动实体: {sorted(movable_entities_after_destroy)} (应该是 {sorted([entity3])})"
    )
    assert movable_entities_after_destroy == {entity3}

    print("\n✅ 所有缓存正确性测试通过!")


def cache_management_test():
    """缓存管理测试"""
    print("\n=== 缓存管理测试 ===\n")

    world = World()

    # 测试缓存大小限制
    print("1. 测试缓存大小限制:")
    world.set_max_cache_size(5)

    # 创建多个不同的查询来填满缓存
    entities = create_test_entities(world, 100)

    # 执行多个不同的查询
    queries = [
        world.query().with_component(Position),
        world.query().with_component(Velocity),
        world.query().with_component(Health),
        world.query().with_component(Damage),
        world.query().with_all(Position, Velocity),
        world.query().with_all(Position, Health),
        world.query().with_all(Velocity, Health),
        world.query().with_all(Position, Velocity, Health),
    ]

    for i, query in enumerate(queries):
        count = query.count()
        print(f"   查询 {i+1}: {count} 个实体")

    stats = world.get_cache_stats()
    print(f"   缓存统计: {stats}")
    print(f"   缓存应该被限制在 {world._max_cache_size} 个条目以内")

    # 测试手动清空缓存
    print("\n2. 测试手动清空缓存:")
    world.clear_cache()
    stats_after_clear = world.get_cache_stats()
    print(f"   清空后缓存统计: {stats_after_clear}")
    assert stats_after_clear["cache_size"] == 0, "缓存应该为空"

    print("\n✅ 缓存管理测试通过!")


class PerformanceTimer:
    """性能计时器"""

    def __init__(self):
        self.timers: Dict[str, float] = {}

    def start(self, name: str) -> None:
        """开始计时"""
        self.timers[name] = time.time()

    def end(self, name: str) -> float:
        """结束计时并返回耗时"""
        if name not in self.timers:
            return 0.0
        elapsed = time.time() - self.timers[name]
        del self.timers[name]
        return elapsed


def benchmark_queries(world: World = None, iterations: int = 1000) -> None:
    """基准测试查询性能"""
    w = world
    timer = PerformanceTimer()

    print(f"=== 查询性能基准测试 ({iterations} 次迭代) ===")

    # 测试单组件查询
    timer.start("single_query")
    for _ in range(iterations):
        list(w.query().with_all(Position).entities())
    single_time = timer.end("single_query")
    # 测试多组件查询
    timer.start("multi_query")
    for _ in range(iterations):
        list(w.query().with_all(Position, Velocity).entities())
    multi_time = timer.end("multi_query")
    # 测试组件获取
    timer.start("component_access")
    for _ in range(iterations):
        for entity in w.query().with_all(Position).entities():
            w.get_component(entity, Position)
    access_time = timer.end("component_access")
    print(f"单组件查询: {single_time:.4f}s ({single_time/iterations*1000:.2f}ms/iter)")
    print(f"多组件查询: {multi_time:.4f}s ({multi_time/iterations*1000:.2f}ms/iter)")
    print(f"组件访问: {access_time:.4f}s ({access_time/iterations*1000:.2f}ms/iter)")


def main():
    """主测试函数"""
    try:
        performance_test()
        cache_correctness_test()
        cache_management_test()
        print("\n🎉 所有测试通过！缓存机制工作正常。")
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
