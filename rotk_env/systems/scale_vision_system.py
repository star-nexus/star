"""Window-only incremental fog/vision aggregation for large unit counts.

The base VisionSystem caches each unit's LOS result, but still clears and
rebuilds every faction visibility set from every unit on every frame. At 2000
units that faction-level set-union work dominates the frame even when almost no
units move.

This compatibility-named subclass keeps the base LOS semantics and adds a
reference-counted faction aggregate. Unchanged units keep their cached LOS and
perform no set union. Spawn/move/range/faction changes update only the affected
unit contribution; removed units subtract their previous contribution.

When fog is disabled, the visible window publishes one shared whole-map tile
set for every active faction and then suspends per-unit vision work entirely.
Re-enabling fog triggers a one-pass aggregate rebuild from the existing per-unit
LOS caches before gameplay continues.

The canonical/headless VisionSystem remains untouched; this class is installed
only for display='window'.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, Set, Tuple

from framework.ecs import profiling

from ..components import FogOfWar, HexPosition, MapData, Unit, Vision
from ..prefabs.config import Faction
from .vision_system import VisionSystem as _BaseVisionSystem

Tile = Tuple[int, int]


class VisionSystem(_BaseVisionSystem):
    """Incremental window-mode VisionSystem with ref-counted faction sets."""

    def __init__(self):
        super().__init__()
        self._unit_state: Dict[int, tuple[Faction, Set[Tile], Tile, int]] = {}
        self._faction_refcounts: Dict[Faction, Dict[Tile, int]] = defaultdict(dict)
        self._faction_visible: Dict[Faction, Set[Tile]] = defaultdict(set)
        self._force_aggregate_rebuild = True
        self._fog_was_enabled = True

    def initialize(self, world) -> None:
        super().initialize(world)
        self._unit_state.clear()
        self._faction_refcounts.clear()
        self._faction_visible.clear()
        self._force_aggregate_rebuild = True
        self._fog_was_enabled = True

    def invalidate_all(self) -> None:
        super().invalidate_all()
        self._force_aggregate_rebuild = True

    def _remove_contribution(self, faction: Faction, tiles: Set[Tile]) -> int:
        counts = self._faction_refcounts[faction]
        visible = self._faction_visible[faction]
        changed = 0
        for tile in tiles:
            count = counts.get(tile, 0)
            if count <= 1:
                if tile in counts:
                    del counts[tile]
                visible.discard(tile)
            else:
                counts[tile] = count - 1
            changed += 1
        if not counts:
            self._faction_refcounts.pop(faction, None)
            if not visible:
                self._faction_visible.pop(faction, None)
        return changed

    def _add_contribution(self, faction: Faction, tiles: Set[Tile]) -> int:
        counts = self._faction_refcounts[faction]
        visible = self._faction_visible[faction]
        for tile in tiles:
            count = counts.get(tile, 0) + 1
            counts[tile] = count
            if count == 1:
                visible.add(tile)
        return len(tiles)

    def _reset_aggregate_only(self) -> None:
        self._unit_state.clear()
        self._faction_refcounts.clear()
        self._faction_visible.clear()

    def _publish_faction_sets(self, fog: FogOfWar) -> None:
        active = set(self._faction_visible)
        for faction in list(fog.faction_vision):
            if faction not in active:
                del fog.faction_vision[faction]
        for faction, tiles in self._faction_visible.items():
            # Publish the maintained set itself; do not copy thousands of tiles
            # every frame. Consumers treat faction_vision as read-only state.
            fog.faction_vision[faction] = tiles

    def _publish_fog_disabled_visibility(self, fog: FogOfWar) -> None:
        """Publish whole-map visibility once without scanning units every frame."""
        map_data = self.world.get_singleton_component(MapData)
        all_tiles = set(map_data.tiles) if map_data is not None else set()
        factions = {state[0] for state in self._unit_state.values()}
        if not factions:
            for entity in self.world.query().with_component(Unit).entities():
                unit = self.world.get_component(entity, Unit)
                if unit is not None:
                    factions.add(unit.faction)
        fog.faction_vision.clear()
        for faction in factions:
            fog.faction_vision[faction] = all_tiles
            fog.explored_tiles.setdefault(faction, set()).update(all_tiles)

    def _update_fog_of_war(self):
        fog = self.world.get_singleton_component(FogOfWar)
        if not fog:
            fog = FogOfWar()
            self.world.add_singleton_component(fog)

        if not fog.enabled:
            # Fog-off semantics are whole-map visibility for humans, BOTs and
            # agents. Publish that state once on transition, then do zero per-unit
            # vision work until fog is re-enabled.
            if self._fog_was_enabled:
                self._publish_fog_disabled_visibility(fog)
            self._fog_was_enabled = False
            self._force_aggregate_rebuild = True
            profiling.profiler.set_frame_metric("vision_mode", "fog_disabled")
            profiling.profiler.set_frame_metric("vision_units_scanned", 0)
            profiling.profiler.set_frame_metric("vision_units_changed", 0)
            profiling.profiler.set_frame_metric("vision_tile_updates", 0)
            return

        if not self._fog_was_enabled:
            self._force_aggregate_rebuild = True
            self._fog_was_enabled = True

        if self._force_aggregate_rebuild:
            self._reset_aggregate_only()

        entities = self.world.query().with_all(HexPosition, Vision, Unit).entities()
        seen = set()
        changed_units = 0
        tile_updates = 0
        scanned = 0

        for entity in entities:
            scanned += 1
            seen.add(entity)
            position = self.world.get_component(entity, HexPosition)
            vision = self.world.get_component(entity, Vision)
            unit = self.world.get_component(entity, Unit)
            if not position or not vision or not unit:
                continue

            current_pos = (position.col, position.row)
            old = self._unit_state.get(entity)
            unchanged = bool(
                old
                and old[0] == unit.faction
                and old[2] == current_pos
                and old[3] == vision.range
                and not vision.dirty
                and vision.visible_tiles
            )
            if unchanged:
                self._stat_cache_hits += 1
                continue

            if old:
                tile_updates += self._remove_contribution(old[0], old[1])

            # Reuse the base per-unit cache if valid. A forced aggregate rebuild
            # should not force thousands of LOS raycasts.
            cache_valid = bool(
                not vision.dirty
                and vision._last_observed_pos == current_pos
                and vision._last_range == vision.range
                and vision.visible_tiles
            )
            if cache_valid:
                visible_tiles = set(vision.visible_tiles)
                self._stat_cache_hits += 1
            else:
                visible_tiles = self._calculate_vision(
                    current_pos, vision.range, entity
                )
                vision.visible_tiles = visible_tiles
                vision._last_observed_pos = current_pos
                vision._last_range = vision.range
                vision.dirty = False
                self._stat_recomputes += 1

            stable_tiles = set(visible_tiles)
            self._unit_state[entity] = (
                unit.faction,
                stable_tiles,
                current_pos,
                vision.range,
            )
            tile_updates += self._add_contribution(unit.faction, stable_tiles)
            fog.explored_tiles.setdefault(unit.faction, set()).update(stable_tiles)
            changed_units += 1

        # Death/despawn removes only that unit's contribution. Explored tiles are
        # intentionally permanent, matching the base system.
        for entity in tuple(self._unit_state):
            if entity in seen:
                continue
            faction, tiles, _pos, _range = self._unit_state.pop(entity)
            tile_updates += self._remove_contribution(faction, tiles)
            changed_units += 1

        self._publish_faction_sets(fog)
        self._force_aggregate_rebuild = False

        profiling.profiler.set_frame_metric("vision_mode", "incremental")
        profiling.profiler.set_frame_metric("vision_units_scanned", scanned)
        profiling.profiler.set_frame_metric("vision_units_changed", changed_units)
        profiling.profiler.set_frame_metric("vision_tile_updates", tile_updates)
