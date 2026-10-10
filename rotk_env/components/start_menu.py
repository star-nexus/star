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


def start_panel_layout(catalog_len=0, screen_width=None, screen_height=None) -> Dict[str, Any]:
    """Measured layout and shared hit rectangles; no independent UI offsets."""
    import pygame
    pygame.font.init()
    w = screen_width or GameConfig.WINDOW_WIDTH
    h = screen_height or GameConfig.WINDOW_HEIGHT
    scale = min(1.25, max(1., min(w/1200, h/800)))
    line = max(32, pygame.font.Font(None, round(18*scale)).get_linesize()+14)
    width = min(round(880*scale), w-80)
    height = min(round(590*scale), h-180)
    x, y = (w-width)//2, max(124, (h-height)//2)
    left, right = x+28, x+width//2+20
    mode_y, player_y = y+24, y+24
    controller_y = y+150
    scenario_y = y+310
    option_y = scenario_y+34
    clip_bottom = y+height-96
    visible_rows = max(1, (clip_bottom-option_y)//line)
    col_w = (width-56)//2
    row_rect = lambda xx, yy, ww: pygame.Rect(xx, yy, ww, line-4)
    return dict(panel_x=x, panel_y=y, panel_width=width, panel_height=height,
        mode_y=mode_y, player_y=player_y, controller_y=controller_y,
        controller_option_y=controller_y+34, controller_spacing=line,
        mode_rects=[row_rect(left, mode_y+34+i*line, width//2-48) for i in range(2)],
        player_rects=[row_rect(right, player_y+34+i*line, width//2-48) for i in range(4)],
        controller_rects=[row_rect(left, controller_y+34+i*line, width-56) for i in range(3)],
        scenario_y=scenario_y, scenario_option_y=option_y,
        scenario_clip_bottom=clip_bottom, scenario_visible_rows=visible_rows,
        scenario_total_rows=(max(0,catalog_len)+1)//2, scenario_row_h=line,
        scenario_col_w=col_w, scenario_cols=2,
        scenario_clip=pygame.Rect(left, option_y, width-56, max(line,clip_bottom-option_y)),
        start_rect=pygame.Rect(x+width-276, y+height-57, 164, 36),
        quit_rect=pygame.Rect(x+width-100, y+height-57, 72, 36),
        summary_rect=pygame.Rect(left, y+height-85, width-56, 22))


def scenario_option_rects(config, geom):
    import pygame
    scroll = clamp_scenario_scroll(config.scenario_scroll, len(config.scenario_catalog or []), geom)
    rects = []
    for i, item in enumerate(config.scenario_catalog or []):
        row = i//2-scroll
        if 0 <= row < geom['scenario_visible_rows']:
            rects.append((i, pygame.Rect(geom['panel_x']+28+(i%2)*geom['scenario_col_w'],
                geom['scenario_option_y']+row*geom['scenario_row_h'],
                geom['scenario_col_w']-12, geom['scenario_row_h']-4)))
    return rects


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
