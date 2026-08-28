"""
Game-state related singleton components.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Set, Tuple, Optional, List
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
    max_turns: int = 100
    # annihilation | mutual_annihilation | timeout. None while the match is running.
    end_reason: Optional[str] = None


@dataclass
class MapData(SingletonComponent):
    """Singleton map data."""

    width: int
    height: int
    tiles: Dict[Tuple[int, int], int] = field(
        default_factory=dict
    )  # (col,row) → tile entity id
    map_id: str = ""
    # Opening deployment cells from the map file, keyed by faction.
    formations: Dict[Faction, List[Tuple[int, int]]] = field(default_factory=dict)
    # One hex per faction: that side's home base (opening formation center).
    home_bases: Dict[Faction, Tuple[int, int]] = field(default_factory=dict)


HOME_BASES_MEANING = (
    "各阵营基地坐标（开局布阵中心），不是部队现在站的格子。"
    " Home-base hex of each faction: center of that side's opening formation, "
    "not live unit positions. Until enemies appear in enemies, "
    "march toward the opponent's home_base."
)


def formation_center(cells: List[Tuple[int, int]]) -> Tuple[int, int]:
    """Integer centroid of a blob of offset hexes."""
    if not cells:
        return (0, 0)
    n = len(cells)
    col = int(round(sum(c for c, _ in cells) / n))
    row = int(round(sum(r for _, r in cells) / n))
    return (col, row)


def board_axis_bounds(map_data: "MapData") -> tuple[int, int, int, int]:
    """Inclusive even-q range: col_min, col_max, row_min, row_max.

    Tile keys win when the board is populated. An empty ``tiles`` map falls
    back to the centered ASCII convention used by map files: col = j - width//2,
    row = height//2 - i.
    """
    if map_data.tiles:
        cols = [col for col, _row in map_data.tiles]
        rows = [row for _col, row in map_data.tiles]
        return min(cols), max(cols), min(rows), max(rows)
    half_w = int(map_data.width) // 2
    half_h = int(map_data.height) // 2
    return (
        -half_w,
        int(map_data.width) - half_w - 1,
        -(int(map_data.height) - half_h - 1),
        half_h,
    )


def map_briefing(map_data: Optional["MapData"]) -> Dict[str, Any]:
    """Public map sheet at join: size, axis bounds, and home-base hexes."""
    if map_data is None:
        return {
            "width": None,
            "height": None,
            "col_min": None,
            "col_max": None,
            "row_min": None,
            "row_max": None,
            "map_id": None,
            "home_bases": {},
            "home_bases_meaning": HOME_BASES_MEANING,
        }
    col_min, col_max, row_min, row_max = board_axis_bounds(map_data)
    home_bases: Dict[str, Dict[str, Any]] = {}
    for faction, cell in (map_data.home_bases or {}).items():
        key = faction.value if hasattr(faction, "value") else str(faction)
        home_bases[key] = {
            "col": int(cell[0]),
            "row": int(cell[1]),
            "kind": "home_base",
        }
    return {
        "width": int(map_data.width),
        "height": int(map_data.height),
        "col_min": col_min,
        "col_max": col_max,
        "row_min": row_min,
        "row_max": row_max,
        "map_id": map_data.map_id or None,
        "home_bases": home_bases,
        "home_bases_meaning": HOME_BASES_MEANING,
    }


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
    # Spectator camera: whose vision to draw when FogOfWar.enabled is True.
    # Not a fog switch — that lives only on FogOfWar.enabled.
    view_faction: Optional[Faction] = None


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
    # The only fog switch. Human, BOT, and agents all read this.
    # True: vision is the union of that faction's units.
    # False (key 1): the whole map is visible.
    # VisionSystem still maintains the tile sets so turning fog back on is instant.
    enabled: bool = True

    def explored_for(self, faction: Faction) -> Set[Tuple[int, int]]:
        return set(self.explored_tiles.get(faction, set()))

    def visible_for(self, faction: Faction) -> Set[Tuple[int, int]]:
        return set(self.faction_vision.get(faction, set()))


def set_fog_enabled(fog: Optional[FogOfWar], enabled: bool) -> None:
    """Write the single fog switch. Systems read FogOfWar.enabled; they do not
    keep a parallel flag on UIState.
    """
    if fog is not None:
        fog.enabled = bool(enabled)


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
    # - prompt_tokens / completion_tokens / reasoning_tokens
    # - prompt_cache_hit_tokens / prompt_cache_miss_tokens / cache_hit_rate
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