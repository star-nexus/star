import pygame
import sys
from framework.core.engine import Engine

from rotk.managers import MapManager
from rotk.scenes import (
    GameScene,
)

from rotk.systems import MapSystem


def main():
    # 创建游戏引擎实例
    engine = Engine(title="简单演示游戏", width=800, height=600, fps=60)

    # 注册场景
    engine.register_scene("game", GameScene(engine))
    # 设置初始场景
    engine.switch_scene("game")

    # 启动游戏
    engine.start()
    # try:
    #     engine.start()
    # except Exception as e:
    #     print(f"游戏发生错误: {e}")
    # finally:
    #     pygame.quit()
    #     sys.exit()


if __name__ == "__main__":
    main()
