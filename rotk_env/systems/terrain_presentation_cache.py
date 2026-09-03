"""Opaque terrain presentation cache for the Pygame renderer.

The oversized ``SRCALPHA`` surface remains convenient for incremental overscan
construction. Once a completed overscan raster becomes active, this mixin builds
a compact opaque presentation surface:

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
            return

        with profiling.profiler.time_system(
            "map_terrain_opaque_present_cache_build", category="render"
        ):
            masks = self._opaque_rgb_masks(source)
            opaque = pygame.Surface(content.size, 0, 32, masks)
            opaque.fill(self.TERRAIN_PRESENT_CLEAR_COLOR)
            opaque.blit(source, (0, 0), content)

        if opaque.get_flags() & pygame.SRCALPHA:
            raise RuntimeError("terrain opaque presentation cache unexpectedly has SRCALPHA")
        if opaque.get_masks()[3] != 0:
            raise RuntimeError("terrain opaque presentation cache unexpectedly has alpha mask")

        self._terrain_present_surface = opaque
        self._terrain_present_source_rect = content.copy()

    def _install_completed_job(self, job) -> None:
        """Atomically install semantic overscan + its presentation representation."""
        super()._install_completed_job(job)
        self._build_terrain_present_cache(
            self._overscan_surface,
            self._overscan_content_rect,
        )

    def _install_overscan(self, map_data, camera_offset, zoom: float) -> None:
        """Keep synchronous overscan installation representation-consistent."""
        super()._install_overscan(map_data, camera_offset, zoom)
        self._build_terrain_present_cache(
            self._overscan_surface,
            self._overscan_content_rect,
        )

    def _advance_overscan_build(self) -> bool:
        """Advance the incremental rebuild, including final cache installation."""
        with profiling.profiler.time_system("map_overscan_build_step", category="render"):
            installed = super()._advance_overscan_build()
        return installed

    def _draw_overscan(self, camera_offset) -> int:
        """Present cached terrain through the compact opaque representation."""
        if (
            self._terrain_present_surface is None
            or self._overscan_surface is None
            or self._overscan_camera_offset is None
        ):
            # Compatibility fallback for callers that manually seed
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

        # Preserve the overscan path's source-area semantics.
        RMS.draw(self._terrain_present_surface, destination, area=relative_source)
        pixels = source.width * source.height
        return pixels
