"""Window UnitRenderSystem with bucketed visibility candidates.

The rich/batch render semantics remain in optimized_render_systems.UnitRenderSystem.
Only candidate discovery changes: instead of walking every Unit entity each frame,
the renderer asks the shared spatial index for buckets intersecting the camera's
world-space viewport, then performs the existing exact bounds/fog checks.
"""

from __future__ import annotations

from typing import List

from framework.ecs import profiling

from ..prefabs.config import GameConfig
from ..utils.unit_spatial_index import get_unit_spatial_index
from .optimized_render_systems import UnitRenderSystem as _BaseUnitRenderSystem


class UnitRenderSystem(_BaseUnitRenderSystem):
    """Scale renderer with coarse spatial culling before exact visibility."""

    def _get_visible_units(self, camera_offset: List[float], zoom: float) -> List[int]:
        index = get_unit_spatial_index(self.world)
        if index is None or zoom <= 0:
            return super()._get_visible_units(camera_offset, zoom)

        margin = 100
        screen_left = (-camera_offset[0] - margin) / zoom
        screen_right = (GameConfig.WINDOW_WIDTH - camera_offset[0] + margin) / zoom
        screen_top = (-camera_offset[1] - margin) / zoom
        screen_bottom = (GameConfig.WINDOW_HEIGHT - camera_offset[1] + margin) / zoom

        visible_units: List[int] = []
        candidates = 0
        for entity in index.candidates_in_world_rect(
            screen_left, screen_right, screen_top, screen_bottom
        ):
            candidates += 1
            record = index.by_entity.get(entity)
            if record is None:
                continue
            if not self._is_unit_visible(entity):
                continue

            world_x, world_y = self.hex_converter.hex_to_pixel(record.col, record.row)
            if (
                screen_left <= world_x <= screen_right
                and screen_top <= world_y <= screen_bottom
            ):
                visible_units.append(entity)

        profiling.profiler.set_frame_metric("unit_cull_candidates", candidates)
        profiling.profiler.set_frame_metric(
            "unit_cull_population", len(index.by_entity)
        )
        profiling.profiler.set_frame_metric(
            "unit_cull_spatial_revision", index.revision
        )
        return visible_units
