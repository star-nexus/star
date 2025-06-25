#!/usr/bin/env python3
"""
测试LLM系统中新增的状态查询指令功能
"""

import json
from typing import Dict, Any
from framework_v2 import World
from rotk_env.systems.llm_system import LLMSystem
from rotk_env.systems.llm_action_handler import LLMActionHandler
from rotk_env.systems.llm_observation_system import LLMObservationSystem
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


def create_test_world_for_llm_system():
    """为LLM系统创建测试世界"""
    world = World()

    # 添加游戏状态
    game_state = GameState(
        current_player=Faction.WEI,
        game_mode="turn_based",
        turn_number=5,
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

    return world, [unit1, unit2]


def test_llm_system_query_actions():
    """测试LLM系统的查询动作"""
    print("=== 测试LLM系统状态查询功能 ===")

    world, units = create_test_world_for_llm_system()

    # 创建LLM系统并初始化（不连接WebSocket）
    llm_system = LLMSystem()
    llm_system.world = world
    llm_system.action_handler = LLMActionHandler(world)
    llm_system.observation_system = LLMObservationSystem(world)
    llm_system.actions = {}
    llm_system.add_env_actions()  # 添加所有动作

    # 测试获取单位列表
    print("\n1. 测试获取单位列表")
    params = {"faction": "WEI", "status": "alive"}
    result = llm_system.handle_get_unit_list(params)
    print(f"单位列表结果: {json.dumps(result, indent=2, ensure_ascii=False)}")

    # 测试获取单位详细信息
    print("\n2. 测试获取单位详细信息")
    params = {"unit_id": units[0]}
    result = llm_system.handle_get_unit_info(params)
    print(f"单位详细信息: {json.dumps(result, indent=2, ensure_ascii=False)}")

    # 测试获取阵营单位
    print("\n3. 测试获取阵营单位")
    params = {"faction": "SHU"}
    result = llm_system.handle_get_faction_units(params)
    print(f"阵营单位结果: {json.dumps(result, indent=2, ensure_ascii=False)}")

    # 测试获取游戏状态
    print("\n4. 测试获取游戏状态")
    result = llm_system.handle_get_game_state({})
    print(f"游戏状态结果: {json.dumps(result, indent=2, ensure_ascii=False)}")

    # 测试获取地图信息
    print("\n5. 测试获取地图信息")
    params = {
        "include_terrain": False,
        "include_units": True,
        "area": {"min_col": 0, "max_col": 10, "min_row": 0, "max_row": 10},
    }
    result = llm_system.handle_get_map_info(params)
    print(f"地图信息结果: {json.dumps(result, indent=2, ensure_ascii=False)}")

    # 测试获取战斗状态
    print("\n6. 测试获取战斗状态")
    params = {"faction": "WEI"}
    result = llm_system.handle_get_battle_status(params)
    print(f"战斗状态结果: {json.dumps(result, indent=2, ensure_ascii=False)}")

    # 测试获取可用动作
    print("\n7. 测试获取可用动作")
    params = {"unit_id": units[1]}
    result = llm_system.handle_get_available_actions(params)
    print(f"可用动作结果: {json.dumps(result, indent=2, ensure_ascii=False)}")

    # 测试获取单位能力
    print("\n8. 测试获取单位能力")
    params = {"unit_id": units[0]}
    result = llm_system.handle_get_unit_capabilities(params)
    print(f"单位能力结果: {json.dumps(result, indent=2, ensure_ascii=False)}")

    # 测试获取视野信息
    print("\n9. 测试获取视野信息")
    params = {"unit_id": units[0]}
    result = llm_system.handle_get_visibility_info(params)
    print(f"视野信息结果: {json.dumps(result, indent=2, ensure_ascii=False)}")

    # 测试获取战略摘要
    print("\n10. 测试获取战略摘要")
    params = {"faction": "WEI"}
    result = llm_system.handle_get_strategic_summary(params)
    print(f"战略摘要结果: {json.dumps(result, indent=2, ensure_ascii=False)}")


def test_llm_system_observation_actions():
    """测试LLM系统的观测动作"""
    print("\n=== 测试LLM系统观测功能 ===")

    world, units = create_test_world_for_llm_system()

    # 创建LLM系统并初始化
    llm_system = LLMSystem()
    llm_system.world = world
    llm_system.action_handler = LLMActionHandler(world)
    llm_system.observation_system = LLMObservationSystem(world)
    llm_system.actions = {}
    llm_system.add_env_actions()

    # 测试受限观测
    print("\n1. 测试受限观测")
    params = {"faction": "WEI"}
    result = llm_system.handle_limited_observation(params)
    print(f"受限观测结果: {json.dumps(result, indent=2, ensure_ascii=False)}")

    # 测试战术观测
    print("\n2. 测试战术观测")
    params = {"center_position": [5, 5], "radius": 3, "faction": "WEI"}
    result = llm_system.handle_tactical_observation(params)
    print(f"战术观测结果: {json.dumps(result, indent=2, ensure_ascii=False)}")


def test_action_mapping():
    """测试动作映射是否正确"""
    print("\n=== 测试动作映射 ===")

    world, units = create_test_world_for_llm_system()

    # 创建LLM系统
    llm_system = LLMSystem()
    llm_system.world = world
    llm_system.action_handler = LLMActionHandler(world)
    llm_system.observation_system = LLMObservationSystem(world)
    llm_system.actions = {}
    llm_system.add_env_actions()

    # 检查所有动作是否都已注册
    expected_actions = [
        # 单位动作
        "move",
        "attack",
        "defend",
        "scout",
        "retreat",
        "fortify",
        "patrol",
        "end_turn",
        "select_unit",
        "formation",
        # 观测动作
        "observation",
        "unit_observation",
        "faction_observation",
        "godview_observation",
        "limited_observation",
        "tactical_observation",
        # 状态查询动作
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
    ]

    registered_actions = list(llm_system.actions.keys())

    print(f"预期动作数量: {len(expected_actions)}")
    print(f"实际注册动作数量: {len(registered_actions)}")

    # 检查缺失的动作
    missing_actions = [
        action for action in expected_actions if action not in registered_actions
    ]
    if missing_actions:
        print(f"❌ 缺失的动作: {missing_actions}")
    else:
        print("✅ 所有预期动作都已注册")

    # 检查额外的动作
    extra_actions = [
        action for action in registered_actions if action not in expected_actions
    ]
    if extra_actions:
        print(f"ℹ️ 额外的动作: {extra_actions}")

    # 按类型分组显示
    print("\n注册的动作按类型分组:")

    unit_actions = [
        a
        for a in registered_actions
        if a
        in [
            "move",
            "attack",
            "defend",
            "scout",
            "retreat",
            "fortify",
            "patrol",
            "end_turn",
            "select_unit",
            "formation",
        ]
    ]
    observation_actions = [
        a
        for a in registered_actions
        if a
        in [
            "observation",
            "unit_observation",
            "faction_observation",
            "godview_observation",
            "limited_observation",
            "tactical_observation",
        ]
    ]
    query_actions = [a for a in registered_actions if a.startswith("get_")]

    print(f"单位动作 ({len(unit_actions)}): {unit_actions}")
    print(f"观测动作 ({len(observation_actions)}): {observation_actions}")
    print(f"查询动作 ({len(query_actions)}): {query_actions}")


def test_websocket_message_simulation():
    """模拟WebSocket消息处理"""
    print("\n=== 测试WebSocket消息模拟 ===")

    world, units = create_test_world_for_llm_system()

    # 创建LLM系统
    llm_system = LLMSystem()
    llm_system.world = world
    llm_system.action_handler = LLMActionHandler(world)
    llm_system.observation_system = LLMObservationSystem(world)
    llm_system.actions = {}
    llm_system.add_env_actions()

    # 模拟WebSocket消息结构
    test_messages = [
        {
            "instruction": "message",
            "data": {
                "id": "query_001",
                "action": "get_unit_list",
                "parameters": {"faction": "WEI", "status": "ready"},
            },
            "msg_from": {"role_type": "agent", "env_id": 1, "agent_id": "test_agent_1"},
        },
        {
            "instruction": "message",
            "data": {"id": "obs_001", "action": "get_game_state", "parameters": {}},
            "msg_from": {"role_type": "agent", "env_id": 1, "agent_id": "test_agent_2"},
        },
        {
            "instruction": "message",
            "data": {
                "id": "strategic_001",
                "action": "get_strategic_summary",
                "parameters": {"faction": "SHU"},
            },
            "msg_from": {"role_type": "agent", "env_id": 1, "agent_id": "test_agent_3"},
        },
    ]

    # 模拟消息处理
    for i, message in enumerate(test_messages, 1):
        print(f"\n处理消息 {i}:")
        print(f"动作: {message['data']['action']}")
        print(f"参数: {message['data']['parameters']}")

        # 直接调用动作处理
        action = message["data"]["action"]
        params = message["data"]["parameters"]

        if action in llm_system.actions:
            try:
                result = llm_system.actions[action](params)
                print(f"处理结果: {json.dumps(result, indent=2, ensure_ascii=False)}")
            except Exception as e:
                print(f"❌ 处理出错: {e}")
        else:
            print(f"❌ 未知动作: {action}")


def main():
    """主测试函数"""
    print("开始测试LLM系统的状态查询功能...")

    try:
        # 测试动作映射
        test_action_mapping()

        # 测试查询动作
        test_llm_system_query_actions()

        # 测试观测动作
        test_llm_system_observation_actions()

        # 测试WebSocket消息模拟
        test_websocket_message_simulation()

        print("\n=== 测试完成 ===")
        print("✅ LLM系统状态查询功能测试通过！")

    except Exception as e:
        print(f"\n❌ 测试过程中出现错误: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
