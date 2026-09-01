"""Scale map renderer that amortizes terrain blits while the camera pans.

At 1000 units the remaining sustained interactive cost is no longer map command
construction: ``RenderEngine`` spends roughly 6-7 ms executing hundreds of
terrain blits in a typical 51x51 viewport. ``FastMapRenderSystem`` already
collapses a stationary view to one cached raster, but deliberately falls back to
per-tile blits whenever the camera moves.

This compatibility renderer adds an overscan raster around the viewport. After
one stable-zoom frame it rasterizes the visible terrain plus a screen-space
margin. Subsequent pans within that margin are a single cropped blit; only when
the camera leaves the margin is the overscan surface rebuilt. Continuous zoom
still uses the proven direct-tile path so we do not trade RenderEngine time for a
full raster rebuild on every zoom step.

Overscan rebuilds use a staging surface and split candidate scanning and terrain
rasterization across frames under a small time budget. While a pan rebuild is in
flight, the previous raster supplies the overlapping region and only newly
exposed tiles use the direct path. The active cache is swapped atomically after
the staging build completes.

Terrain and fog are deliberately independent caches. Terrain uses the overscan
raster below; fog presentation consumes the revisioned semantic visibility
journal and patches only dirty hexes while view geometry is unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Iterator, List, Optional, Tuple

import pygame

from framework.ecs import profiling
from framework.engine import RMS

from ..components import MapData, Terrain
from ..prefabs.config import GameConfig, TerrainType
from .fast_render_systems import FastMapRenderSystem
from .fog_surface_presenter import IncrementalFogSurfacePresenter


@dataclass
class _OverscanBuildJob:
    surface: pygame.Surface
    camera_offset: Tuple[float, float]
    zoom: float
    zoom_key: float
    map_key: tuple
    viewport: Tuple[int, int]
    tile_iterator: Iterator
    reason: str
    phase: str = "scan"
    candidates: list = field(default_factory=list)
    candidate_index: int = 0
    content_rect: Optional[pygame.Rect] = None
    tiles_examined: int = 0
    tiles_built: int = 0


class ScaleMapRenderSystem(FastMapRenderSystem):
    """Fast map renderer with pan-friendly terrain and incremental fog."""

    OVERSCAN_MARGIN_PX = 256
    OVERSCAN_ZOOM_STABLE_FRAMES = 2
    OVERSCAN_BUILD_BUDGET_MS = 1.5
    OVERSCAN_BUILD_MAX_ITEMS_PER_STEP = 2048
    OVERSCAN_BUILD_CLOCK_CHECK_INTERVAL = 16

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
        self._overscan_surface_reuses = 0
        self._overscan_build_job: Optional[_OverscanBuildJob] = None
        self._overscan_build_cancel_count = 0
        self._fog_presenter = IncrementalFogSurfacePresenter(self)

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
        self._overscan_build_job = None
        if hasattr(self, "_fog_presenter"):
            self._fog_presenter.reset()

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
        RMS.draw(self._overscan_surface, destination, area=source)
        pixels = source.width * source.height
        profiling.profiler.set_frame_metric("map_terrain_blits", 1)
        profiling.profiler.set_frame_metric("map_overscan_source_pixels", pixels)
        return pixels

    def _active_overscan_geometry_matches(
        self, map_data: MapData, zoom: float
    ) -> bool:
        return bool(
            self._overscan_surface is not None
            and self._overscan_camera_offset is not None
            and self._overscan_viewport
            == (GameConfig.WINDOW_WIDTH, GameConfig.WINDOW_HEIGHT)
            and self._overscan_map_key == self._scale_map_key(map_data)
            and self._overscan_zoom_key == self._scale_zoom_key(zoom)
        )

    def _render_direct_outside_cached_overlap(
        self,
        map_data: MapData,
        visible_tiles,
        camera_offset: List[float],
        zoom: float,
    ) -> int:
        """Use the old raster for overlap and direct-render only exposed tiles.

        A pan beyond the overscan margin used to force either one synchronous
        rebuild or a full direct fallback. During an incremental rebuild the old
        surface still covers most of the new viewport, so retain that one blit
        and submit direct commands only for tiles touching the exposed strips.
        """
        if not self._active_overscan_geometry_matches(map_data, zoom):
            direct_tiles = set(visible_tiles)
            self._render_terrain_direct(map_data, direct_tiles, camera_offset, zoom)
            profiling.profiler.set_frame_metric(
                "map_overscan_fallback_direct_tiles", len(direct_tiles)
            )
            profiling.profiler.set_frame_metric("map_terrain_blits", len(direct_tiles))
            profiling.profiler.set_frame_metric("map_overscan_source_pixels", 0)
            return len(direct_tiles)

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
        cached_source = viewport_source.clip(self._overscan_content_rect)
        cached_source = cached_source.clip(self._overscan_surface.get_rect())
        tile_extent = max(2, int(GameConfig.HEX_SIZE * zoom) + 2)
        direct_tiles = set()

        for q, r in visible_tiles:
            world_x, world_y = self.hex_converter.hex_to_pixel(q, r)
            old_local_x = world_x * zoom + self._overscan_camera_offset[0] + margin
            old_local_y = world_y * zoom + self._overscan_camera_offset[1] + margin
            tile_rect = pygame.Rect(
                int(old_local_x - tile_extent),
                int(old_local_y - tile_extent),
                tile_extent * 2 + 1,
                tile_extent * 2 + 1,
            )
            if not cached_source.contains(tile_rect):
                direct_tiles.add((q, r))

        overlap_pixels = self._draw_overscan(camera_offset)
        if direct_tiles:
            self._render_terrain_direct(map_data, direct_tiles, camera_offset, zoom)
        profiling.profiler.set_frame_metric(
            "map_overscan_fallback_direct_tiles", len(direct_tiles)
        )
        profiling.profiler.set_frame_metric(
            "map_terrain_blits", (1 if overlap_pixels else 0) + len(direct_tiles)
        )
        return len(direct_tiles)

    def _overscan_miss_reason(
        self, map_data: MapData, camera_offset: List[float], zoom: float
    ) -> str:
        viewport = (GameConfig.WINDOW_WIDTH, GameConfig.WINDOW_HEIGHT)
        if self._overscan_surface is None or self._overscan_camera_offset is None:
            return "initial"
        if self._overscan_viewport != viewport:
            return "viewport_changed"
        if self._overscan_map_key != self._scale_map_key(map_data):
            return "map_changed"
        if self._overscan_zoom_key != self._scale_zoom_key(zoom):
            return "zoom_changed"
        dx = float(camera_offset[0]) - self._overscan_camera_offset[0]
        dy = float(camera_offset[1]) - self._overscan_camera_offset[1]
        if abs(dx) > self.OVERSCAN_MARGIN_PX or abs(dy) > self.OVERSCAN_MARGIN_PX:
            return "pan_margin_exceeded"
        return "unknown"

    def _build_job_matches_view(
        self,
        job: _OverscanBuildJob,
        map_data: MapData,
        camera_offset: List[float],
        zoom: float,
    ) -> bool:
        if job.viewport != (GameConfig.WINDOW_WIDTH, GameConfig.WINDOW_HEIGHT):
            return False
        if job.map_key != self._scale_map_key(map_data):
            return False
        if job.zoom_key != self._scale_zoom_key(zoom):
            return False
        dx = float(camera_offset[0]) - job.camera_offset[0]
        dy = float(camera_offset[1]) - job.camera_offset[1]
        return abs(dx) <= self.OVERSCAN_MARGIN_PX and abs(dy) <= self.OVERSCAN_MARGIN_PX

    def _cancel_overscan_build(self) -> None:
        if self._overscan_build_job is not None:
            self._overscan_build_job = None
            self._overscan_build_cancel_count += 1

    def _start_overscan_build(
        self,
        map_data: MapData,
        camera_offset: List[float],
        zoom: float,
        reason: str,
    ) -> None:
        self._cancel_overscan_build()
        width, height = GameConfig.WINDOW_WIDTH, GameConfig.WINDOW_HEIGHT
        margin = self.OVERSCAN_MARGIN_PX
        with profiling.profiler.time_system(
            "map_overscan_surface_allocate", category="render"
        ):
            staging_surface = pygame.Surface(
                (width + margin * 2, height + margin * 2), pygame.SRCALPHA
            )
        self._overscan_build_job = _OverscanBuildJob(
            surface=staging_surface,
            camera_offset=(float(camera_offset[0]), float(camera_offset[1])),
            zoom=float(zoom),
            zoom_key=self._scale_zoom_key(zoom),
            map_key=self._scale_map_key(map_data),
            viewport=(width, height),
            tile_iterator=iter(map_data.tiles.items()),
            reason=reason,
        )
        profiling.profiler.set_frame_metric("map_overscan_rebuild_reason", reason)
        profiling.profiler.set_frame_metric("map_overscan_cleared_pixels", 0)

    def _scan_overscan_candidates(
        self, job: _OverscanBuildJob, deadline: float, item_budget: int
    ) -> int:
        width, height = job.viewport
        margin = self.OVERSCAN_MARGIN_PX
        tile_extent = max(2, int(GameConfig.HEX_SIZE * job.zoom) + 2)
        left = -margin - tile_extent
        right = width + margin + tile_extent
        top = -margin - tile_extent
        bottom = height + margin + tile_extent
        processed = 0

        while processed < item_budget:
            try:
                (q, r), tile_entity = next(job.tile_iterator)
            except StopIteration:
                job.phase = "raster"
                break

            processed += 1
            job.tiles_examined += 1
            if tile_entity is not None:
                terrain = self.world.get_component(tile_entity, Terrain)
                if terrain is not None:
                    world_x, world_y = self.hex_converter.hex_to_pixel(q, r)
                    screen_x = world_x * job.zoom + job.camera_offset[0]
                    screen_y = world_y * job.zoom + job.camera_offset[1]
                    if left <= screen_x <= right and top <= screen_y <= bottom:
                        job.candidates.append((q, r, terrain, screen_x, screen_y))

            if (
                processed % self.OVERSCAN_BUILD_CLOCK_CHECK_INTERVAL == 0
                and time.perf_counter() >= deadline
            ):
                break
        return processed

    @staticmethod
    def _include_job_rect(job: _OverscanBuildJob, rect: pygame.Rect) -> None:
        clipped = rect.clip(job.surface.get_rect())
        if clipped.width <= 0 or clipped.height <= 0:
            return
        if job.content_rect is None:
            job.content_rect = clipped.copy()
        else:
            job.content_rect.union_ip(clipped)

    def _raster_overscan_candidates(
        self, job: _OverscanBuildJob, deadline: float, item_budget: int
    ) -> int:
        margin = self.OVERSCAN_MARGIN_PX
        processed = 0
        while job.candidate_index < len(job.candidates) and processed < item_budget:
            q, r, terrain, screen_x, screen_y = job.candidates[job.candidate_index]
            job.candidate_index += 1
            processed += 1

            local_x = screen_x + margin
            local_y = screen_y + margin
            texture = self._get_terrain_texture(terrain.terrain_type, (q, r))
            if texture is not None and self.texture_loaded:
                scaled = self._scaled_terrain_texture(texture, job.zoom)
                rect = scaled.get_rect(center=(int(local_x), int(local_y)))
                job.surface.blit(scaled, rect.topleft)
                self._include_job_rect(job, rect)
            else:
                color = GameConfig.TERRAIN_COLORS.get(
                    terrain.terrain_type, (128, 128, 128)
                )
                corners = self.hex_converter.get_hex_corners(q, r)
                points = [
                    (
                        int(round(x * job.zoom + job.camera_offset[0] + margin)),
                        int(round(y * job.zoom + job.camera_offset[1] + margin)),
                    )
                    for x, y in corners
                ]
                pygame.draw.polygon(job.surface, color, points)
                pygame.draw.polygon(job.surface, (0, 0, 0), points, 1)
                xs = [point[0] for point in points]
                ys = [point[1] for point in points]
                self._include_job_rect(
                    job,
                    pygame.Rect(
                        min(xs),
                        min(ys),
                        max(xs) - min(xs) + 1,
                        max(ys) - min(ys) + 1,
                    ),
                )

            if terrain.terrain_type == TerrainType.CITY:
                marker_size = max(1, int(12 * job.zoom))
                center = (int(local_x), int(local_y))
                pygame.draw.circle(job.surface, (211, 211, 211), center, marker_size)
                pygame.draw.circle(job.surface, (0, 0, 0), center, marker_size, 2)
                self._include_job_rect(
                    job,
                    pygame.Rect(
                        center[0] - marker_size - 2,
                        center[1] - marker_size - 2,
                        marker_size * 2 + 4,
                        marker_size * 2 + 4,
                    ),
                )

            job.tiles_built += 1
            if (
                processed % self.OVERSCAN_BUILD_CLOCK_CHECK_INTERVAL == 0
                and time.perf_counter() >= deadline
            ):
                break

        if job.candidate_index >= len(job.candidates):
            job.phase = "complete"
        return processed

    def _install_completed_job(self, job: _OverscanBuildJob) -> None:
        self._overscan_surface = job.surface
        self._overscan_content_rect = job.content_rect or pygame.Rect(0, 0, 0, 0)
        self._overscan_camera_offset = job.camera_offset
        self._overscan_zoom_key = job.zoom_key
        self._overscan_map_key = job.map_key
        self._overscan_viewport = job.viewport
        self._overscan_build_count += 1
        self._overscan_build_job = None
        profiling.profiler.set_frame_metric("map_overscan_tiles", job.tiles_built)
        profiling.profiler.set_frame_metric(
            "map_overscan_builds", self._overscan_build_count
        )

    def _advance_overscan_build(self) -> bool:
        job = self._overscan_build_job
        if job is None:
            return False

        deadline = time.perf_counter() + self.OVERSCAN_BUILD_BUDGET_MS / 1000.0
        remaining_budget = self.OVERSCAN_BUILD_MAX_ITEMS_PER_STEP
        if job.phase == "scan":
            with profiling.profiler.time_system(
                "map_overscan_candidate_scan", category="render"
            ):
                used = self._scan_overscan_candidates(job, deadline, remaining_budget)
            remaining_budget -= used

        if job.phase == "raster" and remaining_budget > 0 and time.perf_counter() < deadline:
            with profiling.profiler.time_system(
                "map_overscan_tile_raster", category="render"
            ):
                self._raster_overscan_candidates(job, deadline, remaining_budget)

        profiling.profiler.set_frame_metric("map_overscan_build_phase", job.phase)
        profiling.profiler.set_frame_metric(
            "map_overscan_tiles_examined", job.tiles_examined
        )
        profiling.profiler.set_frame_metric(
            "map_overscan_candidates", len(job.candidates)
        )
        profiling.profiler.set_frame_metric(
            "map_overscan_tiles_built_progress", job.tiles_built
        )
        profiling.profiler.set_frame_metric(
            "map_overscan_build_cancels", self._overscan_build_cancel_count
        )

        if job.phase == "complete":
            self._install_completed_job(job)
            return True
        return False

    def _acquire_overscan_surface(self, size: Tuple[int, int]) -> tuple[pygame.Surface, int]:
        """Reuse the previous surface and clear only its last drawn content."""
        if self._overscan_surface is not None and self._overscan_surface.get_size() == size:
            cleared_pixels = 0
            if self._overscan_content_rect.width > 0 and self._overscan_content_rect.height > 0:
                clear_rect = self._overscan_content_rect.clip(
                    self._overscan_surface.get_rect()
                )
                if clear_rect.width > 0 and clear_rect.height > 0:
                    self._overscan_surface.fill((0, 0, 0, 0), clear_rect)
                    cleared_pixels = clear_rect.width * clear_rect.height
            self._overscan_surface_reuses += 1
            return self._overscan_surface, cleared_pixels

        return pygame.Surface(size, pygame.SRCALPHA), 0

    def _build_overscan_surface(
        self,
        map_data: MapData,
        camera_offset: List[float],
        zoom: float,
    ) -> Tuple[pygame.Surface, pygame.Rect, int]:
        """Rasterize terrain for the viewport plus a reusable pan margin."""
        width, height = GameConfig.WINDOW_WIDTH, GameConfig.WINDOW_HEIGHT
        margin = self.OVERSCAN_MARGIN_PX
        surface, cleared_pixels = self._acquire_overscan_surface(
            (width + margin * 2, height + margin * 2)
        )
        profiling.profiler.set_frame_metric(
            "map_overscan_cleared_pixels", cleared_pixels
        )
        profiling.profiler.set_frame_metric(
            "map_overscan_surface_reuses", self._overscan_surface_reuses
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

    def _render_fog_of_war_optimized(
        self,
        visible_tiles,
        camera_offset: List[float],
        zoom: float = 1.0,
    ) -> None:
        """Patch the cached fog surface from faction-level visibility deltas."""
        self._fog_presenter.render(set(visible_tiles), camera_offset, zoom)

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
            self._cancel_overscan_build()
            profiling.profiler.set_frame_metric("map_render_mode", "overscan_cached")
            self._draw_overscan(camera_offset)
            return

        if zoom_key == self._overscan_zoom_candidate:
            self._overscan_zoom_stable_frames += 1
        else:
            self._overscan_zoom_candidate = zoom_key
            self._overscan_zoom_stable_frames = 1

        if self._overscan_zoom_stable_frames >= self.OVERSCAN_ZOOM_STABLE_FRAMES:
            job = self._overscan_build_job
            if job is None or not self._build_job_matches_view(
                job, map_data, camera_offset, zoom
            ):
                self._start_overscan_build(
                    map_data,
                    camera_offset,
                    zoom,
                    self._overscan_miss_reason(map_data, camera_offset, zoom),
                )
            installed = self._advance_overscan_build()
            if installed and self._overscan_matches_view(
                map_data, camera_offset, zoom
            ):
                profiling.profiler.set_frame_metric(
                    "map_render_mode", "overscan_build_complete"
                )
                self._draw_overscan(camera_offset)
                return
            profiling.profiler.set_frame_metric(
                "map_render_mode", "overscan_building_fallback"
            )
            self._render_direct_outside_cached_overlap(
                map_data, visible_tiles, camera_offset, zoom
            )
            return

        self._cancel_overscan_build()
        profiling.profiler.set_frame_metric("map_render_mode", "direct_zoom")
        profiling.profiler.set_frame_metric(
            "map_terrain_blits", len(visible_tiles)
        )
        profiling.profiler.set_frame_metric("map_overscan_source_pixels", 0)
        self._render_terrain_direct(map_data, visible_tiles, camera_offset, zoom)
