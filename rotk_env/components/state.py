"""
Game-state related singleton components.
"""

from dataclasses import dataclass, field
from typing import Dict, Set, Tuple, Optional, List
from framework import SingletonComponent
from ..prefabs.config import Faction, GameMode


@dataclass
class GameState(SingletonComponent):
    """Singleton game state."""

    current_player: Faction
    turn_number: int = 1
    game_mode: GameMode = GameMode.TURN_BASED
    game_over: bool = False
    paused: bool = False
    winner: Optional[Faction] = None
    max_turns: int = 50


@dataclass
class MapData(SingletonComponent):
    """Singleton map data."""

    width: int
    height: int
    tiles: Dict[Tuple[int, int], int] = field(
        default_factory=dict
    )  # (col,row) -> tile entity id


@dataclass
class UIState(SingletonComponent):
    """Singleton UI state."""

    selected_unit: Optional[int] = None
    hovered_tile: Optional[Tuple[int, int]] = None
    show_grid: bool = True
    show_stats: bool = False
    show_help: bool = False
    show_coordinates: bool = False  # Show coordinates overlay
    camera_position: Tuple[float, float] = (0.0, 0.0)
    zoom_level: float = 1.0
    # View-related
    god_mode: bool = False  # God view (no fog of war)
    view_faction: Optional[Faction] = None  # Current viewed faction perspective


@dataclass
class InputState(SingletonComponent):
    """Singleton input state."""

    mouse_pos: Tuple[int, int] = (0, 0)
    mouse_hex_pos: Optional[Tuple[int, int]] = None
    keys_pressed: Set[int] = field(default_factory=set)
    mouse_pressed: Set[int] = field(default_factory=set)


@dataclass
class FogOfWar(SingletonComponent):
    """Singleton fog-of-war state."""

    faction_vision: Dict[Faction, Set[Tuple[int, int]]] = field(default_factory=dict)
    explored_tiles: Dict[Faction, Set[Tuple[int, int]]] = field(default_factory=dict)


@dataclass
class GameStats(SingletonComponent):
    """Singleton game statistics (data-only)."""

    # Faction stats
    faction_stats: Dict[Faction, Dict[str, int]] = field(default_factory=dict)

    # Battle history
    battle_history: List[Dict] = field(default_factory=list)

    # Turn history
    turn_history: List[Dict] = field(default_factory=list)

    # Unit observation history
    unit_observation_history: List[Dict] = field(default_factory=list)

    # Game-mode specific stats
    game_mode_stats: Dict[str, any] = field(default_factory=dict)

    # Game start time
    game_start_time: float = 0.0

    # Total game time (real-time mode)
    total_game_time: float = 0.0
    
    # 🆕 Initial unit counts
    initial_unit_counts: Dict[Faction, int] = field(default_factory=dict)

    # 🆕 Action counts: Agent -> ENV submitted actions
    # By agent (agent_id -> count)
    action_counts_by_agent: Dict[str, int] = field(default_factory=dict)
    # By faction (Faction -> count)
    action_counts_by_faction: Dict[Faction, int] = field(default_factory=dict)
    # 🆕 Agent-to-faction mapping (for faction aggregation)
    agent_id_to_faction: Dict[str, Faction] = field(default_factory=dict)

    # 🆕 Interaction counts: Agent -> ENV message packets (one packet = one interaction)
    # By agent (agent_id -> message count)
    interaction_counts_by_agent: Dict[str, int] = field(default_factory=dict)
    # By faction (Faction -> message count)
    interaction_counts_by_faction: Dict[Faction, int] = field(default_factory=dict)

    # 🆕 Strategy scoring stats
    strategy_scores_by_faction: Dict[Faction, float] = field(default_factory=dict)
    strategy_ping_count_by_faction: Dict[Faction, int] = field(default_factory=dict)
    strategy_evidence: Dict[Faction, List[str]] = field(default_factory=dict)
    last_strategy_ping_ts: Dict[Faction, float] = field(default_factory=dict)

    # 🆕 Map metadata
    map_info: Dict[str, any] = field(default_factory=dict)
    # Includes:
    # - map_width: int - map width
    # - map_height: int - map height
    # - map_type: str - generation type/mode (e.g., "river_split", "diagonal")
    # - competitive_mode: bool - whether competitive mode is enabled
    # - map_seed: int - RNG seed used for generation
    # - spawn_positions: Dict[Faction, Tuple[int, int]] - faction spawn positions
    # - coordinate_system: str - coordinate system ("centered" uses (0,0) as center; "offset" starts top-left)
    # - symmetry_type: str - symmetry type
    # - generation_timestamp: float - generation timestamp

    # 🆕 LLM API interaction stats
    llm_api_stats: Dict[Faction, Dict[str, any]] = field(default_factory=dict)
    # Includes:
    # - total_calls: int - total calls
    # - successful_calls: int - successful calls
    # - failed_calls: int - failed calls
    # - success_rate: float - success rate
    # - provider: str - LLM provider
    # - model_id: str - model id
    # - timestamp: float - last update timestamp
    
    # 🆕 Settlement report generation gate
    can_generate_settlement_report: bool = False  # Whether settlement report can be generated
    
    # 🆕 LLM stats collection counters (multi-agent)
    expected_llm_stats_count: int = 0
    received_llm_stats_count: int = 0

    # 🆕 Registered/received sets (use sets instead of counters to avoid races)
    registered_factions: Set[Faction] = field(default_factory=set)
    received_llm_stats_factions: Set[Faction] = field(default_factory=set)