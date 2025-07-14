"""
游戏结束相关组件
Game Over Components
"""

import pygame
from dataclasses import dataclass
from typing import Dict, Any, Optional
from ..prefabs.config import Faction
from framework import SingletonComponent


@dataclass
class Winner(SingletonComponent):
    """获胜者组件"""

    faction: Optional[Faction] = None


@dataclass
class GameStatistics(SingletonComponent):
    """游戏统计数据组件"""

    data: Dict[str, Any]


@dataclass
class GameOverButtons(SingletonComponent):
    """游戏结束按钮组件"""

    buttons: Dict[str, Dict[str, Any]]
