import pygame
import os
import sys

# 添加项目根目录到 Python 路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from framework.core.game_engine import GameEngine
from examples.scenes.main_menu_scene import MainMenuScene
from examples.scenes import GameScene
from examples.scenes.game_over_scene import GameOverScene


def main():
    # 创建游戏引擎
    game = GameEngine(width=800, height=600, title="Simple Game Demo")

    # 注册场景
    game.scene_manager.register_scene("main_menu", MainMenuScene)
    game.scene_manager.register_scene("game", GameScene)
    game.scene_manager.register_scene("game_over", GameOverScene)

    # 切换到主菜单场景
    game.scene_manager.change_scene("main_menu")

    # 启动游戏
    game.start()


if __name__ == "__main__":
    main()
