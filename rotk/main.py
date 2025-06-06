#!/usr/bin/env python3
"""
三国策略游戏主启动文件
Romance of the Three Kingdoms Strategy Game

使用方法:
    python main.py [选项]

选项:
    --mode [turn_based|real_time]  游戏模式（默认: turn_based）
    --scenario [default|chibi|three_kingdoms]  游戏场景（默认: default）
    --players [human_vs_ai|ai_vs_ai|three_kingdoms]  玩家配置（默认: human_vs_ai）
    --help  显示帮助信息
"""

import sys
import os
import argparse
import pygame
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# 添加framework_v2到路径
sys.path.append(str(Path(__file__).parent.parent / "framework_v2"))

from framework_v2.engine.game_engine import GameEngine

from rotk.scenes import GameScene
from rotk.prefabs.config import Faction, PlayerType


def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="三国策略游戏 - Romance of the Three Kingdoms Strategy Game",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
游戏说明:
  这是一个基于六边形地图的回合制策略游戏，支持人类玩家和AI对战。
  游戏中有不同的地形类型，会对单位产生不同的效果。
  
控制说明:
  鼠标左键: 选择单位/移动/攻击
  鼠标右键: 取消选择
  WASD/方向键: 移动摄像机
  空格键: 结束回合
  Tab键: 显示/隐藏统计
  F1键: 显示/隐藏帮助
  ESC键: 取消选择

获胜条件:
  消灭所有敌方单位，或在回合结束时获得最高积分
        """,
    )

    parser.add_argument(
        "--mode",
        choices=["turn_based", "real_time"],
        default="turn_based",
        help="游戏模式 (默认: turn_based)",
    )

    parser.add_argument(
        "--scenario",
        choices=["default", "chibi", "three_kingdoms"],
        default="default",
        help="游戏场景 (默认: default)",
    )

    parser.add_argument(
        "--players",
        choices=["human_vs_ai", "ai_vs_ai", "three_kingdoms"],
        default="human_vs_ai",
        help="玩家配置 (默认: human_vs_ai)",
    )

    return parser.parse_args()


def create_game_from_args(args):
    """根据参数创建游戏"""
    players_config = {
        "human_vs_ai": {Faction.WEI: PlayerType.HUMAN, Faction.SHU: PlayerType.AI},
        "ai_vs_ai": {Faction.WEI: PlayerType.AI, Faction.SHU: PlayerType.AI},
        "three_kingdoms": {
            Faction.WEI: PlayerType.HUMAN,
            Faction.SHU: PlayerType.AI,
            Faction.WU: PlayerType.AI,
        },
    }

    return players_config.get(
        args.players, {Faction.WEI: PlayerType.HUMAN, Faction.SHU: PlayerType.AI}
    )


def print_welcome():
    """显示欢迎信息"""
    print("\n" + "=" * 60)
    print("  三国策略游戏")
    print("  Romance of the Three Kingdoms Strategy Game")
    print("=" * 60)
    print("\n基于framework_v2的六边形回合制策略游戏")
    print("\n游戏特色:")
    print("  ✓ 六边形地图系统")
    print("  ✓ 多种地形效果")
    print("  ✓ 战争迷雾系统")
    print("  ✓ AI和人类玩家")
    print("  ✓ 详细游戏统计")
    print("  ✓ 回合制策略")
    print("\n正在启动游戏...")


def main():
    """游戏主函数"""
    try:
        # 解析命令行参数
        args = parse_arguments()

        # 显示欢迎信息
        print_welcome()

        # 创建游戏引擎
        engine = GameEngine(
            title="三国策略游戏 - Romance of the Three Kingdoms",
            width=1024,
            height=768,
            fps=60,
        )

        # 获取玩家配置
        players_config = create_game_from_args(args)

        # 注册游戏场景
        engine.scene_manager.register_scene("game", GameScene)

        # 设置初始场景，传递参数
        engine.scene_manager.switch_to(
            "game", players=players_config, game_mode=args.mode
        )

        print(f"游戏模式: {args.mode}")
        print(f"玩家配置: {args.players}")
        print(f"游戏场景: {args.scenario}")
        print("游戏已启动! 按F1查看帮助信息。")

        # 启动游戏
        engine.start()

    except KeyboardInterrupt:
        print("\n游戏被用户中断")
    except Exception as e:
        print(f"\n游戏运行出错: {e}")
        import traceback

        traceback.print_exc()
    finally:
        pygame.quit()
        print("游戏结束")


if __name__ == "__main__":
    main()
