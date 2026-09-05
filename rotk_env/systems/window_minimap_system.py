"""Window minimap with independently cached terrain and unit layers.

Terrain is already cached by FastMiniMapSystem. The remaining cost is redrawing
all unit dots at render FPS even though the minimap is a low-frequency overview.
The dynamic unit-dot layer refreshes at 15 Hz while keeping the
camera viewport, frame border and final composite at full frame rate.

The optional ``STAR_SCALE_MINIMAP_UNITS`` environment override exists only to
support controlled scale-ablation runs. Normal production behavior is unchanged
when the variable is absent.

This policy is mounted only for ``display='window'``.
"""

from __future__ import annotations

import os
import time
from typing import Optional, Tuple

import pygame

from framework.engine import RMS
from framework.ecs import profiling

from ..components import Camera, MapData, MiniMap
from ..utils.unit_spatial_index import get_unit_spatial_index
from .optimized_render_systems import MiniMapSystem as _BaseMiniMapSystem

_MINIMAP_UNITS_OVERRIDE_ENV = "STAR_SCALE_MINIMAP_UNITS"


def _parse_minimap_units_override(value: Optional[str]) -> Optional[bool]:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(
        f"{_MINIMAP_UNITS_OVERRIDE_ENV} must be one of on/off, true/false, 1/0"
    )


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
        self._layout_key = None
        self._layout_bounds: Optional[Tuple[int, int, int, int]] = None
        self._layout_rebuild_count = 0

    def initialize(self, world) -> None:
        super().initialize(world)
        minimap = self.world.get_singleton_component(MiniMap)
        if minimap is None:
            return

        requested = _parse_minimap_units_override(
            os.environ.get(_MINIMAP_UNITS_OVERRIDE_ENV)
        )
        if requested is not None:
            minimap.show_units = requested

        profiling.profiler.set_metadata(
            minimap_unit_layer_enabled=bool(minimap.show_units),
            minimap_unit_layer_override=(
                "default"
                if requested is None
                else ("on" if requested else "off")
            ),
            minimap_unit_refresh_hz=self.UNIT_REFRESH_HZ,
        )

    def _get_layout_bounds(self, map_data: MapData) -> Tuple[int, int, int, int]:
        layout_key = (
            id(map_data),
            id(map_data.tiles),
            map_data.map_id,
            len(map_data.tiles),
        )
        if self._layout_bounds is None or self._layout_key != layout_key:
            with profiling.profiler.time_system(
                "minimap_layout_bounds", category="render"
            ):
                min_q = min(q for q, _ in map_data.tiles)
                max_q = max(q for q, _ in map_data.tiles)
                min_r = min(r for _, r in map_data.tiles)
                max_r = max(r for _, r in map_data.tiles)
            self._layout_bounds = (min_q, max_q, min_r, max_r)
            self._layout_key = layout_key
            self._layout_rebuild_count += 1
            self._unit_layer_key = None
        return self._layout_bounds

    def _render_minimap(self, minimap: MiniMap):
        map_data = self.world.get_singleton_component(MapData)
        camera = self.world.get_singleton_component(Camera)
        if not map_data or not map_data.tiles:
            return

        rect_x, rect_y, rect_w, rect_h = self._get_screen_rect(minimap)
        min_q, max_q, min_r, max_r = self._get_layout_bounds(map_data)
        static_key = (
            self._layout_key,
            rect_w,
            rect_h,
            bool(minimap.show_terrain),
            float(minimap.scale),
            minimap.background_alpha,
        )

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

        unit_layout_key = (
            self._layout_key,
            rect_w,
            rect_h,
            float(minimap.scale),
            bool(minimap.show_units),
        )
        spatial_index = get_unit_spatial_index(self.world)
        spatial_revision = spatial_index.revision if spatial_index is not None else None
        unit_key = (unit_layout_key, spatial_revision)
        now = time.perf_counter()
        surface_invalid = bool(
            self._unit_surface is None
            or self._unit_surface_size != (rect_w, rect_h)
            or self._unit_layer_key is None
            or self._unit_layer_key[0] != unit_layout_key
        )
        refresh_due = now - self._last_unit_refresh >= self._unit_refresh_interval
        revision_changed = bool(
            spatial_index is not None
            and self._unit_layer_key is not None
            and self._unit_layer_key[1] != spatial_revision
        )
        refresh_units = bool(
            minimap.show_units
            and (
                surface_invalid
                or (refresh_due and (spatial_index is None or revision_changed))
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
            "minimap_unit_layer_enabled", 1 if minimap.show_units else 0
        )
        profiling.profiler.set_frame_metric(
            "minimap_unit_refreshed", 1 if refresh_units else 0
        )
        profiling.profiler.set_frame_metric(
            "minimap_unit_refreshes", self._unit_refresh_count
        )
        profiling.profiler.set_frame_metric(
            "minimap_spatial_revision",
            spatial_revision if spatial_revision is not None else -1,
        )
        profiling.profiler.set_frame_metric(
            "minimap_revision_changed", 1 if revision_changed else 0
        )
        profiling.profiler.set_frame_metric(
            "minimap_layout_rebuilds", self._layout_rebuild_count
        )
