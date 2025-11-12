"""
Settlement Report components.
Defines data carriers for the post-game report: overall report, battle stats,
map stats, and performance stats.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from framework import SingletonComponent
from ..prefabs.config import Faction


@dataclass
class SettlementReport(SingletonComponent):
    """Main settlement report component."""
    
    # Basic metadata
    experiment_id: str = ""  # experiment identifier (timestamp)
    timestamp: str = ""  # generation time (ISO)
    map_type: str = ""  # map type (human-readable)
    game_mode: str = ""  # game mode (turn_based/real_time)
    
    # Game result
    is_tie: bool = False  # draw or not
    winner_faction: Optional[Faction] = None  # winning faction (if any)
    is_half_win: bool = False  # partial victory (timeout with higher survivors)
    game_duration_seconds: float = 0.0  # duration in seconds
    game_duration_formatted: str = ""  # formatted duration string
    
    # Game progress (turn-based)
    total_turns: int = 0  # total turns
    
    units_info: Dict[str, Any] = field(default_factory=dict)  # unit details by faction
    
    model_info: Dict[str, str] = field(default_factory=dict)  # model id by faction
    
    agent_endpoints: Dict[str, str] = field(default_factory=dict)  # agent endpoint by faction
    
    strategy_scores: Dict[str, float] = field(default_factory=dict)  # strategy scores by faction
    
    strategy_evidence: Dict[str, List[str]] = field(default_factory=dict)  # recent strategy evidence snippets by faction
    
    enable_thinking: Dict[str, Optional[bool]] = field(default_factory=dict)  # thinking mode enabled by faction
    
    action_counts: Dict[str, int] = field(default_factory=dict)  # agent->env action count by faction
    interaction_counts: Dict[str, int] = field(default_factory=dict)  # agent->env message/interaction count by faction
    
    # LLM API statistics by faction
    llm_api_stats: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    # Battle statistics
    battle_statistics: Dict[str, Any] = field(default_factory=dict)
    
    # Map statistics
    map_statistics: Dict[str, Any] = field(default_factory=dict)
    
    # Performance statistics
    performance_statistics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BattleStatistics(SingletonComponent):
    """Battle statistics component."""
    
    total_battles: int = 0  # total number of battles
    
    # Per-faction battle stats
    faction_battle_stats: Dict[Faction, Dict[str, Any]] = field(default_factory=dict)
    
    battle_history: List[Dict[str, Any]] = field(default_factory=list)
    
    casualties: Dict[Faction, Dict[str, int]] = field(default_factory=dict)
    
    victory_types: Dict[str, int] = field(default_factory=dict)


@dataclass
class MapStatistics(SingletonComponent):
    """Map statistics component."""
    
    # Basic map info
    map_width: int = 0
    map_height: int = 0
    total_tiles: int = 0
    
    # Terrain distribution
    terrain_distribution: Dict[str, int] = field(default_factory=dict)
    
    # Territory control per faction
    territory_control: Dict[Faction, Dict[str, Any]] = field(default_factory=dict)
    
    # Map symmetry type
    symmetry_type: str = ""
    
    # Special features
    special_features: Dict[str, int] = field(default_factory=dict)


@dataclass
class PerformanceStatistics(SingletonComponent):
    """Performance statistics component."""
    
    # FPS statistics
    fps_statistics: Dict[str, float] = field(default_factory=dict)
    
    # Memory usage
    memory_usage: Dict[str, Any] = field(default_factory=dict)
    
    # Rendering performance
    rendering_performance: Dict[str, Any] = field(default_factory=dict)
    
    # System performance
    system_performance: Dict[str, Any] = field(default_factory=dict)
