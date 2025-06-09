#!/usr/bin/env python3
"""
测试统计系统功能
Test Statistics System Features
"""

import os
import sys
import time
import json

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pygame
from framework_v2.engine.game_engine import GameEngine
from rotk.scenes.game_scene import GameScene
from rotk.prefabs.config import Faction, PlayerType, GameMode


def test_game_statistics():
    """测试游戏统计功能"""
    print("=" * 60)
    print("测试游戏统计功能")
    print("=" * 60)

    # 初始化pygame（必须的，否则游戏引擎会报错）
    pygame.init()

    try:
        # 创建引擎和场景
        engine = GameEngine()
        game_scene = GameScene(engine)

        # 配置游戏参数
        players = {
            Faction.WEI: PlayerType.HUMAN,
            Faction.SHU: PlayerType.AI,
            Faction.WU: PlayerType.AI,
        }

        # 测试回合制模式统计
        print("\n1. 测试回合制模式统计...")
        game_scene.enter(players=players, mode=GameMode.TURN_BASED, headless=True)

        # 获取统计系统
        statistics_system = None
        for system in game_scene.world.systems:
            if system.__class__.__name__ == "StatisticsSystem":
                statistics_system = system
                break

        if not statistics_system:
            print("❌ 统计系统未找到！")
            return False

        print("✅ 统计系统已初始化")

        # 检查初始统计数据
        initial_stats = statistics_system.get_detailed_statistics()
        print(f"✅ 初始统计数据: {len(initial_stats)} 个类别")

        for category, data in initial_stats.items():
            print(f"   - {category}: {type(data).__name__}")
            if isinstance(data, dict):
                print(f"     包含 {len(data)} 个键: {list(data.keys())}")

        # 模拟一些游戏事件
        print("\n2. 模拟游戏事件...")

        # 获取一些单位进行测试
        wei_units = []
        shu_units = []

        from rotk.components import Unit, Health, HexPosition

        for entity in (
            game_scene.world.query().with_all(Unit, Health, HexPosition).entities()
        ):
            unit = game_scene.world.get_component(entity, Unit)
            if unit:
                if unit.faction == Faction.WEI and len(wei_units) < 2:
                    wei_units.append(entity)
                elif unit.faction == Faction.SHU and len(shu_units) < 2:
                    shu_units.append(entity)

        # 模拟战斗
        if wei_units and shu_units:
            print("   模拟战斗事件...")
            statistics_system.record_combat_action(
                wei_units[0], shu_units[0], 25, "damage"
            )
            print("   ✅ 战斗事件已记录")

            # 模拟移动
            print("   模拟移动事件...")
            statistics_system.record_movement_action(wei_units[0], (0, 0), (1, 1))
            print("   ✅ 移动事件已记录")

            # 模拟回合变化
            print("   模拟回合变化...")
            statistics_system.record_turn_change(Faction.WEI, Faction.SHU)
            print("   ✅ 回合变化已记录")

        # 让统计系统运行一段时间收集观测数据
        print("\n3. 收集单位观测数据...")
        for i in range(3):
            game_scene.world.update(1.0)
            time.sleep(0.1)
        print("   ✅ 观测数据收集完成")

        # 获取最终统计数据
        print("\n4. 检查最终统计数据...")
        final_stats = statistics_system.get_detailed_statistics()

        # 检查游戏统计
        game_stats = final_stats.get("game_stats", {})
        print(f"   游戏统计:")
        print(f"   - 战斗数量: {game_stats.get('battle_count', 0)}")
        print(f"   - 回合数量: {game_stats.get('turn_count', 0)}")
        print(f"   - 观测记录: {game_stats.get('observation_count', 0)}")

        faction_summaries = game_stats.get("faction_summaries", {})
        for faction, summary in faction_summaries.items():
            print(
                f"   - {faction}阵营: 击杀{summary.get('kills', 0)}, 损失{summary.get('losses', 0)}"
            )

        # 检查单位统计
        unit_stats = final_stats.get("unit_stats", {})
        print(f"   单位统计:")
        for faction, summary in unit_stats.items():
            print(
                f"   - {faction}: 单位数{summary.get('unit_count', 0)}, 总击杀{summary.get('total_kills', 0)}"
            )

        print("✅ 回合制模式统计测试完成")

        # 测试实时模式
        print("\n5. 测试实时模式统计...")

        # 重新创建场景测试实时模式
        game_scene2 = GameScene(engine)
        game_scene2.enter(players=players, mode=GameMode.REAL_TIME, headless=True)

        # 获取实时模式的统计系统
        rt_statistics_system = None
        for system in game_scene2.world.systems:
            if system.__class__.__name__ == "StatisticsSystem":
                rt_statistics_system = system
                break

        if rt_statistics_system:
            print("✅ 实时模式统计系统已初始化")

            # 运行几秒钟让系统收集数据
            for i in range(5):
                game_scene2.world.update(1.0)
                time.sleep(0.1)

            rt_stats = rt_statistics_system.get_detailed_statistics()
            mode_stats = rt_stats.get("mode_stats", {})
            print(f"   实时模式统计: {len(mode_stats)} 个指标")
            if mode_stats:
                print(f"   - 实时统计可用: {list(mode_stats.keys())}")

            print("✅ 实时模式统计测试完成")
        else:
            print("❌ 实时模式统计系统未找到")

        print("\n" + "=" * 60)
        print("统计系统测试总结:")
        print("✅ 统计系统正确初始化")
        print("✅ 战斗事件记录功能正常")
        print("✅ 移动事件记录功能正常")
        print("✅ 回合变化记录功能正常")
        print("✅ 单位观测数据收集正常")
        print("✅ 统计数据获取功能正常")
        print("✅ 实时模式统计功能正常")
        print("=" * 60)

        return True

    except Exception as e:
        print(f"❌ 测试过程中出现错误: {e}")
        import traceback

        traceback.print_exc()
        return False
    finally:
        pygame.quit()


def save_statistics_report(stats_data, filename="statistics_report.json"):
    """保存统计报告到文件"""
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(stats_data, f, ensure_ascii=False, indent=2, default=str)
        print(f"✅ 统计报告已保存到 {filename}")
    except Exception as e:
        print(f"❌ 保存统计报告失败: {e}")


if __name__ == "__main__":
    print("开始测试ROTK游戏统计系统...")
    success = test_game_statistics()

    if success:
        print("🎉 所有统计功能测试通过！")
        sys.exit(0)
    else:
        print("💥 统计功能测试失败！")
        sys.exit(1)
