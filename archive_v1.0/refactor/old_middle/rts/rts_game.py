import pygame
import os
import sys

# 添加项目根目录到 Python 路径，确保可以导入顶层包
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from framework.core.game_engine import GameEngine
from rts.scenes.rts_menu_scene import RTSMenuScene
from rts.scenes.rts_game_scene import RTSGameScene


def main():
    """
    RTS游戏的主入口点
    初始化游戏引擎，注册场景，并启动游戏主循环
    """
    # 创建游戏引擎实例
    # 设置窗口尺寸为1024x768，标题为"Strategic Commander - RTS Game"
    game = GameEngine(width=1024, height=768, title="Strategic Commander - RTS Game")

    # 注册游戏场景
    # 'rts_menu' - 游戏主菜单场景
    game.scene_manager.register_scene("rts_menu", RTSMenuScene)
    # 'rts_game' - 游戏主要战略场景
    game.scene_manager.register_scene("rts_game", RTSGameScene)

    # 初始启动时切换到菜单场景
    # 该场景将显示游戏标题、开始按钮和其他选项
    game.scene_manager.change_scene("rts_menu")

    # 启动游戏主循环
    # 调用start()方法开始游戏主循环，处理事件、更新状态和渲染
    game.start()


# 当脚本直接运行时执行main函数
if __name__ == "__main__":
    main()
