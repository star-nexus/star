import pygame
import sys
from framework.core.engine import Engine
from framework.managers.events import EventManager
from game.managers.managers import GameManager
from game.scenes import GameScene
from game.menu_scenes import MenuScene
from game.victory_defeat_scenes import VictoryScene, DefeatScene
from game.systems import (
    MovementSystem,
    PlayerControlSystem,
    EnemyAISystem,
    CollisionSystem,
    GlowSystem,
    RenderSystem,
)


def main():
    # 创建游戏引擎实例
    engine = Engine(title="简单演示游戏", width=800, height=600, fps=60)

    # 添加游戏管理器
    engine.game_manager = GameManager(engine.event_manager)

    # 注册系统
    engine.world.add_system(MovementSystem())
    engine.world.add_system(PlayerControlSystem(engine.input_manager))
    engine.world.add_system(EnemyAISystem())
    engine.world.add_system(CollisionSystem(engine.event_manager))
    engine.world.add_system(GlowSystem(engine.world, engine.event_manager))
    engine.world.add_system(RenderSystem(engine.render_manager))

    # 注册场景
    engine.register_scene("menu", MenuScene(engine))
    engine.register_scene("game", GameScene(engine))
    engine.register_scene("victory", VictoryScene(engine))
    engine.register_scene("defeat", DefeatScene(engine))

    # 设置初始场景
    engine.switch_scene("menu")

    # 启动游戏
    try:
        engine.start()
    except Exception as e:
        print(f"游戏发生错误: {e}")
    finally:
        pygame.quit()
        sys.exit()


if __name__ == "__main__":
    main()
