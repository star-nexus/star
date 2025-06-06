"""
围棋游戏 - pygbag web版本入口
"""

import asyncio
import sys
import os

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from framework_v2.engine.async_game_engine import AsyncGameEngine
from framework_v2.engine.scenes import scene_manager

from go_game.scenes import MenuScene, GameScene


async def main():
    """异步游戏主函数 - 用于pygbag部署"""
    # 创建异步游戏引擎
    engine = AsyncGameEngine(title="围棋游戏 - Go Game", width=800, height=600, fps=60)

    # 注册场景
    scene_manager().register_scene("menu", MenuScene)
    scene_manager().register_scene("game", GameScene)

    # 设置初始场景
    scene_manager().switch_to("menu")

    # 启动游戏
    await engine.start()


if __name__ == "__main__":
    # 运行异步主函数
    asyncio.run(main())
