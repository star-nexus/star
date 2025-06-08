#!/usr/bin/env python3
"""
完整的游戏流程测试
Full Game Flow Test
"""

import sys
import os
import pygame
from pathlib import Path

# 添加路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.append(str(Path(__file__).parent.parent / "framework_v2"))

from framework_v2.engine.game_engine import GameEngine
from rotk.scenes import StartScene, GameScene, GameOverScene


def test_game_flow():
    """测试完整游戏流程"""
    print("开始测试完整游戏流程...")
    print("StartScene -> GameScene -> GameOverScene")

    try:
        # 创建游戏引擎
        engine = GameEngine(
            title="完整游戏流程测试",
            width=1200,
            height=800,
            fps=60,
        )

        # 注册场景
        engine.scene_manager.register_scene("start", StartScene)
        engine.scene_manager.register_scene("game", GameScene)
        engine.scene_manager.register_scene("game_over", GameOverScene)

        # 设置初始场景
        engine.scene_manager.switch_to("start")

        print("游戏流程测试已启动!")
        print("1. 在开始界面配置游戏")
        print("2. 点击开始游戏按钮进入GameScene")
        print("3. 游戏结束后会自动进入GameOverScene")
        print("4. 按ESC或点击退出游戏按钮退出")

        # 启动游戏
        engine.start()

    except KeyboardInterrupt:
        print("\n测试被用户中断")
    except Exception as e:
        print(f"\n测试出错: {e}")
        import traceback

        traceback.print_exc()
    finally:
        pygame.quit()
        print("测试结束")


if __name__ == "__main__":
    test_game_flow()
