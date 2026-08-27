"""
Vision system - handles fog of war and line-of-sight calculation.

Performance: per-unit visibility is the most expensive O(units × range^2 × LOS)
loop in the frame. Most ticks however have *no movement* — units recompute
the same tile set every frame. This system therefore keeps a per-unit cache
on the `Vision` component (`_last_observed_pos`, `_last_range`, `dirty`) and
skips the raycasting work when nothing relevant has changed; only the cheap
faction-level union still runs every tick.

Cache invalidation rules:
  * unit moved (HexPosition changed) → recompute
  * `Vision.range` changed → recompute
  * `Vision.dirty == True` → recompute (used after terrain edits that change LOS)
"""

from typing import Set, Tuple
from framework import System, World
from ..components import HexPosition, Vision, Unit, FogOfWar, MapData, Terrain
from ..utils.hex_utils import HexMath


class VisionSystem(System):
    """Vision system - handles fog of war and line-of-sight calculation."""

    def __init__(self):
        super().__init__(required_components={HexPosition, Vision, Unit})
        # Performance counters; exposed via `get_stats()` for profiling.
        self._stat_recomputes = 0
        self._stat_cache_hits = 0

    def initialize(self, world: World) -> None:
        self.world = world

    def subscribe_events(self):
        pass

    def update(self, delta_time: float) -> None:
        """Update vision system."""
        self._update_fog_of_war()

    def invalidate_all(self) -> None:
        """Force every unit's vision to recompute on the next tick.

        Call this after a terrain edit that could change line-of-sight
        (e.g. demolishing a mountain) — otherwise stale `visible_tiles`
        would persist on units that did not move.
        """
        for entity in self.world.query().with_component(Vision).entities():
            vision = self.world.get_component(entity, Vision)
            if vision is not None:
                vision.dirty = True

    def get_stats(self) -> dict:
        total = self._stat_recomputes + self._stat_cache_hits
        return {
            "recomputes": self._stat_recomputes,
            "cache_hits": self._stat_cache_hits,
            "hit_rate": (self._stat_cache_hits / total) if total else 0.0,
        }

    def _update_fog_of_war(self):
        """Update fog of war."""
        fog_of_war = self.world.get_singleton_component(FogOfWar)
        if not fog_of_war:
            fog_of_war = FogOfWar()
            self.world.add_singleton_component(fog_of_war)

        # Clear current-frame visibility.
        fog_of_war.faction_vision.clear()

        # Compute per-unit visibility.
        for entity in self.world.query().with_all(HexPosition, Vision, Unit).entities():
            position = self.world.get_component(entity, HexPosition)
            vision = self.world.get_component(entity, Vision)
            unit = self.world.get_component(entity, Unit)

            if not position or not vision or not unit:
                continue

            # Reuse cached visibility when the inputs are unchanged.
            current_pos = (position.col, position.row)
            if (
                not vision.dirty
                and vision._last_observed_pos == current_pos
                and vision._last_range == vision.range
                and vision.visible_tiles  # guard against initial empty cache
            ):
                visible_tiles = vision.visible_tiles
                self._stat_cache_hits += 1
            else:
                # Compute visible tile set.
                visible_tiles = self._calculate_vision(
                    current_pos, vision.range, entity
                )
                vision.visible_tiles = visible_tiles
                vision._last_observed_pos = current_pos
                vision._last_range = vision.range
                vision.dirty = False
                self._stat_recomputes += 1

            # Update faction-level visibility.
            if unit.faction not in fog_of_war.faction_vision:
                fog_of_war.faction_vision[unit.faction] = set()

            fog_of_war.faction_vision[unit.faction].update(visible_tiles)

            # Update explored (permanently revealed) tiles.
            if unit.faction not in fog_of_war.explored_tiles:
                fog_of_war.explored_tiles[unit.faction] = set()

            fog_of_war.explored_tiles[unit.faction].update(visible_tiles)

    def _calculate_vision(
        self, center: Tuple[int, int], range_val: int, observer_entity: int
    ) -> Set[Tuple[int, int]]:
        """Calculate the set of tiles visible from center within range."""
        visible = set()
        q, r = center

        # Apply terrain vision bonus.
        terrain_bonus = self._get_vision_terrain_bonus(center)
        effective_range = range_val + terrain_bonus

        # Ray-cast to determine visible tiles.
        for target_q in range(q - effective_range, q + effective_range + 1):
            for target_r in range(r - effective_range, r + effective_range + 1):
                target_pos = (target_q, target_r)

                # Distance check.
                if HexMath.hex_distance(center, target_pos) <= effective_range:
                    # Check for line-of-sight obstruction.
                    if self._has_line_of_sight(center, target_pos):
                        visible.add(target_pos)

        return visible

    def _has_line_of_sight(self, start: Tuple[int, int], end: Tuple[int, int]) -> bool:
        """Check whether there is an unobstructed line of sight between start and end."""
        line = HexMath.line_of_sight(start, end)

        map_data = self.world.get_singleton_component(MapData)
        if not map_data:
            return True

        from ..components.terrain import effect_for

        for pos in line[1:-1]:  # exclude start and end
            tile_entity = map_data.tiles.get(pos)
            if tile_entity:
                terrain = self.world.get_component(tile_entity, Terrain)
                if terrain and effect_for(terrain.terrain_type).blocks_line_of_sight:
                    return False

        return True

    def _get_vision_terrain_bonus(self, position: Tuple[int, int]) -> int:
        """Return the vision range bonus granted by the terrain at position."""
        map_data = self.world.get_singleton_component(MapData)
        if not map_data:
            return 0

        tile_entity = map_data.tiles.get(position)
        if not tile_entity:
            return 0

        from ..components.terrain import effect_for

        terrain = self.world.get_component(tile_entity, Terrain)
        if not terrain:
            return 0
        return int(effect_for(terrain.terrain_type).vision_bonus)
