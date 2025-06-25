"""
LLM系统功能测试示例
展示如何使用新的动作处理器和观测系统
"""

import json
from typing import Dict, Any
from framework_v2 import World
from rotk_env.systems import LLMSystem, LLMActionHandler, LLMObservationSystem
from rotk_env.components import Unit, HexPosition, Health, Movement, Combat, Vision
from rotk_env.prefabs.config import Faction, UnitType


def create_test_world():
    """创建测试用的游戏世界"""
    world = World()

    # 创建测试单位1 - 关羽 (SHU阵营)
    unit1 = world.create_entity()
    world.add_component(
        unit1, Unit(name="关羽", faction=Faction.SHU, unit_type=UnitType.CAVALRY)
    )
    world.add_component(unit1, HexPosition(col=5, row=5))
    world.add_component(unit1, Health(current=100, max=100))
    world.add_component(unit1, Movement(max_movement=4, current_movement=4))
    world.add_component(unit1, Combat(attack=15, defense=12, attack_range=1))
    world.add_component(unit1, Vision(sight_range=3))

    # 创建测试单位2 - 曹操 (WEI阵营)
    unit2 = world.create_entity()
    world.add_component(
        unit2, Unit(name="曹操", faction=Faction.WEI, unit_type=UnitType.INFANTRY)
    )
    world.add_component(unit2, HexPosition(col=7, row=6))
    world.add_component(unit2, Health(current=80, max=100))
    world.add_component(unit2, Movement(max_movement=3, current_movement=3))
    world.add_component(unit2, Combat(attack=12, defense=15, attack_range=1))
    world.add_component(unit2, Vision(sight_range=2))

    return world, unit1, unit2


def test_action_handler():
    """测试动作处理器"""
    print("=== 测试动作处理器 ===")

    world, unit1, unit2 = create_test_world()
    action_handler = LLMActionHandler(world)

    # 测试移动动作
    print("\n1. 测试移动动作")
    move_params = {"unit_id": unit1, "target_position": [6, 5]}
    result = action_handler.execute_action("move", move_params)
    print(f"移动结果: {json.dumps(result, indent=2, ensure_ascii=False)}")

    # 测试攻击动作
    print("\n2. 测试攻击动作")
    attack_params = {"attacker_id": unit1, "target_id": unit2}
    result = action_handler.execute_action("attack", attack_params)
    print(f"攻击结果: {json.dumps(result, indent=2, ensure_ascii=False)}")

    # 测试防御动作
    print("\n3. 测试防御动作")
    defend_params = {"unit_id": unit1}
    result = action_handler.execute_action("defend", defend_params)
    print(f"防御结果: {json.dumps(result, indent=2, ensure_ascii=False)}")

    # 测试不支持的动作
    print("\n4. 测试不支持的动作")
    result = action_handler.execute_action("unknown_action", {})
    print(f"未知动作结果: {json.dumps(result, indent=2, ensure_ascii=False)}")

    # 获取支持的动作列表
    print("\n5. 支持的动作列表")
    actions = action_handler.get_supported_actions()
    print(f"支持的动作总数: {len(actions)}")
    for action_name, action_info in actions.items():
        print(f"  {action_name}: {action_info['function_desc']}")


def test_observation_system():
    """测试观测系统"""
    print("\n=== 测试观测系统 ===")

    world, unit1, unit2 = create_test_world()
    obs_system = LLMObservationSystem(world)

    # 测试单位观测
    print("\n1. 测试单位观测")
    unit_obs = obs_system.get_observation("unit", unit_id=unit1)
    print(f"单位观测结果: {json.dumps(unit_obs, indent=2, ensure_ascii=False)}")

    # 测试阵营观测
    print("\n2. 测试阵营观测")
    faction_obs = obs_system.get_observation("faction", faction=Faction.SHU)
    print(f"阵营观测结果: {json.dumps(faction_obs, indent=2, ensure_ascii=False)}")

    # 测试上帝视角观测
    print("\n3. 测试上帝视角观测")
    god_obs = obs_system.get_observation("godview")
    print(f"上帝视角观测结果: {json.dumps(god_obs, indent=2, ensure_ascii=False)}")

    # 测试受限观测
    print("\n4. 测试受限观测")
    limited_obs = obs_system.get_observation("limited", faction=Faction.WEI)
    print(f"受限观测结果: {json.dumps(limited_obs, indent=2, ensure_ascii=False)}")


def test_llm_system_integration():
    """测试LLM系统集成"""
    print("\n=== 测试LLM系统集成 ===")

    world, unit1, unit2 = create_test_world()

    # 创建LLM系统（不连接WebSocket）
    llm_system = LLMSystem()
    llm_system.world = world
    llm_system.action_handler = LLMActionHandler(world)
    llm_system.observation_system = LLMObservationSystem(world)

    # 测试动作处理
    print("\n1. 测试集成的动作处理")
    move_params = {"unit_id": unit1, "target_position": [6, 6]}
    result = llm_system.handle_move(move_params)
    print(f"集成移动结果: {json.dumps(result, indent=2, ensure_ascii=False)}")

    # 测试观测处理
    print("\n2. 测试集成的观测处理")
    obs_params = {"observation_level": "unit", "unit_id": unit1}
    result = llm_system.handle_observation(obs_params)
    print(f"集成观测结果: {json.dumps(result, indent=2, ensure_ascii=False)}")

    # 测试阵营观测
    print("\n3. 测试集成的阵营观测")
    faction_params = {"faction": "SHU", "include_hidden": True}
    result = llm_system.handle_faction_observation(faction_params)
    print(f"集成阵营观测结果: {json.dumps(result, indent=2, ensure_ascii=False)}")


def main():
    """主测试函数"""
    print("开始LLM系统功能测试...")

    try:
        # 测试动作处理器
        test_action_handler()

        # 测试观测系统
        test_observation_system()

        # 测试系统集成
        test_llm_system_integration()

        print("\n=== 测试完成 ===")
        print("所有功能模块测试通过！")

    except Exception as e:
        print(f"\n❌ 测试过程中出现错误: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
