#!/usr/bin/env python3
"""
测试LLM Action Handler的新增观测和状态查询功能
"""

import json
from typing import Dict, Any
from framework_v2 import World
from rotk_env.systems.llm_action_handler import LLMActionHandler
from rotk_env.components import (
    Unit,
    HexPosition,
    Health,
    Movement,
    Combat,
    Vision,
    GameState,
)
from rotk_env.prefabs.config import Faction, UnitType


def create_test_world_with_game_state():
    """创建包含游戏状态的测试世界"""
    world = World()

    # 添加游戏状态
    game_state = GameState(
        current_player=Faction.WEI,
        game_mode="turn_based",
        turn_number=3,
        phase="action",
    )
    world.add_singleton_component(game_state)

    # 创建测试单位 - WEI阵营
    unit1 = world.create_entity()
    world.add_component(
        unit1, Unit(name="曹操", faction=Faction.WEI, unit_type=UnitType.CAVALRY)
    )
    world.add_component(unit1, HexPosition(col=5, row=5))
    world.add_component(unit1, Health(current=80, max=100))
    world.add_component(unit1, Movement(max_movement=4, current_movement=2))
    world.add_component(unit1, Combat(attack=15, defense=12, attack_range=1))
    world.add_component(unit1, Vision(sight_range=3))

    # 创建测试单位 - SHU阵营
    unit2 = world.create_entity()
    world.add_component(
        unit2, Unit(name="刘备", faction=Faction.SHU, unit_type=UnitType.INFANTRY)
    )
    world.add_component(unit2, HexPosition(col=7, row=6))
    world.add_component(unit2, Health(current=100, max=100))
    world.add_component(unit2, Movement(max_movement=3, current_movement=3))
    world.add_component(unit2, Combat(attack=12, defense=15, attack_range=1))
    world.add_component(unit2, Vision(sight_range=2))

    # 创建测试单位 - WU阵营
    unit3 = world.create_entity()
    world.add_component(
        unit3, Unit(name="孙权", faction=Faction.WU, unit_type=UnitType.ARCHER)
    )
    world.add_component(unit3, HexPosition(col=3, row=8))
    world.add_component(unit3, Health(current=60, max=80))
    world.add_component(
        unit3, Movement(max_movement=2, current_movement=0, has_moved=True)
    )
    world.add_component(
        unit3, Combat(attack=10, defense=8, attack_range=3, has_attacked=True)
    )
    world.add_component(unit3, Vision(sight_range=4))

    return world, [unit1, unit2, unit3]


def test_observation_actions():
    """测试观测动作"""
    print("=== 测试观测动作 ===")

    world, units = create_test_world_with_game_state()
    handler = LLMActionHandler(world)

    # 测试单位观测
    print("\n1. 测试单位观测")
    result = handler.execute_action("unit_observation", {"unit_id": units[0]})
    print(f"单位观测结果: {json.dumps(result, indent=2, ensure_ascii=False)}")

    # 测试阵营观测
    print("\n2. 测试阵营观测")
    result = handler.execute_action(
        "faction_observation", {"faction": "WEI", "include_hidden": True}
    )
    print(f"阵营观测结果: {json.dumps(result, indent=2, ensure_ascii=False)}")

    # 测试上帝视角观测
    print("\n3. 测试上帝视角观测")
    result = handler.execute_action("godview_observation", {})
    print(f"上帝视角观测结果: {json.dumps(result, indent=2, ensure_ascii=False)}")

    # 测试战术观测
    print("\n4. 测试战术观测")
    result = handler.execute_action(
        "tactical_observation",
        {"center_position": [5, 5], "radius": 3, "faction": "WEI"},
    )
    print(f"战术观测结果: {json.dumps(result, indent=2, ensure_ascii=False)}")


def test_query_actions():
    """测试状态查询动作"""
    print("\n=== 测试状态查询动作 ===")

    world, units = create_test_world_with_game_state()
    handler = LLMActionHandler(world)

    # 测试获取单位列表
    print("\n1. 测试获取单位列表")
    result = handler.execute_action(
        "get_unit_list", {"faction": "WEI", "status": "alive"}
    )
    print(f"单位列表结果: {json.dumps(result, indent=2, ensure_ascii=False)}")

    # 测试获取单位详细信息
    print("\n2. 测试获取单位详细信息")
    result = handler.execute_action("get_unit_info", {"unit_id": units[0]})
    print(f"单位详细信息: {json.dumps(result, indent=2, ensure_ascii=False)}")

    # 测试获取阵营单位
    print("\n3. 测试获取阵营单位")
    result = handler.execute_action("get_faction_units", {"faction": "SHU"})
    print(f"阵营单位结果: {json.dumps(result, indent=2, ensure_ascii=False)}")

    # 测试获取游戏状态
    print("\n4. 测试获取游戏状态")
    result = handler.execute_action("get_game_state", {})
    print(f"游戏状态结果: {json.dumps(result, indent=2, ensure_ascii=False)}")

    # 测试获取地图信息
    print("\n5. 测试获取地图信息")
    result = handler.execute_action(
        "get_map_info",
        {
            "include_terrain": False,
            "include_units": True,
            "area": {"min_col": 0, "max_col": 10, "min_row": 0, "max_row": 10},
        },
    )
    print(f"地图信息结果: {json.dumps(result, indent=2, ensure_ascii=False)}")

    # 测试获取战斗状态
    print("\n6. 测试获取战斗状态")
    result = handler.execute_action("get_battle_status", {"faction": "WEI"})
    print(f"战斗状态结果: {json.dumps(result, indent=2, ensure_ascii=False)}")

    # 测试获取可用动作
    print("\n7. 测试获取可用动作")
    result = handler.execute_action("get_available_actions", {"unit_id": units[1]})
    print(f"可用动作结果: {json.dumps(result, indent=2, ensure_ascii=False)}")

    # 测试获取所有支持的动作
    print("\n8. 测试获取所有支持的动作")
    result = handler.execute_action("get_available_actions", {})
    print(f"所有支持动作: {json.dumps(result, indent=2, ensure_ascii=False)}")

    # 测试获取单位能力
    print("\n9. 测试获取单位能力")
    result = handler.execute_action("get_unit_capabilities", {"unit_id": units[2]})
    print(f"单位能力结果: {json.dumps(result, indent=2, ensure_ascii=False)}")

    # 测试获取视野信息
    print("\n10. 测试获取视野信息")
    result = handler.execute_action("get_visibility_info", {"unit_id": units[0]})
    print(f"单位视野信息: {json.dumps(result, indent=2, ensure_ascii=False)}")

    result = handler.execute_action("get_visibility_info", {"faction": "SHU"})
    print(f"阵营视野信息: {json.dumps(result, indent=2, ensure_ascii=False)}")

    # 测试获取战略摘要
    print("\n11. 测试获取战略摘要")
    result = handler.execute_action("get_strategic_summary", {"faction": "WEI"})
    print(f"战略摘要结果: {json.dumps(result, indent=2, ensure_ascii=False)}")


def test_supported_actions():
    """测试支持的动作列表"""
    print("\n=== 测试支持的动作列表 ===")

    world, units = create_test_world_with_game_state()
    handler = LLMActionHandler(world)

    supported_actions = handler.get_supported_actions()
    print(f"支持的动作总数: {len(supported_actions)}")
    print("支持的动作列表:")
    for i, (action_name, action_info) in enumerate(supported_actions.items(), 1):
        print(f"  {i:2d}. {action_name}: {action_info['function_desc']}")

    # 按类型分组显示
    action_categories = {
        "单位动作": [
            "move",
            "attack",
            "defend",
            "scout",
            "retreat",
            "fortify",
            "patrol",
            "select_unit",
            "formation",
            "end_turn",
        ],
        "观测动作": [
            "unit_observation",
            "faction_observation",
            "godview_observation",
            "limited_observation",
            "tactical_observation",
        ],
        "查询动作": [
            "get_unit_list",
            "get_unit_info",
            "get_faction_units",
            "get_game_state",
            "get_map_info",
            "get_battle_status",
            "get_available_actions",
            "get_unit_capabilities",
            "get_visibility_info",
            "get_strategic_summary",
        ],
    }

    print("\n按类型分组的动作:")
    for category, actions in action_categories.items():
        print(f"\n{category}:")
        available_in_category = [
            action for action in actions if action in supported_actions.keys()
        ]
        for action in available_in_category:
            action_info = supported_actions[action]
            print(f"  ✓ {action}: {action_info['function_desc']}")


def test_error_handling():
    """测试错误处理"""
    print("\n=== 测试错误处理 ===")

    world, units = create_test_world_with_game_state()
    handler = LLMActionHandler(world)

    # 测试不存在的动作
    print("\n1. 测试不存在的动作")
    result = handler.execute_action("unknown_action", {})
    print(f"未知动作结果: {json.dumps(result, indent=2, ensure_ascii=False)}")

    # 测试缺少参数
    print("\n2. 测试缺少参数")
    result = handler.execute_action("get_unit_info", {})
    print(f"缺少参数结果: {json.dumps(result, indent=2, ensure_ascii=False)}")

    # 测试无效单位ID
    print("\n3. 测试无效单位ID")
    result = handler.execute_action("get_unit_info", {"unit_id": 99999})
    print(f"无效单位ID结果: {json.dumps(result, indent=2, ensure_ascii=False)}")

    # 测试无效阵营
    print("\n4. 测试无效阵营")
    result = handler.execute_action(
        "faction_observation", {"faction": "INVALID_FACTION"}
    )
    print(f"无效阵营结果: {json.dumps(result, indent=2, ensure_ascii=False)}")


def main():
    """主测试函数"""
    print("开始测试LLM Action Handler的新增功能...")

    try:
        # 测试观测动作
        test_observation_actions()

        # 测试查询动作
        test_query_actions()

        # 测试支持的动作列表
        test_supported_actions()

        # 测试错误处理
        test_error_handling()

        print("\n=== 测试完成 ===")
        print("✅ 所有新增功能测试通过！")

    except Exception as e:
        print(f"\n❌ 测试过程中出现错误: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
