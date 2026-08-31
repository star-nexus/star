"""Compatibility-named EffectRenderSystem with 1000-unit hot-path diagnostics.

The underlying FastEffectRenderSystem remains the source of visual semantics.
This subclass only splits the expensive interactive path into profiler sections
so the next 1000-unit run can distinguish position-index cost, movement cache
key construction, reachable recomputation, overlay submission, and the other
effect layers without changing rendering behaviour.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from framework.ecs import profiling
from framework.engine import RMS

from ..components import (
    Camera,
    HexPosition,
    MovementPoints,
    Unit,
    UnitCount,
)
from ..prefabs.config import GameConfig
from .fast_render_systems import FastEffectRenderSystem


class EffectRenderSystem(FastEffectRenderSystem):
    """Fast effect renderer plus second-level profiling for scale tests."""

    def update(self, delta_time: float) -> None:
        camera = self.world.get_singleton_component(Camera)
        if not camera:
            return

        with profiling.profiler.time_system(
            "effect_position_index", category="render"
        ):
            index: Dict[Tuple[int, int], List[Tuple[int, object]]] = {}
            indexed_units = 0
            for entity in self.world.query().with_all(HexPosition, Unit).entities():
                pos = self.world.get_component(entity, HexPosition)
                unit = self.world.get_component(entity, Unit)
                if pos is not None and unit is not None:
                    index.setdefault((pos.col, pos.row), []).append(
                        (entity, unit.faction)
                    )
                    indexed_units += 1
            self._unit_position_index = index
        profiling.profiler.set_frame_metric(
            "effect_position_index_units", indexed_units
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
