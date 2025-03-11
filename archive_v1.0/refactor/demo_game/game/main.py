import pygame
import sys
from framework.core.engine import Engine
from game.managers.game_manager import GameManager
from game.managers.map_manager import MapManager
from game.scenes.game_scene import GameScene
from game.scenes.menu_scene import MenuScene
from game.scenes.victory_defeat_scene import VictoryScene, DefeatScene
from game.scenes.map_edit_scene import MapEditScene
from game.systems import (
    MovementSystem,
    PlayerControlSystem,
    EnemyAISystem,
    CollisionDetectionSystem,
    CollisionResponseSystem,
    GlowSystem,
    RenderSystem,
    # 地图系统
    MapGenerationSystem,
    MapRenderSystem,
    TerrainEffectSystem,
)


def main():
    # 创建游戏引擎实例
    engine = Engine(title="简单演示游戏", width=800, height=600, fps=60)

    # 添加游戏管理器
    engine.game_manager = GameManager(engine.event_manager)

    # 注册系统
    # 地图系统 - 应在其他系统之前注册，确保地图先生成和渲染
    engine.world.add_system(MapGenerationSystem())
    engine.world.add_system(MapRenderSystem(engine.render_manager))
    engine.world.add_system(TerrainEffectSystem())

    # 原有系统
    engine.world.add_system(MovementSystem())  # 移动系统已经集成了边界检查
    engine.world.add_system(PlayerControlSystem(engine.input_manager))
    engine.world.add_system(EnemyAISystem())
    engine.world.add_system(RenderSystem(engine.render_manager))

    # 正确初始化碰撞检测系统
    engine.world.add_system(CollisionDetectionSystem(engine.event_manager))

    # 正确初始化碰撞响应系统，并调用setup方法订阅事件
    collision_response = CollisionResponseSystem(engine.event_manager)
    collision_response.setup(engine.world)
    glow = GlowSystem(engine.event_manager)
    glow.setup(engine.world)
    engine.world.add_system(collision_response)
    engine.world.add_system(glow)

    # 注册场景
    engine.register_scene("menu", MenuScene(engine))
    engine.register_scene("game", GameScene(engine))
    engine.register_scene("victory", VictoryScene(engine))
    engine.register_scene("defeat", DefeatScene(engine))
    # 添加地图编辑场景
    engine.register_scene("map_edit", MapEditScene(engine))

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
