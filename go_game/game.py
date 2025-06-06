"""
围棋游戏主入口 - 本地运行版本
"""

import sys
import os
import pygame

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from framework_v2.engine.game_engine import GameEngine
from framework_v2.engine.scenes import scene_manager

from go_game.scenes import MenuScene, GameScene


def main():
    """游戏主函数"""
    # 创建游戏引擎
    engine = GameEngine(title="围棋游戏 - Go Game", width=800, height=600, fps=60)

    # 注册场景
    scene_manager().register_scene("menu", MenuScene)
    scene_manager().register_scene("game", GameScene)

    # 设置初始场景
    scene_manager().switch_to("menu")

    # 启动游戏
    try:
        engine.start()
    except KeyboardInterrupt:
        print("游戏被用户中断")
    except Exception as e:
        print(f"游戏运行错误: {e}")
    finally:
        pygame.quit()


if __name__ == "__main__":
    main()
