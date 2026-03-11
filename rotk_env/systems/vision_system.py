"""
Vision system - handles fog of war and line-of-sight calculation.
"""

from typing import Set, Tuple
from framework import System, World
from ..components import HexPosition, Vision, Unit, FogOfWar, MapData, Terrain
from ..prefabs.config import GameConfig, TerrainType
from ..utils.hex_utils import HexMath


class VisionSystem(System):
    """Vision system - handles fog of war and line-of-sight calculation."""

    def __init__(self):
        super().__init__(required_components={HexPosition, Vision, Unit})

    def initialize(self, world: World) -> None:
        self.world = world

    def subscribe_events(self):
        pass

    def update(self, delta_time: float) -> None:
        """Update vision system."""
        self._update_fog_of_war()

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

            # Compute visible tile set.
            visible_tiles = self._calculate_vision(
                (position.col, position.row), vision.range, entity
            )

            # Update the unit's visible tiles.
            vision.visible_tiles = visible_tiles

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

        for pos in line[1:-1]:  # exclude start and end
            tile_entity = map_data.tiles.get(pos)
            if tile_entity:
                terrain = self.world.get_component(tile_entity, Terrain)
                if terrain and terrain.terrain_type == TerrainType.MOUNTAIN:
                    return False  # Mountains block line of sight.

        return True

    def _get_vision_terrain_bonus(self, position: Tuple[int, int]) -> int:
        """Return the vision range bonus granted by the terrain at position."""
        map_data = self.world.get_singleton_component(MapData)
        if not map_data:
            return 0

        tile_entity = map_data.tiles.get(position)
        if not tile_entity:
            return 0

        terrain = self.world.get_component(tile_entity, Terrain)
        if not terrain:
            return 0

        terrain_effect = GameConfig.TERRAIN_EFFECTS.get(terrain.terrain_type)
        # Terrain currently provides no vision bonus; always returns 0.
        return 0
