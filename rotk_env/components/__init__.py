"""
游戏组件模块
定义游戏中所有的ECS组件
"""

from .base import HexPosition, Renderable, AnimationState, PathFinding
from .unit import (
    Unit,
    Movement,
    Combat,
    Vision,
    Selected,
    AIControlled,
    UnitCount,
    UnitStatus,
    UnitSkills,
    ActionPoints,
)
from .terrain import Terrain, TerrainModifier, Tile
from .player import Player, TurnOrder, TurnManager
from .state import GameState, MapData, UIState, InputState, FogOfWar, GameStats
from .minimap import MiniMap
from .gamemode import GameModeComponent
from .camera import Camera
from .game_time import GameTime
from .animation import (
    MovementAnimation,
    DamageNumber,
    AttackAnimation,
    EffectAnimation,
    ProjectileAnimation,
)
from .battle_log import BattleLog, BattleLogEntry
from .unit_observation import (
    UnitObservation,
    UnitStatistics,
    VisibilityTracker,
    GameModeStatistics,
)
from .game_over import Winner, GameStatistics, GameOverButtons
from .ui_button import UIButton, UIButtonCollection, UIPanel
from .random_events import (
    DiceRoll,
    TerrainEvent,
    UnitSkillEvent,
    RandomEventQueue,
    CombatRoll,
)

__all__ = [
    # 基础组件
    "HexPosition",
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
    "UnitCount",
    "UnitStatus",
    "UnitSkills",
    "ActionPoints",
    # 地形组件
    "Terrain",
    "TerrainModifier",
    "Tile",
    # 玩家组件
    "Player",
    "TurnOrder",
    "TurnManager",
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
    # 游戏时间组件
    "GameTime",
    # 动画组件
    "MovementAnimation",
    "DamageNumber",
    "AttackAnimation",
    "EffectAnimation",
    "ProjectileAnimation",
    # 战斗日志组件
    "BattleLog",
    "BattleLogEntry",
    "UnitObservation",
    "UnitStatistics",
    "VisibilityTracker",
    "GameModeStatistics",
    # 游戏结束组件
    "Winner",
    "GameStatistics",
    "GameOverButtons",
    # UI按钮组件
    "UIButton",
    "UIButtonCollection",
    "UIPanel",
    # 随机事件组件
    "DiceRoll",
    "TerrainEvent",
    "UnitSkillEvent",
    "RandomEventQueue",
    "CombatRoll",
]
