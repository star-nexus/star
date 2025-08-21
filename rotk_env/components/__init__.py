"""
游戏组件模块
定义游戏中所有的ECS组件
"""

from .base import HexPosition, Renderable, AnimationState, PathFinding
from .unit import (
    Unit,
    Combat,
    Vision,
    Selected,
    AIControlled,
    UnitCount,
    UnitStatus,
    UnitSkills,
)

# 导入原有Movement组件用于向后兼容
from .unit import Movement as LegacyMovement, ActionPoints as LegacyActionPoints

# 导入新的多层次资源组件
from .multilayer_resources import (
    ActionPoints,
    MovementPoints,
    AttackPoints,
    ConstructionPoints,
    SkillPoints,
    # Movement,  # 新的Movement别名指向MovementPoints
)
from .terrain import Terrain, TerrainModifier, Tile, TerritoryControl, CaptureAction
from .player import Player, TurnOrder, TurnManager
from .state import GameState, MapData, UIState, InputState, FogOfWar, GameStats
from .unit_action_panel import (
    UnitActionPanel as OldUnitActionPanel,
    UnitActionButton as OldUnitActionButton,
    ActionConfirmDialog as OldActionConfirmDialog,
    ActionType as OldActionType,
)
from .unit_action_buttons import (
    UnitActionPanel,
    UnitActionButton,
    ActionConfirmDialog,
    ActionType,
)
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
from .agent_info import AgentInfo, AgentInfoRegistry

__all__ = [
    # 基础组件
    "HexPosition",
    "Renderable",
    "AnimationState",
    "PathFinding",
    # 单位组件
    "Unit",
    # "Movement",  # 新的多层次Movement组件
    "Combat",
    "Vision",
    "Selected",
    "AIControlled",
    "UnitCount",
    "UnitStatus",
    "UnitSkills",
    "ActionPoints",  # 新的多层次ActionPoints组件
    # 多层次资源组件
    "MovementPoints",
    "AttackPoints",
    "ConstructionPoints",
    "SkillPoints",
    # 向后兼容组件
    "LegacyMovement",
    "LegacyActionPoints",
    # 地形组件
    "Terrain",
    "TerrainModifier",
    "Tile",
    "TerritoryControl",
    "CaptureAction",
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
    # 单位行动面板组件
    "UnitActionPanel",
    "UnitActionButton",
    "ActionConfirmDialog",
    "ActionType",
    # 随机事件组件
    "DiceRoll",
    "TerrainEvent",
    "UnitSkillEvent",
    "RandomEventQueue",
    "CombatRoll",
    "AgentInfo",
    "AgentInfoRegistry",
]
