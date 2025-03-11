import pygame
import sys
import os
from engine.core import GameEngine
from engine.scene_manager import SceneManager
from engine.asset_manager import AssetManager
from engine.input_manager import InputManager
from engine.event_manager import EventManager
from engine.map_manager import MapManager
from factories.entity_factory import EntityFactory
from managers.game_state_manager import GameStateManager
from managers.collision_manager import CollisionManager
from ui.ui_manager import UIManager

# 导入场景
from scenes.main_menu_scene import MainMenuScene
from scenes.game_scene import GameScene  # 更新为新的导入路径
from scenes.victory_scene import VictoryScene

# 主程序入口
if __name__ == "__main__":
    # 创建游戏引擎
    engine = GameEngine("模块化Pygame游戏", 800, 600)

    # 创建管理器
    event_manager = EventManager()
    asset_manager = AssetManager()
    input_manager = InputManager(event_manager)
    scene_manager = SceneManager(engine)
    map_manager = MapManager(asset_manager)

    # 创建游戏状态管理器和碰撞管理器
    game_state_manager = GameStateManager(engine)
    collision_manager = CollisionManager(engine)

    # 创建UI管理器
    ui_manager = UIManager(engine)

    # 将管理器添加到引擎
    engine.game_state_manager = game_state_manager
    engine.collision_manager = collision_manager
    engine.ui_manager = ui_manager

    # 初始化引擎
    engine.initialize(
        scene_manager, input_manager, asset_manager, event_manager, map_manager
    )

    # 创建场景
    menu_scene = MainMenuScene(engine)
    game_scene = GameScene(engine)
    victory_scene = VictoryScene(engine)

    # 添加场景到管理器
    scene_manager.add_scene("menu", menu_scene)
    scene_manager.add_scene("game", game_scene)
    scene_manager.add_scene("victory", victory_scene)

    # 设置初始场景
    scene_manager.change_scene("menu")

    # 启动游戏
    engine.start()
