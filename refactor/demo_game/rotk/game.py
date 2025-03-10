import pygame
import sys
from framework.core.engine import Engine

from rotk.managers import MapManager, FactionManager
from rotk.scenes import GameScene, StartScene, EndScene


def main():
    # 创建游戏引擎实例
    engine = Engine(title="简单演示游戏", width=800, height=600, fps=60)

    # 注册场景
    engine.register_scene("start", StartScene(engine))
    engine.register_scene("game", GameScene(engine))
    engine.register_scene("end", EndScene(engine))

    # 设置初始场景为开始菜单
    engine.switch_scene("start")

    # 启动游戏
    engine.start()


if __name__ == "__main__":
    main()
