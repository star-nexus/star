"""Start scene components."""

from dataclasses import dataclass, field
from typing import Dict, Any, List
from rotk_env.maps.map_file import map_catalog
from ..prefabs.config import Faction, GameConfig, PlayerType, GameMode
from framework import SingletonComponent

START_PANEL_WIDTH = 600
START_SCENARIO_COLS = 2
START_SCENARIO_ROW_H = 32
START_SCENARIO_COL_W = 270

# Player topology and controller backend are deliberately orthogonal.
# A PlayerType.AI slot describes who may control that faction; it does not
# imply that the built-in MockLLMAISystem should run.  This mirrors the CLI,
# where --players and --mock-ai/Hub selection are separate switches.
START_PLAYER_OPTIONS = (
    (
        {Faction.WEI: PlayerType.HUMAN, Faction.SHU: PlayerType.AI},
        "Human Wei vs Agent Shu",
    ),
    (
        {Faction.WEI: PlayerType.AI, Faction.SHU: PlayerType.AI},
        "Two Agent factions",
    ),
    (
        {
            Faction.WEI: PlayerType.HUMAN,
            Faction.SHU: PlayerType.AI,
            Faction.WU: PlayerType.AI,
        },
        "Human Wei vs Shu & Wu Agents",
    ),
    (
        {
            Faction.WEI: PlayerType.AI,
            Faction.SHU: PlayerType.AI,
            Faction.WU: PlayerType.AI,
        },
        "Three Agent factions (Benchmark)",
    ),
)

CONTROLLER_NONE = "none"
CONTROLLER_MOCK_AI = "mock_ai"
CONTROLLER_HUB = "hub"

START_CONTROLLER_OPTIONS = (
    (CONTROLLER_NONE, "Static slots — no controller"),
    (CONTROLLER_MOCK_AI, "Local rule BOT"),
    (CONTROLLER_HUB, "External Agent / Hub"),
)


def controller_backend_flags(backend: str) -> tuple[bool, bool]:
    """Return (enable_mock_ai, use_hub) for a start-menu backend choice."""
    if backend == CONTROLLER_MOCK_AI:
        return True, False
    if backend == CONTROLLER_HUB:
        return False, True
    return False, False


def clamp_scenario_scroll(scroll: int, catalog_len: int, geom: Dict[str, int]) -> int:
    total_rows = int(geom["scenario_total_rows"])
    visible_rows = int(geom["scenario_visible_rows"])
    max_scroll = max(0, total_rows - visible_rows)
    return min(max_scroll, max(0, int(scroll)))


@dataclass
class StartMenuConfig(SingletonComponent):
    """Start menu configuration component."""

    selected_mode: GameMode = GameMode.TURN_BASED
    selected_players: Dict[Faction, PlayerType] = field(
        default_factory=lambda: {
            Faction.WEI: PlayerType.HUMAN,
            Faction.SHU: PlayerType.AI,
        }
    )
    # Match CLI semantics by default: AI slots exist but have no implicit
    # local controller.  The user must explicitly choose Rule BOT or Hub.
    selected_controller_backend: str = CONTROLLER_NONE
    selected_scenario: str = "default"
    scenario_catalog: List[Dict[str, Any]] = field(default_factory=map_catalog)
    scenario_scroll: int = 0


@dataclass
class StartMenuButtons(SingletonComponent):
    """Start menu button component."""

    buttons: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    options: Dict[str, Dict[str, Any]] = field(default_factory=dict)


@dataclass
class StartMenuOptions(SingletonComponent):
    """Start menu options component."""

    mode_options: List[Dict[str, Any]] = field(default_factory=list)
    player_options: List[Dict[str, Any]] = field(default_factory=list)
    controller_options: List[Dict[str, Any]] = field(default_factory=list)
    scenario_options: List[Dict[str, Any]] = field(default_factory=list)
