"""Compatibility-named EffectRenderSystem for 1000+ unit interactive scale tests.

The renderer keeps the visual semantics of ``FastEffectRenderSystem`` while
removing its per-frame full spatial-index rebuild.  A persistent unit position
index is synchronized in place and only mutates when units actually move,
spawn, disappear, or change faction.  The same spatial revision also replaces
the previous O(units) occupancy tuple in the movement-range cache key.

Second-level profiler sections remain in place so scale runs can attribute any
remaining EffectRender cost precisely.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from framework.ecs import profiling
from framework.engine import RMS

from ..components import (
    Camera,
    HexPosition,
    MapData,
    MovementPoints,
    Unit,
    UnitCount,
)
from ..prefabs.config import GameConfig
from .fast_render_systems import FastEffectRenderSystem


class EffectRenderSystem(FastEffectRenderSystem):
    """Fast effect renderer with a persistent low-allocation spatial index."""

    def __init__(self):
        super().__init__()
        # entity -> [col, row, faction, last_seen_generation]
        # Lists are mutated in place so unchanged units allocate nothing here.
        self._spatial_state: Dict[int, List[object]] = {}
        self._spatial_generation = 0
        self._spatial_revision = 0

    def initialize(self, world) -> None:
        super().initialize(world)
        # Build once during world initialization, before the gameplay profiling
        # epoch.  The first measured frame therefore pays only the cheap sync.
        self._sync_position_index()

    def _remove_index_entry(self, entity: int, col: int, row: int) -> None:
        key = (col, row)
        bucket = self._unit_position_index.get(key)
        if not bucket:
            return
        for index, entry in enumerate(bucket):
            if entry[0] == entity:
                bucket.pop(index)
                break
        if not bucket:
            self._unit_position_index.pop(key, None)

    def _add_index_entry(self, entity: int, col: int, row: int, faction) -> None:
        self._unit_position_index.setdefault((col, row), []).append(
            (entity, faction)
        )

    def _sync_position_index(self) -> Tuple[int, int]:
        """Synchronize the persistent spatial index without rebuilding it.

        We still scan Unit/HexPosition components once per frame so direct ECS
        position mutations remain visible, but unchanged units only perform
        dictionary lookups and integer/object comparisons.  Tuple/list churn is
        limited to units whose spatial state actually changes.
        """
        self._spatial_generation += 1
        generation = self._spatial_generation
        indexed_units = 0
        changes = 0
        added = False

        for entity in self.world.query().with_all(HexPosition, Unit).entities():
            pos = self.world.get_component(entity, HexPosition)
            unit = self.world.get_component(entity, Unit)
            if pos is None or unit is None:
                continue

            indexed_units += 1
            state = self._spatial_state.get(entity)
            if state is None:
                self._spatial_state[entity] = [
                    pos.col,
                    pos.row,
                    unit.faction,
                    generation,
                ]
                self._add_index_entry(
                    entity, pos.col, pos.row, unit.faction
                )
                changes += 1
                added = True
                continue

            state[3] = generation
            if (
                state[0] == pos.col
                and state[1] == pos.row
                and state[2] == unit.faction
            ):
                continue

            self._remove_index_entry(entity, int(state[0]), int(state[1]))
            self._add_index_entry(entity, pos.col, pos.row, unit.faction)
            state[0] = pos.col
            state[1] = pos.row
            state[2] = unit.faction
            changes += 1

        # Entity destruction is rare.  Only allocate a stale-id list when the
        # population changed (or a new entity appeared), not on steady frames.
        if added or len(self._spatial_state) != indexed_units:
            stale_entities = [
                entity
                for entity, state in self._spatial_state.items()
                if state[3] != generation
            ]
            for entity in stale_entities:
                state = self._spatial_state.pop(entity)
                self._remove_index_entry(entity, int(state[0]), int(state[1]))
                changes += 1

        if changes:
            # One revision per frame is sufficient: movement reachability only
            # needs to know whether occupancy changed since the cached result.
            self._spatial_revision += 1

        return indexed_units, changes

    def _movement_state_key(
        self,
        unit_entity: int,
        position: HexPosition,
        movement: MovementPoints,
        unit_count: UnitCount | None,
    ):
        """Movement cache key using the already-maintained spatial revision."""
        map_data = self.world.get_singleton_component(MapData)
        return (
            unit_entity,
            position.col,
            position.row,
            movement.current_mp,
            movement.max_mp,
            unit_count.current_count if unit_count else None,
            id(map_data),
            self._spatial_revision,
        )

    def update(self, delta_time: float) -> None:
        camera = self.world.get_singleton_component(Camera)
        if not camera:
            return

        with profiling.profiler.time_system(
            "effect_position_index", category="render"
        ):
            indexed_units, index_changes = self._sync_position_index()
        profiling.profiler.set_frame_metric(
            "effect_position_index_units", indexed_units
        )
        profiling.profiler.set_frame_metric(
            "effect_position_index_changes", index_changes
        )
        profiling.profiler.set_frame_metric(
            "effect_spatial_revision", self._spatial_revision
        )

        camera_offset = [camera.offset_x, camera.offset_y]
        zoom = getattr(camera, "zoom", 1.0)

        with profiling.profiler.time_system(
            "effect_selection", category="render"
        ):
            self._render_selection_effects(camera_offset, zoom)
        with profiling.profiler.time_system(
            "effect_attack_effects", category="render"
        ):
            self._render_attack_effects(camera_offset, zoom)
        with profiling.profiler.time_system(
            "effect_attack_indicators", category="render"
        ):
            self._render_attack_indicators(camera_offset, zoom)
        with profiling.profiler.time_system(
            "effect_projectiles", category="render"
        ):
            self._render_projectiles(camera_offset, zoom)
        with profiling.profiler.time_system("effect_hover", category="render"):
            self._render_tile_hover(camera_offset, zoom)

    def _render_movement_range(
        self, unit_entity: int, camera_offset: List[float], zoom: float = 1.0
    ):
        """Mirror FastEffectRenderSystem movement rendering with attribution."""
        position = self.world.get_component(unit_entity, HexPosition)
        movement = self.world.get_component(unit_entity, MovementPoints)
        unit = self.world.get_component(unit_entity, Unit)
        unit_count = self.world.get_component(unit_entity, UnitCount)
        if not position or not movement or not unit:
            profiling.profiler.set_frame_metric("effect_movement_cache_miss", 0)
            profiling.profiler.set_frame_metric("effect_reachable_tiles", 0)
            return

        with profiling.profiler.time_system(
            "effect_movement_cache_key", category="render"
        ):
            key = self._movement_state_key(
                unit_entity, position, movement, unit_count
            )

        cache_miss = int(key != self._movement_cache_key)
        profiling.profiler.set_frame_metric(
            "effect_movement_cache_miss", cache_miss
        )

        if cache_miss:
            from ..utils.map_query import reachable_hexes

            with profiling.profiler.time_system(
                "effect_reachable_recompute", category="render"
            ):
                self._movement_cache = reachable_hexes(
                    self.world,
                    (position.col, position.row),
                    movement.spendable(unit_count),
                    mover=unit_entity,
                )
            self._movement_cache_key = key

        profiling.profiler.set_frame_metric(
            "effect_reachable_tiles", len(self._movement_cache)
        )

        with profiling.profiler.time_system(
            "effect_movement_overlay_prepare", category="render"
        ):
            overlay, radius = self._movement_overlay(zoom)

        margin = radius + 2
        submitted = 0
        with profiling.profiler.time_system(
            "effect_movement_overlay_submit", category="render"
        ):
            for q, r in self._movement_cache:
                if (q, r) == (position.col, position.row):
                    continue
                world_x, world_y = self.hex_converter.hex_to_pixel(q, r)
                screen_x = world_x * zoom + camera_offset[0]
                screen_y = world_y * zoom + camera_offset[1]
                if not (
                    -margin <= screen_x <= GameConfig.WINDOW_WIDTH + margin
                    and -margin <= screen_y <= GameConfig.WINDOW_HEIGHT + margin
                ):
                    continue
                RMS.draw(
                    overlay,
                    (screen_x - radius - 1, screen_y - radius - 1),
                )
                submitted += 1

        profiling.profiler.set_frame_metric(
            "effect_movement_overlays_submitted", submitted
        )
