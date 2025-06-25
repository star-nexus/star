#!/usr/bin/env python3
"""
LLM系统测试脚本 - 测试LLM系统的基本功能
"""

import sys
import os
import time

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from framework_v2 import World
from rotk_env.systems.llm_system import LLMSystem
from rotk_env.components import (
    GameState,
    Unit,
    Health,
    HexPosition,
    Movement,
    Combat,
    Vision,
    FogOfWar,
    Player,
    AIControlled,
    GameStats,
    BattleLog,
    UnitObservation,
)
from rotk_env.prefabs.config import Faction, PlayerType, GameMode, UnitType


def create_test_world():
    """创建测试用的世界和组件"""
    world = World()

    # 创建游戏状态
    game_state = GameState(
        current_player=Faction.WEI, game_mode=GameMode.TURN_BASED, turn_number=1
    )
    world.add_singleton_component(game_state)

    # 创建游戏统计
    game_stats = GameStats(
        faction_stats={
            Faction.WEI: {"battles_won": 0, "battles_lost": 0, "units_lost": 0},
            Faction.SHU: {"battles_won": 0, "battles_lost": 0, "units_lost": 0},
            Faction.WU: {"battles_won": 0, "battles_lost": 0, "units_lost": 0},
        },
        battle_history=[],
        turn_history=[],
        game_start_time=0.0,
        total_game_time=0.0,
    )
    world.add_singleton_component(game_stats)

    # 创建战斗日志
    battle_log = BattleLog(entries=[], max_entries=100)
    world.add_singleton_component(battle_log)

    # 创建测试单位
    for i, (faction, pos) in enumerate(
        [
            (Faction.WEI, (0, 0)),
            (Faction.WEI, (1, 0)),
            (Faction.SHU, (5, 5)),
            (Faction.SHU, (6, 5)),
        ]
    ):
        unit_entity = world.create_entity()

        # 添加单位组件
        unit = Unit(unit_type=UnitType.INFANTRY, faction=faction)
        world.add_component(unit_entity, unit)

        # 添加玩家组件
        player = Player(
            faction=faction, player_type=PlayerType.HUMAN, color=(255, 0, 0)
        )
        world.add_component(unit_entity, player)

        # 添加位置组件
        position = HexPosition(col=pos[0], row=pos[1])
        world.add_component(unit_entity, position)

        # 添加健康组件
        health = Health(current=100, maximum=100)
        world.add_component(unit_entity, health)

        # 添加移动组件
        movement = Movement(max_movement=3, current_movement=3, has_moved=False)
        world.add_component(unit_entity, movement)

        # 添加战斗组件
        combat = Combat(attack=10, defense=5, attack_range=1, has_attacked=False)
        world.add_component(unit_entity, combat)

        # 添加视野组件
        vision = Vision(range=2)
        world.add_component(unit_entity, vision)

    # 创建战争迷雾
    fog = FogOfWar(
        faction_vision={
            Faction.WEI: {(0, 0), (1, 0), (2, 0)},
            Faction.SHU: {(5, 5), (6, 5), (4, 5)},
            Faction.WU: set(),
        }
    )
    world.add_singleton_component(fog)

    return world


def test_llm_system_initialization():
    """测试LLM系统初始化"""
    print("=== 测试LLM系统初始化 ===")

    world = create_test_world()
    llm_system = LLMSystem()

    # 初始化系统
    llm_system.initialize(world)

    print(f"✓ LLM系统初始化成功")
    print(f"  - 服务器地址: {llm_system.client.server_url}")
    print(f"  - 环境ID: {llm_system.client.client_info.env_id}")
    print(f"  - 活跃会话: {len(llm_system.client.connected_agents)}")

    return world, llm_system


def test_observation_generation():
    """测试观测数据生成"""
    print("\n=== 测试观测数据生成 ===")

    world, llm_system = test_llm_system_initialization()

    # 测试完整观测
    full_obs = llm_system._generate_basic_observation(Faction.WEI)

    print(f"✓ 完整观测数据生成成功")
    print(f"  - 游戏状态: {bool(full_obs.get('game_state'))}")
    print(f"  - 地图信息: {bool(full_obs.get('map_info'))}")
    print(f"  - 单位信息: {bool(full_obs.get('units'))}")
    print(f"  - 己方单位数: {len(full_obs.get('units', {}).get('own_units', []))}")
    print(
        f"  - 敌方单位数: {len(full_obs.get('units', {}).get('visible_enemy_units', []))}"
    )
    print(f"  - 可见性信息: {bool(full_obs.get('visibility'))}")
    print(f"  - 战斗日志: {bool(full_obs.get('battle_log'))}")
    print(f"  - 统计信息: {bool(full_obs.get('statistics'))}")

    return world, llm_system


def test_action_execution():
    """测试动作执行"""
    print("\n=== 测试动作执行 ===")

    world, llm_system = test_llm_system_initialization()

    # 获取第一个WEI单位
    wei_unit = None
    for entity_id in world.entities.keys():
        if world.has_component(entity_id, Unit):
            player = world.get_component(entity_id, Player)
            if player and player.faction == Faction.WEI:
                wei_unit = entity_id
                break

    if wei_unit:
        # 测试移动
        move_params = {"unit_id": wei_unit, "target_position": {"col": 2, "row": 1}}
        move_result = llm_system._execute_move_unit(move_params)
        print(f"✓ 移动测试: {move_result.get('success', False)}")
        if move_result.get("success"):
            print(
                f"  - 单位{wei_unit}移动到({move_params['target_position']['col']}, {move_params['target_position']['row']})"
            )

        # 获取SHU单位作为攻击目标
        shu_unit = None
        for entity_id in world.entities.keys():
            if world.has_component(entity_id, Unit):
                player = world.get_component(entity_id, Player)
                if player and player.faction == Faction.SHU:
                    shu_unit = entity_id
                    break

        if shu_unit:
            # 测试攻击
            attack_params = {"attacker_id": wei_unit, "target_id": shu_unit}
            attack_result = llm_system._execute_attack_unit(attack_params)
            print(f"✓ 攻击测试: {attack_result.get('success', False)}")
            if attack_result.get("success"):
                print(
                    f"  - 单位{wei_unit}攻击单位{shu_unit}造成{attack_result.get('damage_dealt', 0)}点伤害"
                )

        # 测试回合结束
        end_turn_params = {"faction": "WEI"}
        end_turn_result = llm_system._execute_end_turn(end_turn_params)
        print(f"✓ 回合结束测试: {end_turn_result.get('success', False)}")
        if end_turn_result.get("success"):
            print(f"  - 重置了{end_turn_result.get('units_reset', 0)}个单位")

    return world, llm_system


def test_session_management():
    """测试会话管理"""
    print("\n=== 测试会话管理 ===")

    world, llm_system = test_llm_system_initialization()

    # 模拟会话初始化消息
    msg_from = {"agent_id": 1, "role_type": "agent"}
    msg_data = {
        "player_faction": "WEI",
        "control_level": "full",
        "capabilities": ["move_unit", "attack_unit", "end_turn"],
    }

    # 测试会话初始化
    import asyncio

    async def test_session_init():
        result = await llm_system.handle_session_init_async(msg_from, msg_data)
        return result

    # 运行异步测试
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    session_result = loop.run_until_complete(test_session_init())

    print(f"✓ 会话初始化测试: {session_result.get('status') == 'success'}")
    print(f"  - 分配阵营: {session_result.get('assigned_faction')}")
    print(f"  - 游戏状态: {session_result.get('game_state')}")
    print(f"  - 当前回合: {session_result.get('current_turn')}")
    print(f"  - 活跃会话数: {len(llm_system.active_sessions)}")

    # 测试观测请求
    obs_msg_data = {"faction": "WEI", "observation_type": "full"}

    async def test_observation_request():
        result = await llm_system.handle_observation_request_async(
            msg_from, obs_msg_data
        )
        return result

    obs_result = loop.run_until_complete(test_observation_request())
    print(f"✓ 观测请求测试: {bool(obs_result.get('units'))}")

    loop.close()

    return world, llm_system


def test_validation_and_helpers():
    """测试验证和辅助方法"""
    print("\n=== 测试验证和辅助方法 ===")

    world, llm_system = test_llm_system_initialization()

    # 创建一个测试会话
    llm_system.active_sessions[1] = {
        "agent_id": 1,
        "faction": "WEI",
        "active": True,
        "created_at": 0.0,
    }

    # 测试动作验证
    valid_move = llm_system._validate_action(
        "move_unit", {"unit_id": 1, "target_position": {"col": 2, "row": 3}}, 1
    )
    print(f"✓ 有效移动验证: {valid_move}")

    invalid_move = llm_system._validate_action(
        "move_unit", {"unit_id": 1}, 1  # 缺少目标位置
    )
    print(f"✓ 无效移动验证: {not invalid_move}")

    # 测试动作执行检查
    test_action = {
        "type": "move_unit",
        "params": {"unit_id": 1, "target_position": {"col": 2, "row": 3}},
        "timestamp": 0.0,
    }
    can_execute = llm_system._can_execute_action(test_action)
    print(f"✓ 动作执行检查: {can_execute}")

    # 测试统计辅助方法
    test_units = [
        {"health": {"percentage": 0.8}, "combat": {"attack": 10}},
        {"health": {"percentage": 0.6}, "combat": {"attack": 15}},
        {"health": {"percentage": 1.0}, "combat": {"attack": 8}},
    ]

    avg_health = llm_system._calculate_average_health(test_units)
    total_attack = llm_system._calculate_total_attack_power(test_units)

    print(f"✓ 平均健康度计算: {avg_health:.2f}")
    print(f"✓ 总攻击力计算: {total_attack}")

    # 测试当前回合获取
    current_turn = llm_system._get_current_turn()
    print(f"✓ 当前回合获取: {current_turn}")

    return world, llm_system


# def main():
#     """主测试函数"""
#     print("开始LLM系统测试...\n")

#     try:
#         # 运行所有测试
#         test_llm_system_initialization()
#         test_observation_generation()
#         test_action_execution()
#         # test_session_management()
#         # test_validation_and_helpers()

#         print("\n" + "=" * 50)
#         print("🎉 所有LLM系统测试通过！")
#         print("=" * 50)

#         print("\n📝 测试总结:")
#         print("  ✓ LLM系统初始化正常")
#         print("  ✓ 观测数据生成功能正常")
#         print("  ✓ 动作执行功能正常")
#         print("  ✓ 会话管理功能正常")
#         print("  ✓ 验证和辅助方法正常")

#         print("\n🚀 LLM系统已准备就绪，可以与Star Client集成！")
#         print("\n📌 下一步:")
#         print("  1. 启动WebSocket服务器")
#         print("  2. 运行游戏并初始化LLM系统")
#         print("  3. 连接LLM Agent客户端进行测试")
#         print("  4. 验证完整的消息传递和动作执行流程")

#     except Exception as e:
#         print(f"\n❌ 测试失败: {e}")
#         import traceback

#         traceback.print_exc()
#         return False

#     return True


def main():
    world = World()
    # world.add_system(PrintSystem())
    world.add_system(LLMSystem())

    try:
        main_loop(world)
    except KeyboardInterrupt:
        print("\n程序被中断")
    except Exception as e:
        print(f"程序错误: {e}")
    finally:
        # 清理资源
        for system in world.systems:
            if hasattr(system, "cleanup"):
                system.cleanup()


def main_loop(world: World):
    while True:
        delta_time = time.time()  # 获取当前时间戳作为 delta time
        world.update(delta_time)
        time.sleep(1)  # 模拟每秒更新一次


if __name__ == "__main__":
    main()
