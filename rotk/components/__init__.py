"""
游戏组件模块
定义游戏中所有的ECS组件
"""

from .base import HexPosition, Health, Renderable, AnimationState, PathFinding
from .unit import Unit, Movement, Combat, Vision, Selected, AIControlled
from .terrain import Terrain, TerrainModifier, Tile
from .player import Player, TurnOrder
from .state import GameState, MapData, UIState, InputState, FogOfWar, GameStats
from .minimap import MiniMap
from .gamemode import GameModeComponent
from .camera import Camera
from .animation import MovementAnimation, UnitStatus, DamageNumber

__all__ = [
    # 基础组件
    "HexPosition",
    "Health",
    "Renderable",
    "AnimationState",
    "PathFinding",
    # 单位组件
    "Unit",
    "Movement",
    "Combat",
    "Vision",
    "Selected",
    "AIControlled",
    # 地形组件
    "Terrain",
    "TerrainModifier",
    "Tile",
    # 玩家组件
    "Player",
    "TurnOrder",
    # 状态组件
    "GameState",
    "MapData",
    "UIState",
    "InputState",
    "FogOfWar",
    "GameStats",
    "Camera",
    "MiniMap",
    "GameModeComponent",
    # 动画组件
    "MovementAnimation",
    "UnitStatus",
    "DamageNumber",
]
