"""
Main game scene
"""

from typing import Dict, Any
from framework.engine.scenes import Scene, SMS
from framework import World
from ..components.settlement_report import SettlementReport
from ..components import GameState, MapData, Unit, UnitCount
from ..prefabs.config import Faction, GameConfig, PlayerType, GameMode
from ..prefabs.world_builder import DEFAULT_HUB_URL, build_skirmish_world
from performance_profiler import profiler


class GameScene(Scene):
    """Main game scene"""

    def __init__(self, engine):
        super().__init__(engine)
        self.name = "game"
        self.world = World()

        # Default configuration, will be overridden in enter
        self.players = {Faction.WEI: PlayerType.HUMAN, Faction.SHU: PlayerType.AI}
        self.game_mode = GameMode.TURN_BASED  # Default game mode
        self.enable_mock_ai = False

        # Initialization flag
        self.initialized = False

        # Game end waiting state
        self.game_end_wait_start = None
        self.game_end_wait_timeout = 60.0
        self._headless_exit_triggered = False

    def enter(self, **kwargs):
        """Called when entering the scene"""
        super().enter(**kwargs)

        self.players = kwargs.get(
            "players", {Faction.WEI: PlayerType.HUMAN, Faction.SHU: PlayerType.AI}
        )

        mode = kwargs.get("mode", GameMode.TURN_BASED)
        if isinstance(mode, str):
            try:
                mode = GameMode(mode)
            except ValueError:
                mode = GameMode.TURN_BASED
        self.game_mode = mode

        headless = kwargs.get("headless", False)
        self.headless = headless
        self.scenario = kwargs.get("scenario", "default")
        self.seed = kwargs.get("seed", None)
        self.seed_source = kwargs.get("seed_source", "default")
        # Explicit None (from --no-hub) stays offline. Missing key (start UI)
        # still attaches to the default local Hub.
        self.hub_url = kwargs["hub_url"] if "hub_url" in kwargs else DEFAULT_HUB_URL
        self.env_id = kwargs.get("env_id")
        self.enable_mock_ai = bool(kwargs.get("enable_mock_ai", False))

        if not self.initialized:
            self._initialize_game()
            self.initialized = True

    def _initialize_game(self):
        """Fill this scene's World through the shared skirmish builder."""
        display = "dummy" if self.headless else "window"
        build_skirmish_world(
            players=self.players,
            mode=self.game_mode,
            scenario=self.scenario,
            seed=self.seed,
            seed_source=self.seed_source,
            hub_url=self.hub_url,
            env_id=self.env_id,
            display=display,
            enable_mock_ai=self.enable_mock_ai,
            world=self.world,
        )

        # Scale-up experiments need the workload attached to every profiler
        # snapshot; otherwise an FPS number is meaningless without map/unit size.
        map_data = self.world.get_singleton_component(MapData)
        initial_units = len(self.world.query().with_component(Unit).entities())
        mode_label = (
            self.game_mode.value if hasattr(self.game_mode, "value") else str(self.game_mode)
        )
        players_label = ",".join(
            f"{getattr(faction, 'value', faction)}:{getattr(player_type, 'value', player_type)}"
            for faction, player_type in sorted(
                self.players.items(), key=lambda item: str(getattr(item[0], "value", item[0]))
            )
        )
        metadata = {
            "mode": mode_label,
            "scenario": self.scenario,
            "players": players_label,
            "initial_units": initial_units,
            "display": display,
            "mock_ai": self.enable_mock_ai,
        }
        if map_data is not None:
            metadata.update(
                map_id=map_data.map_id or self.scenario,
                map_size=f"{map_data.width}x{map_data.height}",
                map_tiles=len(map_data.tiles),
            )
        profiler.set_metadata(**metadata)

        # Drop menu/scene-switch/map-initialization frames. reset() preserves
        # metadata and profiling switches, so subsequent samples describe only
        # steady gameplay. If this is called during an engine frame, that
        # transition frame is intentionally discarded and timing resumes on the
        # next start_frame().
        if profiler.enabled:
            profiler.reset()

    def update(self, delta_time: float) -> None:
        """Update scene"""
        if self.is_active:
            GameConfig.sync_from_display()
            # Quit is handled by GameEngine.InputSystem (QuitEvent).
            # Do not drain pygame.event here — get() empties the queue.
            with profiler.time_system("world_update", category="update"):
                self.world.update(delta_time)

            game_state = self.world.get_singleton_component(GameState)
            if game_state and game_state.game_over:
                if self.game_end_wait_start is None:
                    import time

                    self.game_end_wait_start = time.time()
                    print("[GameScene] Game end, waiting for settlement report...")

                settlement_report = self.world.get_singleton_component(SettlementReport)
                if settlement_report:
                    print(
                        "[GameScene] Settlement report generated, switching to game over scene"
                    )
                    self._switch_to_game_over(game_state)
                else:
                    import time

                    elapsed = time.time() - self.game_end_wait_start
                    if elapsed >= self.game_end_wait_timeout:
                        print(
                            f"[GameScene] Waiting for settlement report timeout ({elapsed:.1f}s), switching to game over scene"
                        )
                        self._switch_to_game_over(game_state)
                    else:
                        if int(elapsed) != getattr(self, "_last_wait_second", -1):
                            remaining = self.game_end_wait_timeout - elapsed
                            print(
                                f"[GameScene] Waiting for settlement report generation... {elapsed:.1f}s / {self.game_end_wait_timeout}s (remaining {remaining:.1f}s)"
                            )
                            self._last_wait_second = int(elapsed)

    def _switch_to_game_over(self, game_state):
        """Switch to game over scene"""
        statistics = self._collect_game_statistics()

        if self.headless:
            print(f"Game End, Winner: {game_state.winner}, \nStatistics: {statistics}")
            if not self._headless_exit_triggered:
                self._headless_exit_triggered = True
                print("[GameScene] Headless mode: Stopping game loop...")
                self.engine.stop(None)
        else:
            SMS.switch_to("game_over", winner=game_state.winner, statistics=statistics)

    def _collect_game_statistics(self) -> Dict[str, Any]:
        """Collect game statistics data"""
        from ..components import GameTime, GameState

        total_units = 0
        surviving_units = 0
        faction_stats = {}

        for faction in [Faction.WEI, Faction.SHU, Faction.WU]:
            faction_total = 0
            faction_surviving = 0

            for entity in self.world.query().with_component(Unit).entities():
                unit = self.world.get_component(entity, Unit)
                unit_count = self.world.get_component(entity, UnitCount)

                if unit.faction == faction:
                    faction_total += 1
                    total_units += 1

                    if unit_count and unit_count.current_count > 0:
                        faction_surviving += 1
                        surviving_units += 1

            if faction_total > 0:
                faction_stats[faction] = {
                    "total_units": faction_total,
                    "surviving_units": faction_surviving,
                }

        total_turns = 0
        game_duration = 0.0

        try:
            game_state = self.world.get_singleton_component(GameState)
            total_turns = game_state.turn_number

            game_time = self.world.get_singleton_component(GameTime)
            game_duration = game_time.get_game_elapsed_seconds()

        except Exception as e:
            print(f"Error occurred while retrieving game state: {e}")

        return {
            "total_turns": total_turns,
            "game_duration": game_duration,
            "total_units": total_units,
            "surviving_units": surviving_units,
            "faction_stats": faction_stats,
        }

    def exit(self):
        """Called when exiting scene"""
        super().exit()
        self.world.reset()
