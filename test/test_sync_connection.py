"""
测试同步LLM系统连接 - 模拟真实游戏运行环境
这个测试更接近游戏实际运行时的同步调用模式
"""

import time
import sys
import os

# 添加项目路径
sys.path.append(os.path.dirname(__file__))

from rotk.systems.llm_system import LLMSystem
from framework_v2 import World


def test_sync_llm_connection():
    """测试同步LLM系统连接 - 模拟游戏主循环"""
    print("🚀 开始测试同步LLM连接（模拟游戏主循环）...")

    # 创建模拟世界和系统
    world = World()
    llm_system = LLMSystem()

    try:
        # 初始化系统
        print("📋 初始化LLM系统...")
        world.add_system(llm_system)

        print(f"初始连接状态: {llm_system.connection_status}")
        print(f"Environment Client: {llm_system.environment_client}")

        # 模拟游戏主循环 - 完全同步
        print("🔄 开始模拟游戏主循环（同步模式）...")

        frame_count = 0
        max_frames = 3000  # 5秒钟 @ 60 FPS
        target_fps = 60
        frame_time = 1.0 / target_fps

        start_time = time.time()
        last_status_print = start_time

        while frame_count < max_frames:
            frame_start = time.time()

            # 调用系统更新 - 这是同步的
            world.update(frame_time)

            # 每秒打印一次状态
            current_time = time.time()
            # if current_time - last_status_print >= 1.0:
            #     elapsed = current_time - start_time
            #     print(
            #         f"[{elapsed:.1f}s] Frame {frame_count:3d} - 连接状态: {llm_system.connection_status}"
            #     )

            #     # 打印详细状态信息
            #     if (
            #         hasattr(llm_system, "environment_client")
            #         and llm_system.environment_client
            #     ):
            #         client = llm_system.environment_client
            #         print(
            #             f"  └─ Client connected: {getattr(client, 'connected', 'Unknown')}"
            #         )
            #         if hasattr(llm_system, "client_task"):
            #             task = llm_system.client_task
            #             if task:
            #                 print(
            #                     f"  └─ Client task: {task.done()=}, {task.cancelled()=}"
            #                 )
            #                 if task.done() and not task.cancelled():
            #                     try:
            #                         result = task.result()
            #                         print(f"  └─ Task result: {result}")
            #                     except Exception as e:
            #                         print(f"  └─ Task exception: {e}")

            #     last_status_print = current_time

            #     # 如果连接成功，测试一段时间后退出
            #     if llm_system.connection_status == "connected":
            #         print("✅ 连接成功建立！继续测试稳定性...")
            #         # 再测试5秒钟稳定性
            #         if elapsed > 8.0:  # 连接后测试3秒稳定性
            #             print("✅ 连接稳定测试完成")
            #             break

            #     # 如果连接失败，提前退出
            #     elif llm_system.connection_status == "error":
            #         print("❌ 连接失败，提前退出")
            #         break

            # 维持帧率
            frame_elapsed = time.time() - frame_start
            sleep_time = max(0, frame_time - frame_elapsed)
            if sleep_time > 0:
                time.sleep(sleep_time)

            frame_count += 1

        # 最终状态报告
        total_time = time.time() - start_time
        actual_fps = frame_count / total_time
        print(f"\n📊 测试完成:")
        print(f"  总时间: {total_time:.2f}s")
        print(f"  总帧数: {frame_count}")
        print(f"  实际FPS: {actual_fps:.1f}")
        print(f"  最终连接状态: {llm_system.connection_status}")

        # 测试具体功能
        # if llm_system.connection_status == "connected":
        #     print("\n🧪 测试LLM系统功能...")
        #     test_llm_system_features(llm_system)

    except KeyboardInterrupt:
        print("\n⏹️  用户中断测试")
    except Exception as e:
        print(f"❌ 测试过程中出现错误: {e}")
        import traceback

        traceback.print_exc()

    finally:
        # 清理
        print("\n🧹 清理资源...")
        cleanup_llm_system(llm_system)

    print("🏁 同步测试完成")


def test_llm_system_features(llm_system):
    """测试LLM系统的具体功能"""
    print("  测试观测数据生成...")
    try:
        # 测试基本观测
        obs = llm_system._generate_basic_observation("WEI")
        print(f"  ✅ 基本观测数据: {len(obs)} 个键")

        # 测试游戏状态收集
        game_state = llm_system._collect_game_state()
        print(f"  ✅ 游戏状态数据: {len(game_state)} 个键")

        # 测试消息功能
        test_send_message(llm_system)
        test_receive_message(llm_system)
        test_execute_message(llm_system)

    except Exception as e:
        print(f"  ❌ 功能测试失败: {e}")


def test_send_message(llm_system):
    """测试发送消息功能"""
    print("  测试发送消息...")
    try:
        if (
            llm_system.connection_status == "connected"
            and llm_system.environment_client
        ):
            # 测试发送基本消息
            test_message = {
                "type": "test_message",
                "content": "这是一个测试消息",
                "timestamp": time.time(),
                "sender": "test_system",
            }

            # 通过同步接口添加到发送队列
            if hasattr(llm_system, "sync_message_queue"):
                llm_system.sync_message_queue.append(
                    {"action": "send", "message": test_message}
                )
                print(f"  ✅ 消息已添加到发送队列: {test_message['type']}")

            # 测试发送观测请求
            observation_request = {
                "type": "observation_request",
                "faction": "WEI",
                "requested_data": ["units", "buildings", "resources"],
                "timestamp": time.time(),
            }

            if hasattr(llm_system, "sync_message_queue"):
                llm_system.sync_message_queue.append(
                    {"action": "send", "message": observation_request}
                )
                print(f"  ✅ 观测请求已添加到队列")

            # 测试发送策略消息
            strategy_message = {
                "type": "strategy_update",
                "faction": "WEI",
                "strategy": {
                    "focus": "defense",
                    "priority_targets": [],
                    "formation": "defensive",
                },
                "timestamp": time.time(),
            }

            if hasattr(llm_system, "sync_message_queue"):
                llm_system.sync_message_queue.append(
                    {"action": "send", "message": strategy_message}
                )
                print(f"  ✅ 策略消息已添加到队列")

        else:
            print(f"  ⚠️  无法发送消息 - 连接状态: {llm_system.connection_status}")

    except Exception as e:
        print(f"  ❌ 发送消息测试失败: {e}")


def test_receive_message(llm_system):
    """测试接收消息功能"""
    print("  测试接收消息...")
    try:
        # 模拟接收到的消息
        mock_messages = [
            {
                "type": "agent_connection",
                "agent_id": "test_agent_001",
                "faction": "WEI",
                "capabilities": ["observation", "decision", "strategy"],
                "timestamp": time.time(),
            },
            {
                "type": "decision_request",
                "agent_id": "test_agent_001",
                "observation_data": {
                    "units": [
                        {"id": 1, "type": "infantry", "hp": 100, "position": [10, 20]}
                    ],
                    "resources": {"gold": 1000, "food": 500},
                    "turn": 1,
                },
                "timestamp": time.time(),
            },
            {
                "type": "action_response",
                "agent_id": "test_agent_001",
                "actions": {
                    "1": {"action": "move", "args": [15, 25]},
                    "2": {"action": "attack", "args": "enemy_unit_5"},
                },
                "timestamp": time.time(),
            },
        ]

        # 测试消息接收处理
        for message in mock_messages:
            if hasattr(llm_system, "sync_message_queue"):
                llm_system.sync_message_queue.append(
                    {"action": "receive", "message": message}
                )
                print(f"  ✅ 模拟接收消息: {message['type']}")

            # 测试消息处理逻辑
            if message["type"] == "agent_connection":
                # 模拟agent连接处理
                agent_id = message["agent_id"]
                if hasattr(llm_system, "connected_agents"):
                    llm_system.connected_agents[agent_id] = {
                        "faction": message["faction"],
                        "capabilities": message["capabilities"],
                        "connected_at": time.time(),
                    }
                    print(f"    📝 已记录Agent连接: {agent_id}")

            elif message["type"] == "decision_request":
                # 模拟决策请求处理
                print(
                    f"    🧠 处理决策请求 - 观测数据包含 {len(message['observation_data'])} 个键"
                )

            elif message["type"] == "action_response":
                # 模拟动作响应处理
                actions = message["actions"]
                print(f"    ⚡ 处理动作响应 - 包含 {len(actions)} 个动作")

        print(f"  ✅ 接收消息测试完成 - 处理了 {len(mock_messages)} 条消息")

    except Exception as e:
        print(f"  ❌ 接收消息测试失败: {e}")


def test_execute_message(llm_system):
    """测试执行消息功能"""
    print("  测试执行消息...")
    try:
        # 模拟需要执行的消息类型
        execution_messages = [
            {
                "type": "unit_action",
                "unit_id": 1,
                "action": "move",
                "target_position": [25, 30],
                "timestamp": time.time(),
            },
            {
                "type": "combat_action",
                "attacker_id": 1,
                "target_id": 5,
                "action": "attack",
                "timestamp": time.time(),
            },
            {
                "type": "strategy_execution",
                "faction": "WEI",
                "strategy_type": "formation_change",
                "parameters": {"formation": "wedge", "units": [1, 2, 3]},
                "timestamp": time.time(),
            },
            {
                "type": "environment_update",
                "update_type": "turn_end",
                "faction": "WEI",
                "turn_number": 1,
                "timestamp": time.time(),
            },
        ]

        # 执行消息处理
        for message in execution_messages:
            print(f"    🎯 执行消息类型: {message['type']}")

            try:
                # 根据消息类型执行相应逻辑
                if message["type"] == "unit_action":
                    result = execute_unit_action(llm_system, message)
                    print(f"      ✅ 单位动作执行结果: {result}")

                elif message["type"] == "combat_action":
                    result = execute_combat_action(llm_system, message)
                    print(f"      ⚔️ 战斗动作执行结果: {result}")

                elif message["type"] == "strategy_execution":
                    result = execute_strategy(llm_system, message)
                    print(f"      📋 策略执行结果: {result}")

                elif message["type"] == "environment_update":
                    result = execute_environment_update(llm_system, message)
                    print(f"      🌍 环境更新结果: {result}")

                # 记录执行结果
                if hasattr(llm_system, "action_results"):
                    llm_system.action_results[f"msg_{time.time()}"] = {
                        "message_type": message["type"],
                        "execution_time": time.time(),
                        "status": "success",
                    }

            except Exception as e:
                print(f"      ❌ 执行消息失败: {e}")
                if hasattr(llm_system, "action_results"):
                    llm_system.action_results[f"msg_{time.time()}"] = {
                        "message_type": message["type"],
                        "execution_time": time.time(),
                        "status": "failed",
                        "error": str(e),
                    }

        print(f"  ✅ 执行消息测试完成 - 处理了 {len(execution_messages)} 条执行消息")

    except Exception as e:
        print(f"  ❌ 执行消息测试失败: {e}")


def execute_unit_action(llm_system, message):
    """执行单位动作"""
    unit_id = message["unit_id"]
    action = message["action"]

    if action == "move":
        target_pos = message["target_position"]
        # 模拟移动逻辑
        return f"单位 {unit_id} 移动到位置 {target_pos}"
    else:
        return f"未知单位动作: {action}"


def execute_combat_action(llm_system, message):
    """执行战斗动作"""
    attacker_id = message["attacker_id"]
    target_id = message["target_id"]
    action = message["action"]

    if action == "attack":
        # 模拟攻击逻辑
        damage = 25  # 模拟伤害值
        return f"单位 {attacker_id} 攻击单位 {target_id} 造成 {damage} 伤害"
    else:
        return f"未知战斗动作: {action}"


def execute_strategy(llm_system, message):
    """执行策略"""
    faction = message["faction"]
    strategy_type = message["strategy_type"]
    parameters = message["parameters"]

    if strategy_type == "formation_change":
        formation = parameters["formation"]
        units = parameters["units"]
        return f"阵营 {faction} 将单位 {units} 变更为 {formation} 阵型"
    else:
        return f"未知策略类型: {strategy_type}"


def execute_environment_update(llm_system, message):
    """执行环境更新"""
    update_type = message["update_type"]

    if update_type == "turn_end":
        faction = message["faction"]
        turn_number = message["turn_number"]
        return f"阵营 {faction} 结束回合 {turn_number}"
    else:
        return f"未知环境更新类型: {update_type}"


def cleanup_llm_system(llm_system):
    """清理LLM系统资源"""
    try:
        # 取消异步任务
        if hasattr(llm_system, "client_task") and llm_system.client_task:
            print("  取消客户端任务...")
            llm_system.client_task.cancel()

        # 断开连接
        if (
            hasattr(llm_system, "environment_client")
            and llm_system.environment_client
            and hasattr(llm_system.environment_client, "connected")
            and llm_system.environment_client.connected
        ):
            print("  断开环境客户端连接...")
            # 注意：这里不能直接调用async方法，在实际游戏中需要特殊处理
            # await llm_system.environment_client.disconnect()

        print("  ✅ 清理完成")

    except Exception as e:
        print(f"  ⚠️  清理过程中出现错误: {e}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="测试LLM系统连接")
    args = parser.parse_args()
    test_sync_llm_connection()
