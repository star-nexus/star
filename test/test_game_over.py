#!/usr/bin/env python3
"""
测试游戏结束场景的快速脚本
"""

import pygame
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from framework_v2.engine.game_engine import GameEngine
from framework_v2.engine.scenes import SceneManager, SMS
from rotk.scenes.game_over_scene import GameOverScene
from rotk.scenes.start_scene import StartScene
from rotk.prefabs.config import Faction


def test_game_over_scene():
    """测试游戏结束场景"""

    # 初始化pygame
    # pygame.init()

    # 创建游戏引擎
    engine = GameEngine(title="ROTK Game Over Test", width=1024, height=768, fps=60)

    # 设置场景管理器
    SMS.set_engine(engine)

    # 创建并注册游戏结束场景
    engine.scene_manager.register_scene("start", StartScene)
    engine.scene_manager.register_scene("game_over", GameOverScene)

    # 准备测试数据
    test_statistics = {
        "total_turns": 25,
        "game_duration": 150.5,
        "total_units": 6,
        "surviving_units": 2,
        "faction_stats": {
            Faction.WEI: {
                "total_units": 3,
                "surviving_units": 2,
            },
            Faction.SHU: {
                "total_units": 3,
                "surviving_units": 0,
            },
        },
    }

    # 切换到游戏结束场景
    engine.scene_manager.switch_to(
        "game_over", winner=Faction.WEI, statistics=test_statistics
    )

    # 启动游戏
    engine.start()


if __name__ == "__main__":
    test_game_over_scene()
