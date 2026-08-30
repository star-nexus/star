"""Assemble a skirmish World without going through GameEngine.

GameScene, pytest, and ``--headless --no-hub`` share this builder so the
system list and opening setup stay one copy. ``hub_url=None`` installs an
offline ``LLMSystem`` that never opens a websocket.

This assembler is the current eval match: annihilate the enemy on one map.
TerritorySystem, RandomEventSystem, ConstructionPoints, and SkillPoints stay
in ENV for other scenes; they are not mounted here. Map tiles are terrain
only — no TerritoryControl.
"""

from __future__ import annotations

import os
import time
from typing import Dict, Literal, Optional

from framework import World

from ..components import (
    AIControlled,
    ActionPoints,
    BattleLog,
    Combat,
    FogOfWar,
    GameModeComponent,
    GameModeStatistics,
    GameState,
    GameStats,
    HexPosition,
    InputState,
    MapData,
    MatchRules,
    MovementPoints,
    Player,
    RngService,
    TurnManager,
    UIState,
    Unit,
    UnitCount,
    UnitSkills,
    UnitStatus,
    VisibilityTracker,
    Vision,
    formation_center,
    resolve_seed,
)
from ..components.agent_info import AgentInfoRegistry
from ..prefabs.action_catalog import match_game_actions
from ..prefabs.config import (
    Faction,
    GameConfig,
    GameMode,
    PlayerType,
    UnitType,
)
from ..systems.combat_system import CombatSystem
from ..systems.game_time_system import GameTimeSystem
from ..systems.llm_system import LLMSystem
from ..systems.map_system import MapSystem
from ..systems.mock_llm_ai_system import MockLLMAISystem
from ..systems.movement_system import MovementSystem
from ..systems.realtime_system import RealtimeSystem
from ..systems.resource_recovery_system import ResourceRecoverySystem
from ..systems.settlement_report_system import SettlementReportSystem
from ..systems.statistics_system import StatisticsSystem
from ..systems.turn_system import TurnSystem
from ..systems.vision_system import VisionSystem

DEFAULT_HUB_URL = "ws://localhost:8000/ws/metaverse"

DisplayKind = Literal["none", "dummy", "window"]


def build_skirmish_world(
    *,
    players: Optional[Dict[Faction, PlayerType]] = None,
    mode: GameMode | str = GameMode.TURN_BASED,
    scenario: str = "default",
    seed: Optional[int] = None,
    seed_source: str = "default",
    hub_url: Optional[str] = None,
    env_id: Optional[str] = None,
    display: DisplayKind = "none",
    world: Optional[World] = None,
) -> World:
    """Build a match World.

    ``display``:
      * ``none`` — rules systems only (pytest). No pygame input/render/animation.
      * ``dummy`` — same as ``GameScene`` with ``--headless`` (input + animation,
        no render systems).
      * ``window`` — full interactive system list.

    ``hub_url=None`` keeps ``LLMSystem`` offline. Pass ``DEFAULT_HUB_URL``
    (or another websocket URL) to attach to a Hub.
    """
    if isinstance(mode, str):
        try:
            mode = GameMode(mode)
        except ValueError:
            mode = GameMode.TURN_BASED
    if players is None:
        players = {Faction.WEI: PlayerType.HUMAN, Faction.SHU: PlayerType.AI}

    assembler = _SkirmishAssembler(
        world=world or World(),
        players=players,
        game_mode=mode,
        scenario=scenario,
        seed=seed,
        seed_source=seed_source,
        hub_url=hub_url,
        env_id=env_id,
        display=display,
    )
    assembler.assemble()
    return assembler.world


class _SkirmishAssembler:
    def __init__(
        self,
        world: World,
        players: Dict[Faction, PlayerType],
        game_mode: GameMode,
        scenario: str,
        seed: Optional[int],
        seed_source: str,
        hub_url: Optional[str],
        env_id: Optional[str],
        display: DisplayKind,
    ):
        self.world = world
        self.players = players
        self.game_mode = game_mode
        self.scenario = scenario
        self.seed = seed
        self.seed_source = seed_source
        self.hub_url = hub_url
        self.env_id = env_id
        self.display = display
        self._temp_initial_unit_counts: Dict[Faction, int] = {}

    def assemble(self) -> None:
        self._initialize_game_mode()
        self._initialize_rng()
        self._initialize_agent_registry()
        self._initialize_systems()
        self._initialize_players()
        self._initialize_units()
        self._initialize_stats()
        self._refresh_opening_vision()

    def _initialize_game_mode(self) -> None:
        self.world.add_singleton_component(GameModeComponent(mode=self.game_mode))
        self.world.add_singleton_component(
            MatchRules(
                game_actions=match_game_actions(
                    turn_based=self.game_mode == GameMode.TURN_BASED
                )
            )
        )

    def _initialize_rng(self) -> None:
        import tomllib

        config_seed = None
        try:
            config_path = ".configs.toml"
            if os.path.exists(config_path):
                with open(config_path, "rb") as f:
                    cfg = tomllib.load(f)
                config_seed = cfg.get("default", {}).get("seed")
        except Exception as e:
            print(f"[WorldBuilder] Failed to read seed from .configs.toml: {e}")

        seed = resolve_seed(cli_seed=self.seed, config_seed=config_seed)
        source = self.seed_source
        if source == "default":
            if self.seed is not None:
                source = "kwargs"
            elif "STAR_SEED" in os.environ:
                source = "env"
            elif config_seed is not None:
                source = "config"
            else:
                source = "wallclock"

        self.world.add_singleton_component(RngService(seed=seed, source=source))
        print(f"[WorldBuilder] RngService initialized: seed={seed} source={source}")

    def _initialize_agent_registry(self) -> None:
        self.world.add_singleton_component(AgentInfoRegistry())

    def _initialize_systems(self) -> None:
        systems = [
            GameTimeSystem(),
            MapSystem(scenario=self.scenario),
            VisionSystem(),
            MovementSystem(),
            CombatSystem(),
            ResourceRecoverySystem(),
            MockLLMAISystem(),
            LLMSystem(server_url=self.hub_url, env_id=self.env_id),
            StatisticsSystem(),
            SettlementReportSystem(),
        ]
        # Display-dependent systems are imported here, not at module scope:
        # they pull in pygame, and `display="none"` (the eval path) mounts none
        # of them. A module-level import would put SDL in every headless run.
        if self.display in ("dummy", "window"):
            from ..systems.animation_system import AnimationSystem
            from ..systems.input_system import InputHandlingSystem

            systems.extend([AnimationSystem(), InputHandlingSystem()])
        if self.display == "window":
            # Compatibility-named optimized renderers preserve legacy UI helpers
            # that discover systems by class name.
            from ..systems.optimized_render_systems import (
                EffectRenderSystem,
                MapRenderSystem,
                MiniMapSystem,
                UnitRenderSystem,
            )
            from ..systems.panel_render_system import PanelRenderSystem
            from ..systems.ui_button_system import UIButtonSystem
            from ..systems.ui_render_system import UIRenderSystem
            from ..systems.unit_action_button_system import UnitActionButtonSystem

            systems.extend(
                [
                    UnitActionButtonSystem(),
                    UIButtonSystem(),
                    MapRenderSystem(),
                    UnitRenderSystem(),
                    EffectRenderSystem(),
                    PanelRenderSystem(),
                    UIRenderSystem(),
                    MiniMapSystem(),
                ]
            )
        if self.game_mode == GameMode.REAL_TIME:
            systems.append(RealtimeSystem())
        else:
            systems.append(TurnSystem())
        for system in systems:
            self.world.add_system(system)

    def _initialize_players(self) -> None:
        turn_manager = TurnManager()
        self.world.add_singleton_component(turn_manager)
        for faction, player_type in self.players.items():
            player_entity = self.world.create_entity()
            self.world.add_component(
                player_entity,
                Player(
                    faction=faction,
                    player_type=player_type,
                    color=GameConfig.FACTION_COLORS[faction],
                    units=set(),
                ),
            )
            if player_type == PlayerType.AI:
                self.world.add_component(player_entity, AIControlled())
            turn_manager.add_player(player_entity)

    def _initialize_units(self) -> None:
        map_data = self.world.get_singleton_component(MapData)
        formations = map_data.formations if map_data else {}
        loadout = map_data.formation_unit_types if map_data else {}

        self._temp_initial_unit_counts = {}
        for faction in self.players.keys():
            cells = list(formations.get(faction) or [])
            types = list(loadout.get(faction) or [])
            if len(types) < len(cells):
                types = types + [UnitType.INFANTRY] * (len(cells) - len(types))
            self._temp_initial_unit_counts[faction] = len(cells)

            if map_data is not None and cells:
                map_data.home_bases[faction] = formation_center(cells)

            if not cells:
                continue
            player_entity = self._get_player_entity(faction)
            if not player_entity:
                continue
            player = self.world.get_component(player_entity, Player)
            for i, ((q, r), unit_type) in enumerate(zip(cells, types)):
                unit_entity = self._create_unit(
                    faction=faction,
                    unit_type=unit_type,
                    position=(q, r),
                    name=f"{faction.value}_{unit_type.value}_{i+1}",
                )
                player.units.add(unit_entity)

    def _create_unit(
        self, faction: Faction, unit_type: UnitType, position: tuple, name: str = ""
    ) -> int:
        unit_entity = self.world.create_entity()
        unit_stats = GameConfig.UNIT_STATS[unit_type]
        self.world.add_component(
            unit_entity, Unit(unit_type=unit_type, faction=faction, name=name)
        )
        self.world.add_component(unit_entity, HexPosition(position[0], position[1]))
        self.world.add_component(
            unit_entity,
            UnitCount(
                current_count=unit_stats.max_count, max_count=unit_stats.max_count
            ),
        )
        self.world.add_component(
            unit_entity,
            MovementPoints(
                base_mp=unit_stats.movement,
                current_mp=unit_stats.movement,
                max_mp=unit_stats.movement,
            ),
        )
        game_mode_comp = self.world.get_singleton_component(GameModeComponent)
        is_turn_based = game_mode_comp and game_mode_comp.mode == GameMode.TURN_BASED
        ap = 2 if is_turn_based else 1
        self.world.add_component(
            unit_entity, ActionPoints(current_ap=ap, max_ap=ap)
        )
        self.world.add_component(
            unit_entity,
            Combat(
                base_attack=unit_stats.base_attack,
                base_defense=unit_stats.base_defense,
                attack_range=unit_stats.attack_range,
            ),
        )
        self.world.add_component(unit_entity, Vision(range=unit_stats.vision_range))
        self.world.add_component(unit_entity, UnitStatus(current_status="normal"))
        self.world.add_component(unit_entity, UnitSkills())
        return unit_entity

    def _get_player_entity(self, faction: Faction) -> Optional[int]:
        for entity in self.world.query().with_component(Player).entities():
            player = self.world.get_component(entity, Player)
            if player and player.faction == faction:
                return entity
        return None

    def _initialize_stats(self) -> None:
        stats = GameStats()
        stats.game_start_time = time.time()
        stats.initial_unit_counts = self._temp_initial_unit_counts.copy()
        self.world.add_singleton_component(stats)

        battle_log = BattleLog()
        battle_log.add_entry("Game Start", "turn", "", (0, 255, 0))
        battle_log.add_entry("Wei Faction Turn Start", "turn", "wei", (255, 100, 100))
        self.world.add_singleton_component(battle_log)
        self.world.add_singleton_component(VisibilityTracker())
        self.world.add_singleton_component(
            GameModeStatistics(current_mode=self.game_mode.value)
        )

        first_faction = list(self.players.keys())[0] if self.players else Faction.WEI
        self.world.add_singleton_component(
            GameState(
                current_player=first_faction,
                turn_number=1,
                game_mode=self.game_mode,
                game_over=False,
                winner=None,
                max_turns=GameConfig.MAX_TURNS,
            )
        )
        if self.world.get_singleton_component(UIState) is None:
            self.world.add_singleton_component(UIState())
        if self.world.get_singleton_component(InputState) is None:
            self.world.add_singleton_component(InputState())
        if self.world.get_singleton_component(FogOfWar) is None:
            self.world.add_singleton_component(FogOfWar())

        try:
            for system in self.world.systems:
                if hasattr(system, "_save_map_info_to_stats"):
                    system._save_map_info_to_stats()
                    break
        except Exception as e:
            print(f"[WorldBuilder] Failed to backfill map_info into GameStats: {e}")

    def _refresh_opening_vision(self) -> None:
        """Compute FogOfWar before the first tick so get_faction_state is not empty."""
        for system in self.world.systems:
            if isinstance(system, VisionSystem):
                system.update(0.0)
                break
