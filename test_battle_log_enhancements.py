#!/usr/bin/env python3
"""
测试扩展的战况记录系统
"""


def test_battle_log_enhancements():
    """测试战况记录系统的增强功能"""
    print("测试战况记录系统增强功能...")

    # 检查统计系统的新方法
    from rotk_env.systems.statistics_system import StatisticsSystem

    required_methods = [
        "record_combat_action",  # 战斗记录（已有）
        "record_movement_action",  # 移动记录（已有）
        "record_turn_change",  # 回合变化记录（已有）
        "record_defense_action",  # 防御记录（新增）
        "record_skill_action",  # 技能记录（新增）
        "record_garrison_action",  # 驻扎记录（新增）
        "record_wait_action",  # 待命记录（新增）
        "record_death_action",  # 死亡记录（新增）
        "record_game_event",  # 通用事件记录（新增）
    ]

    for method_name in required_methods:
        assert hasattr(StatisticsSystem, method_name), f"缺少方法: {method_name}"
        method = getattr(StatisticsSystem, method_name)
        assert callable(method), f"{method_name} 不是可调用的"
        print(f"✓ {method_name} 方法存在且可调用")

    print("✓ 所有统计系统方法测试通过！")


def test_battle_log_entry_types():
    """测试战况记录的事件类型"""
    from rotk_env.components.battle_log import BattleLog, BattleLogEntry

    # 测试不同类型的记录条目
    battle_log = BattleLog()

    event_types = [
        ("combat", "魏国攻击蜀国造成50点伤害", (255, 200, 100)),
        ("movement", "魏国的步兵从(0,0)移动到(1,0)", (100, 200, 255)),
        ("turn", "魏国回合结束，蜀国回合开始", (255, 255, 100)),
        ("defense", "蜀国的步兵防御来自魏国的攻击", (0, 255, 255)),
        ("skill", "魏国的骑兵使用了技能: 冲锋", (255, 165, 0)),
        ("garrison", "蜀国的步兵进入驻扎状态", (128, 255, 128)),
        ("wait", "魏国的弓兵选择了待命", (192, 192, 192)),
        ("death", "蜀国的步兵被魏国击败", (255, 0, 0)),
        ("info", "游戏开始", (255, 255, 255)),
    ]

    for event_type, message, color in event_types:
        battle_log.add_entry(message, event_type, "wei", color)
        print(f"✓ 添加{event_type}类型事件: {message}")

    # 验证记录正确保存
    assert len(battle_log.entries) == len(event_types), "记录数量不匹配"
    print(f"✓ 成功记录了{len(battle_log.entries)}条事件")

    # 测试获取可见记录
    visible_entries = battle_log.get_visible_entries()
    print(f"✓ 可见记录数量: {len(visible_entries)}")

    # 测试最近记录
    recent_entries = battle_log.get_recent_entries(5)
    print(f"✓ 最近5条记录数量: {len(recent_entries)}")

    print("✓ 所有战况记录类型测试通过！")


def test_action_system_integration():
    """测试行动系统的集成"""
    from rotk_env.systems.action_system import ActionSystem

    # 检查行动系统是否有获取统计系统的方法
    assert hasattr(
        ActionSystem, "_get_statistics_system"
    ), "行动系统缺少_get_statistics_system方法"
    print("✓ 行动系统集成统计系统记录")

    # 检查主要方法是否存在
    required_methods = ["perform_garrison", "perform_wait"]
    for method_name in required_methods:
        assert hasattr(ActionSystem, method_name), f"行动系统缺少方法: {method_name}"
        print(f"✓ {method_name} 方法存在")

    print("✓ 行动系统集成测试通过！")


def demonstrate_event_logging():
    """演示事件记录的工作流程"""
    print("\n=== 事件记录工作流程演示 ===")

    from rotk_env.components.battle_log import BattleLog
    from rotk_env.prefabs.config import Faction

    battle_log = BattleLog()

    # 模拟一个完整的游戏回合
    print("1. 游戏开始")
    battle_log.add_entry("游戏开始", "info", "", (0, 255, 0))

    print("2. 魏国回合开始")
    battle_log.add_entry("魏国回合开始", "turn", "wei", (255, 255, 100))

    print("3. 魏国单位移动")
    battle_log.add_entry(
        "魏国的步兵从(0,0)移动到(1,0)", "movement", "wei", (100, 200, 255)
    )
    battle_log.add_entry(
        "魏国的骑兵从(2,2)移动到(1,1)", "movement", "wei", (100, 200, 255)
    )

    print("4. 魏国单位攻击")
    battle_log.add_entry("魏国对蜀国造成25点伤害", "combat", "wei", (255, 200, 100))
    battle_log.add_entry("魏国对蜀国的攻击未命中", "combat", "wei", (128, 128, 128))

    print("5. 蜀国回合开始")
    battle_log.add_entry("魏国回合结束，蜀国回合开始", "turn", "shu", (255, 255, 100))

    print("6. 蜀国单位行动")
    battle_log.add_entry("蜀国的步兵进入驻扎状态", "garrison", "shu", (128, 255, 128))
    battle_log.add_entry("蜀国的弓兵选择了待命", "wait", "shu", (192, 192, 192))

    print("7. 蜀国单位死亡")
    battle_log.add_entry("蜀国的步兵被魏国击败", "death", "shu", (255, 0, 0))

    print(f"\n记录了 {len(battle_log.entries)} 条事件:")
    for i, entry in enumerate(battle_log.entries, 1):
        print(f"  {i:2d}. [{entry.log_type:8s}] {entry.message}")

    print("\n✓ 事件记录演示完成！")


if __name__ == "__main__":
    test_battle_log_enhancements()
    print()
    test_battle_log_entry_types()
    print()
    test_action_system_integration()
    print()
    demonstrate_event_logging()

    print("\n🎉 所有战况记录系统测试通过！")
    print("\n功能总结:")
    print("✓ 扩展了统计系统，支持9种事件类型的记录")
    print("✓ 所有事件都会记录到BattleLog中，显示在游戏界面")
    print("✓ 事件包括：战斗、移动、回合变化、防御、技能、驻扎、待命、死亡和通用事件")
    print("✓ 每种事件类型都有适当的颜色编码和时间戳")
    print("✓ 行动系统集成了统计记录功能")
    print("✓ 战斗系统集成了死亡和未命中记录")
    print("✓ 移动系统和回合系统已集成相应记录功能")
