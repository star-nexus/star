"""Production opaque terrain presentation cache for the Pygame renderer.

The scale terrain raster intentionally remains an oversized ``SRCALPHA`` surface
because that representation is convenient for incremental overscan construction.
Presentation is a different concern: formal A/B/C/D attribution showed that the
steady-state SDL/Pygame per-pixel-alpha blit path dominates the remaining terrain
submit cost even when almost every source pixel is opaque.

This mixin therefore keeps the verified overscan build semantics intact and adds
one representation boundary when an overscan cache becomes active:

    oversized SRCALPHA overscan raster
        -> crop actual terrain content
        -> composite once against the frame clear colour
        -> compact 32-bit RGB surface with no alpha mask / no SRCALPHA
        -> steady-state cropped opaque blit

The compact cache is rebuilt only when the underlying overscan cache is installed.
Camera motion inside the overscan margin only changes the source rectangle; it does
not rebuild the compact surface.
"""

from __future__ import annotations

import time
from typing import Optional

import pygame

from framework.ecs import profiling
from framework.engine import RMS

from ..prefabs.config import GameConfig


class OpaqueTerrainPresentationMixin:
    """Add a compact non-SRCALPHA presentation cache to ScaleMapRenderSystem."""

    # Must match GameEngine's per-frame screen clear colour. Keeping the colour
    # here is deliberate: transparent pixels in the semantic overscan raster are
    # flattened exactly once, before any units/effects/fog are composited.
    TERRAIN_PRESENT_CLEAR_COLOR = (135, 141, 106)

    def __init__(self, *args, **kwargs):
        self._terrain_present_surface: Optional[pygame.Surface] = None
        self._terrain_present_source_rect = pygame.Rect(0, 0, 0, 0)
        self._terrain_present_cache_build_count = 0
        self._terrain_present_cache_build_max_ms = 0.0
        self._terrain_overscan_build_step_max_ms = 0.0
        super().__init__(*args, **kwargs)

    def _invalidate_fast_caches(self) -> None:
        super()._invalidate_fast_caches()
        self._terrain_present_surface = None
        self._terrain_present_source_rect = pygame.Rect(0, 0, 0, 0)

    @staticmethod
    def _opaque_rgb_masks(source: pygame.Surface) -> tuple[int, int, int, int]:
        """Use display RGB channel layout while explicitly removing alpha."""
        screen = getattr(RMS, "_screen", None)
        if screen is None and pygame.display.get_init():
            screen = pygame.display.get_surface()
        reference = screen if screen is not None else source
        masks = reference.get_masks()
        return (int(masks[0]), int(masks[1]), int(masks[2]), 0)

    def _build_terrain_present_cache(
        self,
        source: Optional[pygame.Surface],
        content_rect: pygame.Rect,
    ) -> None:
        """Build one compact opaque presentation copy from the semantic raster."""
        if source is None:
            self._terrain_present_surface = None
            self._terrain_present_source_rect = pygame.Rect(0, 0, 0, 0)
            return

        content = content_rect.clip(source.get_rect())
        if content.width <= 0 or content.height <= 0:
            self._terrain_present_surface = None
            self._terrain_present_source_rect = pygame.Rect(0, 0, 0, 0)
            profiling.profiler.set_metadata(
                scale_terrain_present_mode="opaque_compact",
                scale_terrain_present_cache_present=False,
                scale_terrain_present_cache_pixels=0,
            )
            return

        started_ns = time.perf_counter_ns()
        with profiling.profiler.time_system(
            "map_terrain_opaque_present_cache_build", category="render"
        ):
            masks = self._opaque_rgb_masks(source)
            opaque = pygame.Surface(content.size, 0, 32, masks)
            opaque.fill(self.TERRAIN_PRESENT_CLEAR_COLOR)
            opaque.blit(source, (0, 0), content)

        build_ms = (time.perf_counter_ns() - started_ns) / 1_000_000.0
        if opaque.get_flags() & pygame.SRCALPHA:
            raise RuntimeError("terrain opaque presentation cache unexpectedly has SRCALPHA")
        if opaque.get_masks()[3] != 0:
            raise RuntimeError("terrain opaque presentation cache unexpectedly has alpha mask")

        self._terrain_present_surface = opaque
        self._terrain_present_source_rect = content.copy()
        self._terrain_present_cache_build_count += 1
        self._terrain_present_cache_build_max_ms = max(
            self._terrain_present_cache_build_max_ms,
            build_ms,
        )

        profiling.profiler.set_frame_metric("map_terrain_present_cache_builds", 1)
        profiling.profiler.set_frame_metric(
            "map_terrain_present_cache_pixels", content.width * content.height
        )
        profiling.profiler.set_metadata(
            scale_terrain_present_mode="opaque_compact",
            scale_terrain_present_cache_present=True,
            scale_terrain_present_cache_build_count=self._terrain_present_cache_build_count,
            scale_terrain_present_cache_last_build_ms=build_ms,
            scale_terrain_present_cache_max_build_ms=self._terrain_present_cache_build_max_ms,
            scale_terrain_present_cache_pixels=content.width * content.height,
            scale_terrain_present_cache_pitch=int(opaque.get_pitch()),
            scale_terrain_present_cache_srcalpha=False,
            scale_terrain_present_cache_masks=[int(value) for value in opaque.get_masks()],
            scale_terrain_present_cache_source_rect=[
                int(content.x),
                int(content.y),
                int(content.width),
                int(content.height),
            ],
        )

    def _install_completed_job(self, job) -> None:
        """Atomically install semantic overscan + its presentation representation."""
        super()._install_completed_job(job)
        self._build_terrain_present_cache(
            self._overscan_surface,
            self._overscan_content_rect,
        )

    def _install_overscan(self, map_data, camera_offset, zoom: float) -> None:
        """Keep the legacy synchronous install path representation-consistent."""
        started_ns = time.perf_counter_ns()
        super()._install_overscan(map_data, camera_offset, zoom)
        self._build_terrain_present_cache(
            self._overscan_surface,
            self._overscan_content_rect,
        )
        elapsed_ms = (time.perf_counter_ns() - started_ns) / 1_000_000.0
        profiling.profiler.set_metadata(
            scale_terrain_overscan_sync_install_last_ms=elapsed_ms,
        )

    def _advance_overscan_build(self) -> bool:
        """Measure the per-frame rebuild step, including final opaque-cache install."""
        started_ns = time.perf_counter_ns()
        with profiling.profiler.time_system("map_overscan_build_step", category="render"):
            installed = super()._advance_overscan_build()
        elapsed_ms = (time.perf_counter_ns() - started_ns) / 1_000_000.0
        self._terrain_overscan_build_step_max_ms = max(
            self._terrain_overscan_build_step_max_ms,
            elapsed_ms,
        )
        profiling.profiler.set_metadata(
            scale_terrain_overscan_build_step_last_ms=elapsed_ms,
            scale_terrain_overscan_build_step_max_ms=self._terrain_overscan_build_step_max_ms,
        )
        return installed

    def _draw_overscan(self, camera_offset) -> int:
        """Present cached terrain from the compact opaque RGB representation."""
        if (
            self._terrain_present_surface is None
            or self._overscan_surface is None
            or self._overscan_camera_offset is None
        ):
            # Compatibility fallback for tests/legacy callers that manually seed
            # only the semantic overscan fields. Production installs always build
            # the opaque cache before the raster becomes active.
            return super()._draw_overscan(camera_offset)

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

        source = viewport_source.clip(self._terrain_present_source_rect)
        source = source.clip(self._overscan_surface.get_rect())
        if source.width <= 0 or source.height <= 0:
            profiling.profiler.set_frame_metric("map_terrain_blits", 0)
            profiling.profiler.set_frame_metric("map_overscan_source_pixels", 0)
            profiling.profiler.set_frame_metric("map_terrain_present_opaque", 1)
            return 0

        destination = (
            source.x - viewport_source.x,
            source.y - viewport_source.y,
        )
        relative_source = source.move(
            -self._terrain_present_source_rect.x,
            -self._terrain_present_source_rect.y,
        )
        if not self._terrain_present_surface.get_rect().contains(relative_source):
            raise RuntimeError("terrain opaque presentation source rect escaped compact cache")

        # Preserve ``area=`` semantics from the verified overscan path. The A-D
        # experiment therefore changes only source representation, not batching.
        RMS.draw(self._terrain_present_surface, destination, area=relative_source)
        pixels = source.width * source.height
        profiling.profiler.set_frame_metric("map_terrain_blits", 1)
        profiling.profiler.set_frame_metric("map_overscan_source_pixels", pixels)
        profiling.profiler.set_frame_metric("map_terrain_present_opaque", 1)
        return pixels
