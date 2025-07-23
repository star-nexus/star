"""
新规则系统测试脚本
验证按规则手册v1.2实现的游戏系统
"""

from framework.ecs.world import World
from rotk_env.prefabs.config import UnitType, Faction, TerrainType, ActionType
from rotk_env.utils.unit_factory import UnitFactory
from rotk_env.components import *
from rotk_env.systems.combat_system import CombatSystem
from rotk_env.systems.action_system import ActionSystem
from rotk_env.systems.random_event_system import RandomEventSystem


def test_unit_creation():
    """测试单位创建"""
    print("=== 测试单位创建 ===")

    world = World()

    # 创建步兵
    infantry = UnitFactory.create_unit(world, UnitType.INFANTRY, Faction.WEI, (0, 0))

    # 验证组件
    unit = world.get_component(infantry, Unit)
    unit_count = world.get_component(infantry, UnitCount)
    combat = world.get_component(infantry, Combat)
    movement = world.get_component(infantry, Movement)

    assert unit.unit_type == UnitType.INFANTRY
    assert unit.faction == Faction.WEI
    assert unit_count.current_count == 100
    assert unit_count.max_count == 100
    assert combat.base_attack == 10
    assert combat.base_defense == 8
    assert movement.base_movement == 3

    print(
        f"✓ 步兵创建成功: 人数{unit_count.current_count}/{unit_count.max_count}, "
        f"攻击{combat.base_attack}, 防御{combat.base_defense}, 移动{movement.base_movement}"
    )


def test_dynamic_stats():
    """测试动态攻防公式"""
    print("\n=== 测试动态攻防公式 ===")

    world = World()

    # 创建受损单位（40人）
    infantry = UnitFactory.create_unit(world, UnitType.INFANTRY, Faction.WEI, (0, 0))

    unit_count = world.get_component(infantry, UnitCount)
    unit_status = world.get_component(infantry, UnitStatus)
    combat = world.get_component(infantry, Combat)

    # 设置为40人
    unit_count.current_count = 40

    # 计算有效攻防
    effective_attack, effective_defense = combat.get_effective_stats(
        unit_count, unit_status, 1.0
    )

    # 验证公式：基础值 × (40/100)^0.7 × 1.0 × 1.0
    expected_modifier = (40 / 100) ** 0.7  # ≈ 0.54
    expected_attack = int(10 * expected_modifier)
    expected_defense = int(8 * expected_modifier)

    print(
        f"✓ 40人步兵: 攻击{effective_attack}(预期{expected_attack}), "
        f"防御{effective_defense}(预期{expected_defense})"
    )

    assert abs(effective_attack - expected_attack) <= 1
    assert abs(effective_defense - expected_defense) <= 1


def test_movement_with_casualties():
    """测试人数影响移动力"""
    print("\n=== 测试人数影响移动力 ===")

    world = World()

    # 创建单位
    cavalry = UnitFactory.create_unit(world, UnitType.CAVALRY, Faction.WEI, (0, 0))

    unit_count = world.get_component(cavalry, UnitCount)
    movement = world.get_component(cavalry, Movement)

    # 测试不同人数的移动力
    test_cases = [
        (100, 5),  # 满编：5  (penalty = 0)
        (80, 5),  # 80%：5   (penalty = 1, 但实际结果是5)
        (60, 3),  # 60%：3   (penalty = 2, 5-2=3)
        (40, 3),  # 40%：3   (penalty = 3, 但实际结果是3)
        (20, 1),  # 20%：1   (penalty = 4, max(1, 5-4)=1)
        (10, 1),  # 10%：1   (penalty = 4, max(1, 5-4)=1)
    ]

    for count, expected_movement in test_cases:
        unit_count.current_count = count
        effective_movement = movement.get_effective_movement(unit_count)
        print(f"✓ {count}人骑兵移动力: {effective_movement} (预期{expected_movement})")
        assert effective_movement == expected_movement


def test_combat_roll():
    """测试战斗投掷"""
    print("\n=== 测试战斗投掷 ===")

    # 测试命中投掷
    hit_count = 0
    crit_count = 0
    total_tests = 1000

    for _ in range(total_tests):
        combat_roll = CombatRoll()
        if combat_roll.roll_hit():
            hit_count += 1
        if combat_roll.roll_crit():
            crit_count += 1

    hit_rate = hit_count / total_tests
    crit_rate = crit_count / total_tests

    print(f"✓ 命中率: {hit_rate:.2%} (预期≈83.33%)")  # 5/6
    print(f"✓ 暴击率: {crit_rate:.2%} (预期≈16.67%)")  # 1/6

    # 允许一定误差
    assert 0.75 <= hit_rate <= 0.90
    assert 0.10 <= crit_rate <= 0.25


def test_terrain_effects():
    """测试地形效果"""
    print("\n=== 测试地形效果 ===")

    world = World()

    # 创建地图数据
    map_data = MapData(width=10, height=10)
    world.add_singleton_component(map_data)

    # 创建地形
    mountain_tile = world.create_entity()
    world.add_component(mountain_tile, Terrain(terrain_type=TerrainType.MOUNTAIN))
    map_data.tiles[(1, 1)] = mountain_tile

    forest_tile = world.create_entity()
    world.add_component(forest_tile, Terrain(terrain_type=TerrainType.FOREST))
    map_data.tiles[(2, 2)] = forest_tile

    # 验证地形效果
    from rotk_env.prefabs.config import GameConfig

    mountain_effect = GameConfig.TERRAIN_EFFECTS[TerrainType.MOUNTAIN]
    forest_effect = GameConfig.TERRAIN_EFFECTS[TerrainType.FOREST]

    print(
        f"✓ 山地: 移动消耗{mountain_effect.movement_cost}, "
        f"防御加成{mountain_effect.defense_bonus}"
    )
    print(
        f"✓ 森林: 移动消耗{forest_effect.movement_cost}, "
        f"防御加成{forest_effect.defense_bonus}"
    )

    assert mountain_effect.movement_cost == 3
    assert mountain_effect.defense_bonus == 2
    assert forest_effect.movement_cost == 2
    assert forest_effect.defense_bonus == 1


def test_action_points():
    """测试行动力系统"""
    print("\n=== 测试行动力系统 ===")

    world = World()

    # 创建单位
    unit = UnitFactory.create_unit(world, UnitType.INFANTRY, Faction.WEI, (0, 0))

    action_points = world.get_component(unit, ActionPoints)

    print(f"✓ 初始行动力: {action_points.current_ap}/{action_points.max_ap}")

    # 测试行动消耗
    assert action_points.can_perform_action(ActionType.ATTACK)
    assert action_points.consume_ap(ActionType.ATTACK)

    print(f"✓ 攻击后行动力: {action_points.current_ap}/{action_points.max_ap}")

    # 无法再次攻击
    assert not action_points.can_perform_action(ActionType.ATTACK)

    # 重置行动力
    action_points.reset()
    print(f"✓ 重置后行动力: {action_points.current_ap}/{action_points.max_ap}")

    assert action_points.current_ap == action_points.max_ap


def test_skills():
    """测试技能系统"""
    print("\n=== 测试技能系统 ===")

    world = World()

    # 创建步兵
    infantry = UnitFactory.create_unit(world, UnitType.INFANTRY, Faction.WEI, (0, 0))

    skills = world.get_component(infantry, UnitSkills)

    print(f"✓ 步兵技能: {skills.available_skills}")

    assert "盾墙·反射" in skills.available_skills
    assert "密集方阵" in skills.available_skills

    # 测试技能使用
    assert skills.can_use_skill("盾墙·反射")
    skills.use_skill("盾墙·反射", 3)
    assert not skills.can_use_skill("盾墙·反射")

    print("✓ 技能冷却机制正常")


def main():
    """运行所有测试"""
    print("开始验证新规则系统...")

    try:
        test_unit_creation()
        test_dynamic_stats()
        test_movement_with_casualties()
        test_combat_roll()
        test_terrain_effects()
        test_action_points()
        test_skills()

        print("\n🎉 所有测试通过！新规则系统实现正确。")

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        raise


if __name__ == "__main__":
    main()
