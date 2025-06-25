#!/usr/bin/env python3
"""
测试纯异步LLM系统连接（不使用线程）
"""

import asyncio
import sys
import os

# 添加项目路径
sys.path.append(os.path.dirname(__file__))

from rotk_env.systems.llm_system import LLMSystem
from framework_v2 import World


async def test_async_llm_connection():
    """测试异步LLM系统连接"""
    print("🚀 开始测试异步LLM连接...")

    # 创建模拟世界和系统
    world = World()
    llm_system = LLMSystem()

    try:
        # 初始化系统
        print("📋 初始化LLM系统...")
        llm_system.initialize(world)

        # 模拟游戏循环，多次调用update
        print("🔄 开始模拟游戏循环...")
        for i in range(20):  # 模拟20帧
            print(f"Frame {i+1}/20 - 连接状态: {llm_system.connection_status}")

            # 调用系统更新
            llm_system.update(0.016)  # 60 FPS

            # 给异步任务一些执行时间
            await asyncio.sleep(0.1)

            # 检查连接状态
            if llm_system.connection_status == "connected":
                print("✅ 连接成功建立！")
                break
            elif llm_system.connection_status == "error":
                print("❌ 连接失败")
                break

        # 等待一段时间看连接是否稳定
        if llm_system.connection_status == "connected":
            print("🔄 测试连接稳定性...")
            for i in range(5):
                await asyncio.sleep(1)
                llm_system.update(0.016)
                print(f"稳定性测试 {i+1}/5 - 状态: {llm_system.connection_status}")

                if llm_system.connection_status != "connected":
                    print("❌ 连接不稳定")
                    break
            else:
                print("✅ 连接稳定")

    except Exception as e:
        print(f"❌ 测试过程中出现错误: {e}")
        import traceback

        traceback.print_exc()

    finally:
        # 清理
        print("🧹 清理资源...")
        if hasattr(llm_system, "client_task") and llm_system.client_task:
            llm_system.client_task.cancel()
            try:
                await llm_system.client_task
            except asyncio.CancelledError:
                pass

        if (
            hasattr(llm_system, "environment_client")
            and llm_system.environment_client
            and hasattr(llm_system.environment_client, "connected")
            and llm_system.environment_client.connected
        ):
            try:
                await llm_system.environment_client.disconnect()
            except:
                pass

    print("🏁 测试完成")


if __name__ == "__main__":
    # 运行异步测试
    asyncio.run(test_async_llm_connection())
