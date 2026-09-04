"""Window realtime system using indexed living-faction counts."""

from __future__ import annotations

from ..utils.unit_spatial_index import get_unit_spatial_index
from .game_over_policy import GameOverPolicy
from .realtime_system import RealtimeSystem as _BaseRealtimeSystem


class _IndexedGameOverPolicy(GameOverPolicy):
    def living_factions(self):
        index = get_unit_spatial_index(self.world)
        if index is not None:
            return index.living_factions()
        return super().living_factions()


class RealtimeSystem(_BaseRealtimeSystem):
    """Avoid a full Unit/UnitCount scan on every real-time frame."""

    def initialize(self, world) -> None:
        self.world = world
        self._game_over_policy = _IndexedGameOverPolicy(world)
