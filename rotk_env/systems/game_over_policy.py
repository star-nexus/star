"""Single game-over policy for turn-based and real-time modes."""

from dataclasses import dataclass
from typing import Optional, Set

from framework import World
from framework.engine.events import EBS

from ..components import (
    GameModeComponent,
    GameState,
    GameTime,
    Unit,
    UnitCount,
)
from ..prefabs.config import Faction, GameConfig, GameMode
from ..utils.env_events import GameOverEvent

REASON_ANNIHILATION = "annihilation"
REASON_MUTUAL_ANNIHILATION = "mutual_annihilation"
REASON_TIMEOUT = "timeout"


@dataclass(frozen=True)
class GameOverOutcome:
    over: bool
    winner: Optional[Faction] = None
    reason: Optional[str] = None


class GameOverPolicy:
    """Win by annihilation, lose by being wiped, draw on mutual wipe or timeout.

    Timeout: turn-based when turn_number exceeds max_turns (default 100);
    real-time when GameTime.game_elapsed_time reaches MAX_REALTIME_SECONDS
    (default 3600). Timeout is always a draw; leftover units are not scored.
    """

    def __init__(self, world: World):
        self.world = world

    def living_factions(self) -> Set[Faction]:
        living: Set[Faction] = set()
        for entity in self.world.query().with_all(Unit, UnitCount).entities():
            unit = self.world.get_component(entity, Unit)
            unit_count = self.world.get_component(entity, UnitCount)
            if unit and unit_count and unit_count.current_count > 0:
                living.add(unit.faction)
        return living

    def evaluate(self) -> GameOverOutcome:
        game_state = self.world.get_singleton_component(GameState)
        if not game_state:
            return GameOverOutcome(over=False)
        if game_state.game_over:
            return GameOverOutcome(
                over=True,
                winner=game_state.winner,
                reason=getattr(game_state, "end_reason", None),
            )

        living = self.living_factions()
        if len(living) == 0:
            return GameOverOutcome(
                over=True, winner=None, reason=REASON_MUTUAL_ANNIHILATION
            )
        if len(living) == 1:
            return GameOverOutcome(
                over=True,
                winner=next(iter(living)),
                reason=REASON_ANNIHILATION,
            )
        if self._timed_out(game_state):
            return GameOverOutcome(over=True, winner=None, reason=REASON_TIMEOUT)
        return GameOverOutcome(over=False)

    def apply(self) -> bool:
        """Write GameState if the match is over. Returns True when over."""
        outcome = self.evaluate()
        if not outcome.over:
            return False

        game_state = self.world.get_singleton_component(GameState)
        if game_state and not game_state.game_over:
            game_state.game_over = True
            game_state.winner = outcome.winner
            game_state.end_reason = outcome.reason
            EBS.publish(GameOverEvent(winner=outcome.winner))
        return True

    def _current_mode(self, game_state: GameState) -> GameMode:
        mode_comp = self.world.get_singleton_component(GameModeComponent)
        if mode_comp:
            return mode_comp.mode
        return game_state.game_mode

    def _timed_out(self, game_state: GameState) -> bool:
        mode = self._current_mode(game_state)
        if mode == GameMode.TURN_BASED:
            max_turns = game_state.max_turns or GameConfig.MAX_TURNS
            return game_state.turn_number > max_turns
        if mode == GameMode.REAL_TIME:
            game_time = self.world.get_singleton_component(GameTime)
            elapsed = game_time.game_elapsed_time if game_time else 0.0
            return elapsed >= GameConfig.MAX_REALTIME_SECONDS
        return False
