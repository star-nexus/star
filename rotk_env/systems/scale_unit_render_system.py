"""Window UnitRenderSystem with bucketed visibility candidates.

The rich/batch render semantics remain in optimized_render_systems.UnitRenderSystem.
Only candidate discovery changes: instead of walking every Unit entity each frame,
the renderer asks the shared spatial index for buckets intersecting the camera's
world-space viewport, then performs cheap exact bounds and fog checks from cached
spatial records.
"""

from __future__ import annotations

from typing import List

from framework.ecs import profiling

from ..components import FogOfWar, GameState, UIState
from ..prefabs.config import GameConfig
from ..utils.unit_spatial_index import get_unit_spatial_index
from .optimized_render_systems import UnitRenderSystem as _BaseUnitRenderSystem


class UnitRenderSystem(_BaseUnitRenderSystem):
    """Scale renderer with coarse spatial culling before exact visibility."""

    # A committed HexPosition can trail/lead the interpolated render position by
    # at most one adjacent-hex segment.  One segment is < 2*HEX_SIZE in either
    # orientation, and the unit sprite extends roughly one HEX_SIZE from center.
    # Three hex radii therefore conservatively cover animation + sprite extent
    # without the old screen-space 100px margin exploding at low zoom.
    CULL_WORLD_MARGIN_HEX_RADII = 3.0

    def _get_visible_units(self, camera_offset: List[float], zoom: float) -> List[int]:
        index = get_unit_spatial_index(self.world)
        if index is None or zoom <= 0:
            return super()._get_visible_units(camera_offset, zoom)

        margin = float(GameConfig.HEX_SIZE) * self.CULL_WORLD_MARGIN_HEX_RADII
        left = (-camera_offset[0]) / zoom - margin
        right = (GameConfig.WINDOW_WIDTH - camera_offset[0]) / zoom + margin
        top = (-camera_offset[1]) / zoom - margin
        bottom = (GameConfig.WINDOW_HEIGHT - camera_offset[1]) / zoom + margin

        # Fog/view state is frame-global.  Resolve it once instead of repeating
        # singleton + component lookups for every spatial candidate.
        game_state = self.world.get_singleton_component(GameState)
        fog = self.world.get_singleton_component(FogOfWar)
        ui_state = self.world.get_singleton_component(UIState)
        fog_filter = bool(game_state and fog and fog.enabled and ui_state)
        view_faction = (
            (ui_state.view_faction or game_state.current_player)
            if fog_filter
            else None
        )
        current_vision = (
            fog.faction_vision.get(view_faction, set()) if fog_filter else None
        )

        visible_units: List[int] = []
        bucket_count = 0
        candidates = 0
        bounds_rejected = 0
        fog_rejected = 0

        for _, bucket in index.nonempty_buckets_in_world_rect(
            left, right, top, bottom
        ):
            bucket_count += 1
            for entity in bucket:
                candidates += 1
                record = index.by_entity.get(entity)
                if record is None:
                    continue

                # Cheapest/high-rejection test first.  world_x/world_y were
                # already computed when the authoritative hex position changed.
                if not (
                    left <= record.world_x <= right
                    and top <= record.world_y <= bottom
                ):
                    bounds_rejected += 1
                    continue

                if (
                    fog_filter
                    and record.faction != view_faction
                    and (record.col, record.row) not in current_vision
                ):
                    fog_rejected += 1
                    continue

                visible_units.append(entity)

        metric = profiling.profiler.set_frame_metric
        metric("unit_cull_buckets", bucket_count)
        metric("unit_cull_candidates", candidates)
        metric("unit_cull_bounds_rejected", bounds_rejected)
        metric("unit_cull_fog_rejected", fog_rejected)
        metric("unit_cull_visible", len(visible_units))
        metric("unit_cull_population", len(index.by_entity))
        metric("unit_cull_world_margin", margin)
        metric("unit_cull_spatial_revision", index.revision)
        return visible_units
