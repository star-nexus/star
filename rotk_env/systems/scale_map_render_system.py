"""Scale map renderer that amortizes terrain blits while the camera pans.

At 1000 units the remaining sustained interactive cost is no longer map command
construction: ``RenderEngine`` spends roughly 6-7 ms executing hundreds of
terrain blits in a typical 51x51 viewport.  ``FastMapRenderSystem`` already
collapses a stationary view to one cached raster, but deliberately falls back to
per-tile blits whenever the camera moves.

This compatibility renderer adds an overscan raster around the viewport.  After
one stable-zoom frame it rasterizes the visible terrain plus a screen-space
margin.  Subsequent pans within that margin are a single cropped blit; only when
the camera leaves the margin is the overscan surface rebuilt.  Continuous zoom
still uses the proven direct-tile path so we do not trade RenderEngine time for a
full raster rebuild on every zoom step.

The cache contains terrain/city markers only. Territory, fog, coordinates,
units, effects and UI retain their existing dynamic rendering semantics.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

import pygame

from framework.ecs import profiling
from framework.engine import RMS

from ..components import MapData, Terrain
from ..prefabs.config import GameConfig, TerrainType
from .fast_render_systems import FastMapRenderSystem


class ScaleMapRenderSystem(FastMapRenderSystem):
    """Fast map renderer with a pan-friendly overscan terrain raster."""

    OVERSCAN_MARGIN_PX = 256
    OVERSCAN_ZOOM_STABLE_FRAMES = 2

    def __init__(self):
        super().__init__()
        self._overscan_surface: Optional[pygame.Surface] = None
        self._overscan_content_rect = pygame.Rect(0, 0, 0, 0)
        self._overscan_camera_offset: Optional[Tuple[float, float]] = None
        self._overscan_zoom_key = None
        self._overscan_map_key = None
        self._overscan_viewport: Optional[Tuple[int, int]] = None
        self._overscan_zoom_candidate = None
        self._overscan_zoom_stable_frames = 0
        self._overscan_build_count = 0

    def _invalidate_fast_caches(self) -> None:
        super()._invalidate_fast_caches()
        self._overscan_surface = None
        self._overscan_content_rect = pygame.Rect(0, 0, 0, 0)
        self._overscan_camera_offset = None
        self._overscan_zoom_key = None
        self._overscan_map_key = None
        self._overscan_viewport = None
        self._overscan_zoom_candidate = None
        self._overscan_zoom_stable_frames = 0

    def _scale_map_key(self, map_data: MapData):
        return (
            id(map_data),
            map_data.map_id,
            len(map_data.tiles),
            self.hex_converter.orientation,
        )

    @staticmethod
    def _scale_zoom_key(zoom: float) -> float:
        return round(float(zoom), 5)

    def _overscan_matches_view(
        self,
        map_data: MapData,
        camera_offset: List[float],
        zoom: float,
    ) -> bool:
        if self._overscan_surface is None or self._overscan_camera_offset is None:
            return False
        viewport = (GameConfig.WINDOW_WIDTH, GameConfig.WINDOW_HEIGHT)
        if self._overscan_viewport != viewport:
            return False
        if self._overscan_map_key != self._scale_map_key(map_data):
            return False
        if self._overscan_zoom_key != self._scale_zoom_key(zoom):
            return False

        dx = float(camera_offset[0]) - self._overscan_camera_offset[0]
        dy = float(camera_offset[1]) - self._overscan_camera_offset[1]
        margin = self.OVERSCAN_MARGIN_PX
        return abs(dx) <= margin and abs(dy) <= margin

    def _draw_overscan(self, camera_offset: List[float]) -> int:
        """Draw the current viewport from the cached overscan raster.

        Return the number of source pixels submitted. The source rectangle is
        intersected with the actual terrain content bounds, so a tall/narrow map
        on a wide display does not alpha-blit the large empty side regions.
        """
        if self._overscan_surface is None or self._overscan_camera_offset is None:
            return 0

        width, height = GameConfig.WINDOW_WIDTH, GameConfig.WINDOW_HEIGHT
        margin = self.OVERSCAN_MARGIN_PX
        dx = float(camera_offset[0]) - self._overscan_camera_offset[0]
        dy = float(camera_offset[1]) - self._overscan_camera_offset[1]

        viewport_source = pygame.Rect(
            int(round(margin - dx)),
            int(round(margin - dy)),
            width,
            height,
        )
        source = viewport_source.clip(self._overscan_content_rect)
        source = source.clip(self._overscan_surface.get_rect())
        if source.width <= 0 or source.height <= 0:
            profiling.profiler.set_frame_metric("map_terrain_blits", 0)
            profiling.profiler.set_frame_metric("map_overscan_source_pixels", 0)
            return 0

        destination = (
            source.x - viewport_source.x,
            source.y - viewport_source.y,
        )
        # An area blit is intentionally not part of Surface.blits batching: it
        # replaces hundreds of terrain commands with one bounded pixel copy.
        RMS.draw(self._overscan_surface, destination, area=source)
        pixels = source.width * source.height
        profiling.profiler.set_frame_metric("map_terrain_blits", 1)
        profiling.profiler.set_frame_metric("map_overscan_source_pixels", pixels)
        return pixels

    def _build_overscan_surface(
        self,
        map_data: MapData,
        camera_offset: List[float],
        zoom: float,
    ) -> Tuple[pygame.Surface, pygame.Rect, int]:
        """Rasterize terrain for the viewport plus a reusable pan margin."""
        width, height = GameConfig.WINDOW_WIDTH, GameConfig.WINDOW_HEIGHT
        margin = self.OVERSCAN_MARGIN_PX
        surface = pygame.Surface(
            (width + margin * 2, height + margin * 2), pygame.SRCALPHA
        )

        surface_bounds = surface.get_rect()
        content_rect: Optional[pygame.Rect] = None
        tile_extent = max(2, int(GameConfig.HEX_SIZE * zoom) + 2)
        left = -margin - tile_extent
        right = width + margin + tile_extent
        top = -margin - tile_extent
        bottom = height + margin + tile_extent
        tiles_built = 0

        def include_rect(rect: pygame.Rect) -> None:
            nonlocal content_rect
            clipped = rect.clip(surface_bounds)
            if clipped.width <= 0 or clipped.height <= 0:
                return
            if content_rect is None:
                content_rect = clipped.copy()
            else:
                content_rect.union_ip(clipped)

        for q, r in map_data.tiles:
            tile_entity = map_data.tiles.get((q, r))
            if tile_entity is None:
                continue
            terrain = self.world.get_component(tile_entity, Terrain)
            if terrain is None:
                continue

            world_x, world_y = self.hex_converter.hex_to_pixel(q, r)
            screen_x = world_x * zoom + camera_offset[0]
            screen_y = world_y * zoom + camera_offset[1]
            if not (left <= screen_x <= right and top <= screen_y <= bottom):
                continue

            local_x = screen_x + margin
            local_y = screen_y + margin
            texture = self._get_terrain_texture(terrain.terrain_type, (q, r))

            if texture is not None and self.texture_loaded:
                scaled = self._scaled_terrain_texture(texture, zoom)
                rect = scaled.get_rect(center=(int(local_x), int(local_y)))
                surface.blit(scaled, rect.topleft)
                include_rect(rect)
            else:
                color = GameConfig.TERRAIN_COLORS.get(
                    terrain.terrain_type, (128, 128, 128)
                )
                corners = self.hex_converter.get_hex_corners(q, r)
                points = [
                    (
                        int(round(x * zoom + camera_offset[0] + margin)),
                        int(round(y * zoom + camera_offset[1] + margin)),
                    )
                    for x, y in corners
                ]
                pygame.draw.polygon(surface, color, points)
                pygame.draw.polygon(surface, (0, 0, 0), points, 1)
                xs = [point[0] for point in points]
                ys = [point[1] for point in points]
                include_rect(
                    pygame.Rect(
                        min(xs),
                        min(ys),
                        max(xs) - min(xs) + 1,
                        max(ys) - min(ys) + 1,
                    )
                )

            if terrain.terrain_type == TerrainType.CITY:
                marker_size = max(1, int(12 * zoom))
                center = (int(local_x), int(local_y))
                pygame.draw.circle(surface, (211, 211, 211), center, marker_size)
                pygame.draw.circle(surface, (0, 0, 0), center, marker_size, 2)
                include_rect(
                    pygame.Rect(
                        center[0] - marker_size - 2,
                        center[1] - marker_size - 2,
                        marker_size * 2 + 4,
                        marker_size * 2 + 4,
                    )
                )

            tiles_built += 1

        if content_rect is None:
            content_rect = pygame.Rect(0, 0, 0, 0)
        return surface, content_rect, tiles_built

    def _install_overscan(
        self,
        map_data: MapData,
        camera_offset: List[float],
        zoom: float,
    ) -> None:
        with profiling.profiler.time_system("map_overscan_build", category="render"):
            surface, content_rect, tiles_built = self._build_overscan_surface(
                map_data, camera_offset, zoom
            )

        self._overscan_surface = surface
        self._overscan_content_rect = content_rect
        self._overscan_camera_offset = (
            float(camera_offset[0]),
            float(camera_offset[1]),
        )
        self._overscan_zoom_key = self._scale_zoom_key(zoom)
        self._overscan_map_key = self._scale_map_key(map_data)
        self._overscan_viewport = (
            GameConfig.WINDOW_WIDTH,
            GameConfig.WINDOW_HEIGHT,
        )
        self._overscan_build_count += 1
        profiling.profiler.set_frame_metric("map_overscan_tiles", tiles_built)
        profiling.profiler.set_frame_metric(
            "map_overscan_builds", self._overscan_build_count
        )

    def _render_map_optimized(
        self,
        visible_tiles,
        camera_offset: List[float],
        zoom: float,
    ):
        """Use one overscan blit for pan; direct tiles during continuous zoom."""
        map_data = self.world.get_singleton_component(MapData)
        if not map_data:
            return

        profiling.profiler.set_frame_metric("map_visible_tiles", len(visible_tiles))
        zoom_key = self._scale_zoom_key(zoom)

        if self._overscan_matches_view(map_data, camera_offset, zoom):
            profiling.profiler.set_frame_metric("map_render_mode", "overscan_cached")
            self._draw_overscan(camera_offset)
            return

        if zoom_key == self._overscan_zoom_candidate:
            self._overscan_zoom_stable_frames += 1
        else:
            self._overscan_zoom_candidate = zoom_key
            self._overscan_zoom_stable_frames = 1

        if self._overscan_zoom_stable_frames >= self.OVERSCAN_ZOOM_STABLE_FRAMES:
            self._install_overscan(map_data, camera_offset, zoom)
            profiling.profiler.set_frame_metric("map_render_mode", "overscan_build")
            self._draw_overscan(camera_offset)
            return

        # A new zoom value gets one direct frame. If the next frame keeps the
        # same zoom we build the overscan cache; if zooming continues, stay on
        # the already-proven direct path instead of rebuilding a large Surface.
        profiling.profiler.set_frame_metric("map_render_mode", "direct_zoom")
        profiling.profiler.set_frame_metric(
            "map_terrain_blits", len(visible_tiles)
        )
        profiling.profiler.set_frame_metric("map_overscan_source_pixels", 0)
        self._render_terrain_direct(map_data, visible_tiles, camera_offset, zoom)
