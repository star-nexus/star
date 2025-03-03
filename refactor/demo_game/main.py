from framework.core.engine import Engine
from game.scenes import GameScene
from game.menu_scenes import MenuScene, GameOverScene
from game.systems import (
    MovementSystem,
    PlayerControlSystem,
    EnemyAISystem,
    CollisionSystem,
    RenderSystem,
    GlowSystem,
)
from game.managers import GameManager


def main():
    # 创建游戏引擎实例
    engine = Engine(title="简单演示游戏", width=800, height=600, fps=60)

    # 创建游戏管理器
    game_manager = GameManager(engine.event_manager)
    # 将游戏管理器附加到引擎以便场景可以访问
    engine.game_manager = game_manager

    # 创建场景
    menu_scene = MenuScene(engine)
    game_scene = GameScene(engine)
    victory_scene = GameOverScene(engine, is_victory=True)
    defeat_scene = GameOverScene(engine, is_victory=False)

    # 注册系统
    engine.world.add_system(MovementSystem())
    engine.world.add_system(PlayerControlSystem(engine.input_manager))
    engine.world.add_system(EnemyAISystem())
    engine.world.add_system(CollisionSystem(engine.event_manager))
    engine.world.add_system(GlowSystem(engine.world, engine.event_manager))
    engine.world.add_system(RenderSystem(engine.render_manager))

    # 注册场景
    engine.register_scene("menu", menu_scene)
    engine.register_scene("game", game_scene)
    engine.register_scene("victory", victory_scene)
    engine.register_scene("defeat", defeat_scene)

    # 切换到初始场景（菜单场景）
    engine.switch_scene("menu")

    # 启动游戏引擎
    engine.start()


if __name__ == "__main__":
    main()
