"""
Game components module.

Defines all ECS components used by the game.
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

# Import legacy Movement for backward compatibility.
from .unit import Movement as LegacyMovement

# Import the new multi-layer resource components.
from .multilayer_resources import (
    ActionPoints,
    MovementPoints,
    AttackPoints,
    ConstructionPoints,
    SkillPoints,
    # Movement,  # New Movement alias points to MovementPoints
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
    # Base components
    "HexPosition",
    "Renderable",
    "AnimationState",
    "PathFinding",
    # Unit components
    "Unit",
    # "Movement",  # New multi-layer Movement component
    "Combat",
    "Vision",
    "Selected",
    "AIControlled",
    "UnitCount",
    "UnitStatus",
    "UnitSkills",
    "ActionPoints",  # New multi-layer ActionPoints component
    # Multi-layer resource components
    "MovementPoints",
    "AttackPoints",
    "ConstructionPoints",
    "SkillPoints",
    # Backward compatibility
    "LegacyMovement",
    # Terrain components
    "Terrain",
    "TerrainModifier",
    "Tile",
    "TerritoryControl",
    "CaptureAction",
    # Player components
    "Player",
    "TurnOrder",
    "TurnManager",
    # State components
    "GameState",
    "MapData",
    "UIState",
    "InputState",
    "FogOfWar",
    "GameStats",
    "Camera",
    "MiniMap",
    "GameModeComponent",
    # Game time components
    "GameTime",
    # Animation components
    "MovementAnimation",
    "DamageNumber",
    "AttackAnimation",
    "EffectAnimation",
    "ProjectileAnimation",
    # Battle log components
    "BattleLog",
    "BattleLogEntry",
    "UnitObservation",
    "UnitStatistics",
    "VisibilityTracker",
    "GameModeStatistics",
    # Game over components
    "Winner",
    "GameStatistics",
    "GameOverButtons",
    # UI button components
    "UIButton",
    "UIButtonCollection",
    "UIPanel",
    # Unit action panel components
    "UnitActionPanel",
    "UnitActionButton",
    "ActionConfirmDialog",
    "ActionType",
    # Random event components
    "DiceRoll",
    "TerrainEvent",
    "UnitSkillEvent",
    "RandomEventQueue",
    "CombatRoll",
    "AgentInfo",
    "AgentInfoRegistry",
]
