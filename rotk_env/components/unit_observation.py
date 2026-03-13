"""
Unit observation and statistics components.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Tuple, Any
import time
from framework import Component, SingletonComponent
from ..prefabs.config import Faction, UnitType


@dataclass
class UnitObservation(Component):
    """Unit observation component (observable state snapshot)."""

    # Position
    current_position: Tuple[int, int] = (0, 0)
    previous_position: Tuple[int, int] = (0, 0)

    # Health
    health_percentage: float = 100.0

    # Action state
    movement_remaining: int = 0
    has_acted_this_turn: bool = False

    # Visibility
    is_visible_to: Set[Faction] = field(default_factory=set)
    last_seen_time: float = field(default_factory=time.time)

    # Terrain effects
    current_terrain_type: str = "plains"
    terrain_bonus_active: bool = False

    # Combat state
    in_combat: bool = False
    last_combat_time: float = 0.0

    # Movement trail
    movement_path: List[Tuple[int, int]] = field(default_factory=list)
    total_distance_moved: int = 0


@dataclass
class UnitStatistics(Component):
    """Per-unit statistics."""

    # Core stats
    kills: int = 0
    deaths: int = 0
    damage_dealt: int = 0
    damage_taken: int = 0

    # Action stats
    moves_made: int = 0
    attacks_made: int = 0
    turns_survived: int = 0

    # Combat stats
    battles_participated: int = 0
    battles_won: int = 0
    battles_lost: int = 0

    # Terrain stats
    terrain_types_visited: Set[str] = field(default_factory=set)
    terrain_bonuses_used: int = 0

    # Time stats
    total_active_time: float = 0.0
    creation_time: float = field(default_factory=time.time)


@dataclass
class VisibilityTracker(SingletonComponent):
    """Visibility tracker for units (data-only)."""

    # Faction -> visible unit ids
    faction_visible_units: Dict[Faction, Set[int]] = field(default_factory=dict)

    # Unit id -> visibility history records
    visibility_history: Dict[int, List[Dict]] = field(default_factory=dict)

    # Reconnaissance stats
    reconnaissance_stats: Dict[Faction, Dict[str, int]] = field(default_factory=dict)


@dataclass
class GameModeStatistics(SingletonComponent):
    """Game-mode statistics (data-only)."""

    # Turn-based stats
    turn_based_stats: Dict[str, Any] = field(
        default_factory=lambda: {
            "total_turns": 0,
            "average_turn_duration": 0.0,
            "longest_turn": 0.0,
            "shortest_turn": float("inf"),
            "turn_durations": [],
            "faction_turn_times": {},
            "actions_per_turn": {},
        }
    )

    # Real-time stats
    realtime_stats: Dict[str, Any] = field(
        default_factory=lambda: {
            "total_game_time": 0.0,
            "actions_per_minute": 0.0,
            "peak_activity_time": 0.0,
            "action_frequency": [],
            "faction_activity": {},
            "concurrent_actions": 0,
        }
    )

    # Current tracking window
    current_mode: str = "turn_based"
    current_turn_start_time: float = 0.0
    actions_this_turn: int = 0
    actions_this_minute: int = 0
    last_action_time: float = 0.0
