"""
开始场景相关组件
Start Scene Components
"""

import pygame
from dataclasses import dataclass, field
from typing import Dict, Any, List
from enum import Enum
from ..prefabs.config import Faction, PlayerType, GameMode
from framework_v2 import SingletonComponent


@dataclass
class StartMenuConfig(SingletonComponent):
    """开始菜单配置组件"""

    selected_mode: GameMode = GameMode.TURN_BASED
    selected_players: Dict[Faction, PlayerType] = field(
        default_factory=lambda: {
            Faction.WEI: PlayerType.HUMAN,
            Faction.SHU: PlayerType.AI,
        }
    )
    selected_scenario: str = "default"


@dataclass
class StartMenuButtons(SingletonComponent):
    """开始菜单按钮组件"""

    buttons: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    options: Dict[str, Dict[str, Any]] = field(default_factory=dict)


@dataclass
class StartMenuOptions(SingletonComponent):
    """开始菜单选项组件"""

    mode_options: List[Dict[str, Any]] = field(default_factory=list)
    player_options: List[Dict[str, Any]] = field(default_factory=list)
    scenario_options: List[Dict[str, Any]] = field(default_factory=list)
