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
        "Human Commander vs AI Strategist",
    ),
    (
        {Faction.WEI: PlayerType.AI, Faction.SHU: PlayerType.AI},
        "AI vs AI Slots",
    ),
    (
        {
            Faction.WEI: PlayerType.HUMAN,
            Faction.SHU: PlayerType.AI,
            Faction.WU: PlayerType.AI,
        },
        "Human Wei vs Shu & Wu AI",
    ),
    (
        {
            Faction.WEI: PlayerType.AI,
            Faction.SHU: PlayerType.AI,
            Faction.WU: PlayerType.AI,
        },
        "Three Kingdoms - All AI/Agent (Benchmark)",
    ),
)

CONTROLLER_NONE = "none"
CONTROLLER_MOCK_AI = "mock_ai"
CONTROLLER_HUB = "hub"

START_CONTROLLER_OPTIONS = (
    (CONTROLLER_NONE, "No Controller (Static AI Slots)"),
    (CONTROLLER_MOCK_AI, "Local Rule BOT (MockLLMAISystem)"),
    (CONTROLLER_HUB, "External Agent / Hub"),
)


def controller_backend_flags(backend: str) -> tuple[bool, bool]:
    """Return (enable_mock_ai, use_hub) for a start-menu backend choice."""
    if backend == CONTROLLER_MOCK_AI:
        return True, False
    if backend == CONTROLLER_HUB:
        return False, True
    return False, False


def start_panel_layout(
    catalog_len: int = 0,
    screen_width: int | None = None,
    screen_height: int | None = None,
) -> Dict[str, int]:
    """Shared geometry for start-scene render and click hit-testing."""
    if screen_width is None:
        screen_width = GameConfig.WINDOW_WIDTH
    if screen_height is None:
        screen_height = GameConfig.WINDOW_HEIGHT
    catalog_len = max(0, int(catalog_len))
    total_rows = (
        catalog_len + START_SCENARIO_COLS - 1
    ) // START_SCENARIO_COLS
    panel_x = (screen_width - START_PANEL_WIDTH) // 2
    panel_y = 170
    player_y = panel_y + 145
    player_option_y = player_y + 60

    # Controller backend is a separate section below the topology choices.
    last_player_bottom = (
        player_option_y + (len(START_PLAYER_OPTIONS) - 1) * 45 + 30
    )
    controller_y = last_player_bottom + 18
    controller_option_y = controller_y + 45
    controller_spacing = 34
    last_controller_bottom = (
        controller_option_y
        + (len(START_CONTROLLER_OPTIONS) - 1) * controller_spacing
        + 28
    )

    scenario_y = last_controller_bottom + 18
    scenario_option_y = scenario_y + 40
    content_h = (
        scenario_option_y
        - panel_y
        + 25
        + max(1, total_rows) * START_SCENARIO_ROW_H
    )
    panel_height = max(1, min(screen_height - panel_y - 170, content_h))
    clip_bottom = panel_y + panel_height - 8
    visible_h = max(0, clip_bottom - scenario_option_y)
    visible_rows = visible_h // START_SCENARIO_ROW_H
    return {
        "panel_x": panel_x,
        "panel_y": panel_y,
        "panel_width": START_PANEL_WIDTH,
        "panel_height": panel_height,
        "mode_y": panel_y + 24,
        "player_y": player_y,
        "controller_y": controller_y,
        "controller_option_y": controller_option_y,
        "controller_spacing": controller_spacing,
        "scenario_y": scenario_y,
        "scenario_option_y": scenario_option_y,
        "scenario_clip_bottom": clip_bottom,
        "scenario_visible_rows": visible_rows,
        "scenario_total_rows": total_rows,
        "scenario_row_h": START_SCENARIO_ROW_H,
        "scenario_col_w": START_SCENARIO_COL_W,
        "scenario_cols": START_SCENARIO_COLS,
    }


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
