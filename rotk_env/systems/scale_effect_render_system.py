"""Compatibility-named EffectRenderSystem for 1000+ unit interactive scale tests.

The renderer keeps the visual semantics of ``FastEffectRenderSystem`` while
sharing the same event-driven ``UnitSpatialIndex`` as movement, culling and
realtime game-over checks.  It no longer owns a second per-frame unit index.

Movement-range overlays also use a local spatial revision: movement elsewhere
on a large map no longer invalidates the selected unit's reachable mask.  On an
actual cache miss, occupancy is read from the shared index only inside the
selected unit's movement radius, then the canonical terrain/pathfinding rules
compute the same legal destinations as ``reachable_hexes``.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from framework.ecs import profiling
from framework.engine import RMS

from ..components import Camera, HexPosition, MapData, MovementPoints, Unit, UnitCount
from ..prefabs.config import GameConfig
from ..utils.hex_utils import PathFinding
from ..utils.map_query import board_hexes, impassable_terrain, movement_costs
from ..utils.unit_spatial_index import get_unit_spatial_index
from .fast_render_systems import FastEffectRenderSystem


class EffectRenderSystem(FastEffectRenderSystem):
    """Fast effect renderer backed by the shared scale spatial index."""

    def __init__(self):
        super().__init__()
        self._last_shared_revision: Optional[int] = None

    def initialize(self, world) -> None:
        # Do not build a private index here.  WorldBuilder installs the shared
        # UnitSpatialIndex after unit creation and before gameplay profiling.
        super().initialize(world)

    def _get_enemy_unit_at_position(self, position, friendly_faction):
        index = get_unit_spatial_index(self.world)
        if index is not None:
            return index.enemy_at_cell(position, friendly_faction)

        # Compatibility fallback for isolated tests/worlds that deliberately do
        # not install the window scale index.
        for entity in self.world.query().with_all(HexPosition, Unit).entities():
            pos = self.world.get_component(entity, HexPosition)
            unit = self.world.get_component(entity, Unit)
            if (
                pos is not None
                and unit is not None
                and (pos.col, pos.row) == position
                and unit.faction != friendly_faction
            ):
                return entity
        return None

    def _movement_state_key(
        self,
        unit_entity: int,
        position: HexPosition,
        movement: MovementPoints,
        unit_count: UnitCount | None,
    ):
        index = get_unit_spatial_index(self.world)
        if index is None:
            # Preserve correctness when this renderer is exercised
            # without WorldBuilder's shared index.
            return super()._movement_state_key(
                unit_entity, position, movement, unit_count
            )

        map_data = self.world.get_singleton_component(MapData)
        spendable = max(0, int(movement.spendable(unit_count)))
        local_revision = index.local_revision_signature(
            (position.col, position.row), spendable
        )
        return (
            unit_entity,
            position.col,
            position.row,
            movement.current_mp,
            movement.max_mp,
            unit_count.current_count if unit_count else None,
            spendable,
            id(map_data),
            local_revision,
        )

    def _indexed_reachable_hexes(
        self,
        unit_entity: int,
        position: HexPosition,
        movement: MovementPoints,
        unit: Unit,
        unit_count: UnitCount | None,
    ):
        """Canonical movement range using local occupancy from the shared index."""
        index = get_unit_spatial_index(self.world)
        if index is None:
            from ..utils.map_query import reachable_hexes

            return reachable_hexes(
                self.world,
                (position.col, position.row),
                movement.spendable(unit_count),
                mover=unit_entity,
            )

        start = (position.col, position.row)
        spendable = max(0, int(movement.spendable(unit_count)))
        with profiling.profiler.time_system(
            "effect_reachable_occupancy", category="render"
        ):
            occupied, enemy_held = index.occupancy_for_mover_local(
                unit_entity,
                unit.faction,
                start,
                spendable,
            )

        profiling.profiler.set_frame_metric(
            "effect_reachable_occupied_cells", len(occupied)
        )
        profiling.profiler.set_frame_metric(
            "effect_reachable_enemy_blockers", len(enemy_held)
        )
        profiling.profiler.set_frame_metric(
            "effect_reachable_local_buckets",
            len(index.local_revision_signature(start, spendable)),
        )

        blocked = set(impassable_terrain(self.world))
        blocked.update(enemy_held)
        costs = movement_costs(self.world)
        within_budget = PathFinding.get_movement_range(
            start,
            spendable,
            blocked,
            walkable=board_hexes(self.world),
            step_cost=lambda pos: costs.get(pos, 999),
        )
        return within_budget - occupied

    def update(self, delta_time: float) -> None:
        camera = self.world.get_singleton_component(Camera)
        if not camera:
            return

        # The shared index is already maintained by movement/death commits.
        # Reuse the maintained index; fall back cleanly when it is unavailable.
        with profiling.profiler.time_system(
            "effect_position_index", category="render"
        ):
            index = get_unit_spatial_index(self.world)
            if index is not None:
                indexed_units = len(index.by_entity)
                revision = index.revision
                if self._last_shared_revision is None:
                    revision_delta = 0
                else:
                    revision_delta = max(0, revision - self._last_shared_revision)
                self._last_shared_revision = revision
            else:
                indexed_units = 0
                revision = 0
                revision_delta = 0

        profiling.profiler.set_frame_metric(
            "effect_position_index_units", indexed_units
        )
        profiling.profiler.set_frame_metric(
            "effect_position_index_changes", revision_delta
        )
        profiling.profiler.set_frame_metric(
            "effect_spatial_revision", revision
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
        with profiling.profiler.time_system("effect_projectiles", category="render"):
            self._render_projectiles(camera_offset, zoom)
        with profiling.profiler.time_system("effect_hover", category="render"):
            self._render_tile_hover(camera_offset, zoom)

    def _render_movement_range(
        self, unit_entity: int, camera_offset: List[float], zoom: float = 1.0
    ):
        """Render movement reachability using indexed occupancy."""
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
            with profiling.profiler.time_system(
                "effect_reachable_recompute", category="render"
            ):
                self._movement_cache = self._indexed_reachable_hexes(
                    unit_entity,
                    position,
                    movement,
                    unit,
                    unit_count,
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
