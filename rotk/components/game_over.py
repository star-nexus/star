"""
游戏结束相关组件
Game Over Components
"""

import pygame
from dataclasses import dataclass
from typing import Dict, Any, Optional
from ..prefabs.config import Faction


@dataclass
class Winner:
    """获胜者组件"""

    faction: Optional[Faction] = None


@dataclass
class GameStatistics:
    """游戏统计数据组件"""

    data: Dict[str, Any]


@dataclass
class GameOverButtons:
    """游戏结束按钮组件"""

    buttons: Dict[str, Dict[str, Any]]
