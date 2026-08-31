"""Window-only minimap refresh policy for large unit counts.

Terrain is already cached by FastMiniMapSystem. The remaining cost is redrawing
all unit dots at render FPS even though the minimap is a low-frequency overview.
This subclass caches only the dynamic unit-dot layer at 15 Hz while keeping the
camera viewport, frame border and final composite at full frame rate.

The change is visual-only and mounted only for display='window'.
"""

from __future__ import annotations

import time
from typing import Optional, Tuple

import pygame

from framework.engine import RMS
from framework.ecs import profiling

from ..components import Camera, MapData, MiniMap
from .optimized_render_systems import MiniMapSystem as _BaseMiniMapSystem


class MiniMapSystem(_BaseMiniMapSystem):
    UNIT_REFRESH_HZ = 15.0

    def __init__(self):
        super().__init__()
        self._unit_surface: Optional[pygame.Surface] = None
        self._unit_surface_size: Optional[Tuple[int, int]] = None
        self._unit_layer_key = None
        self._last_unit_refresh = 0.0
        self._unit_refresh_interval = 1.0 / self.UNIT_REFRESH_HZ
        self._unit_refresh_count = 0

    def _render_minimap(self, minimap: MiniMap):
        map_data = self.world.get_singleton_component(MapData)
        camera = self.world.get_singleton_component(Camera)
        if not map_data or not map_data.tiles:
            return

        rect_x, rect_y, rect_w, rect_h = self._get_screen_rect(minimap)
        static_key = (
            id(map_data),
            map_data.map_id,
            len(map_data.tiles),
            rect_w,
            rect_h,
            bool(minimap.show_terrain),
            float(minimap.scale),
            minimap.background_alpha,
        )

        min_q = min(q for q, _ in map_data.tiles)
        max_q = max(q for q, _ in map_data.tiles)
        min_r = min(r for _, r in map_data.tiles)
        max_r = max(r for _, r in map_data.tiles)
        map_width = max_q - min_q + 1
        map_height = max_r - min_r + 1

        if self._static_surface is None or static_key != self._static_key:
            base = pygame.Surface((rect_w, rect_h), pygame.SRCALPHA)
            base.fill((0, 0, 0, minimap.background_alpha))
            self._calculate_world_bounds(map_data)
            if minimap.show_terrain:
                self._render_terrain(
                    base,
                    minimap,
                    map_data,
                    min_q,
                    min_r,
                    map_width,
                    map_height,
                )
            self._static_surface = base
            self._static_key = static_key
            # Map/layout changes invalidate the separately cached unit layer.
            self._unit_layer_key = None

        if self._frame_surface is None or self._frame_size != (rect_w, rect_h):
            self._frame_surface = pygame.Surface((rect_w, rect_h), pygame.SRCALPHA)
            self._frame_size = (rect_w, rect_h)

        unit_key = (
            id(map_data),
            map_data.map_id,
            len(map_data.tiles),
            rect_w,
            rect_h,
            float(minimap.scale),
            bool(minimap.show_units),
        )
        now = time.perf_counter()
        refresh_units = bool(
            minimap.show_units
            and (
                self._unit_surface is None
                or self._unit_surface_size != (rect_w, rect_h)
                or self._unit_layer_key != unit_key
                or now - self._last_unit_refresh >= self._unit_refresh_interval
            )
        )

        if refresh_units:
            if self._unit_surface is None or self._unit_surface_size != (rect_w, rect_h):
                self._unit_surface = pygame.Surface(
                    (rect_w, rect_h), pygame.SRCALPHA
                )
                self._unit_surface_size = (rect_w, rect_h)
            else:
                self._unit_surface.fill((0, 0, 0, 0))

            with profiling.profiler.time_system(
                "minimap_unit_refresh", category="render"
            ):
                self._render_units(
                    self._unit_surface,
                    minimap,
                    min_q,
                    min_r,
                    map_width,
                    map_height,
                )
            self._unit_layer_key = unit_key
            self._last_unit_refresh = now
            self._unit_refresh_count += 1

        frame = self._frame_surface
        # The frame surface is reused, so clear stale dynamic pixels before
        # composing the current cached layers.
        frame.fill((0, 0, 0, 0))
        frame.blit(self._static_surface, (0, 0))
        if minimap.show_units and self._unit_surface is not None:
            frame.blit(self._unit_surface, (0, 0))
        if minimap.show_camera_viewport and camera:
            self._render_camera_viewport(
                frame,
                minimap,
                camera,
                min_q,
                min_r,
                map_width,
                map_height,
            )
        pygame.draw.rect(
            frame,
            minimap.border_color,
            (0, 0, rect_w, rect_h),
            minimap.border_width,
        )
        RMS.draw(frame, (rect_x, rect_y))

        profiling.profiler.set_frame_metric(
            "minimap_unit_refreshed", 1 if refresh_units else 0
        )
        profiling.profiler.set_frame_metric(
            "minimap_unit_refreshes", self._unit_refresh_count
        )
