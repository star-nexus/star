"""Opt-in render presentation diagnostics and causal ablations for scale profiling.

These switches are experiment instrumentation, not production optimizations.
They leave semantic/cache update work intact and alter only the final render
command whose cost we want to isolate.

Environment variables (read once at process import):

- ``STAR_RENDER_ABLATE_FOG_PRESENT=1``: keep incremental fog-surface updates but
  do not enqueue the fog presentation rectangle.
- ``STAR_RENDER_ABLATE_TERRAIN_PRESENT=1``: let ``_draw_overscan`` perform its
  normal geometry/source-rect work and enqueue its command, then remove exactly
  that just-created overscan command before RenderEngine consumes the queue.
- ``STAR_RENDER_TERRAIN_ALPHA_DIAGNOSTICS=1``: inspect the active overscan
  content rectangle once per cache build and publish source/display pixel-format,
  pitch, and alpha-coverage metadata.
- ``STAR_RENDER_TERRAIN_PRESENT_VARIANT=<name>``: run one member of the
  orthogonal terrain-presentation attribution sequence:
    * ``original``: original overscan source and area blit (A);
    * ``compact_alpha``: exact RGBA crop with tight row pitch (B);
    * ``compact_flat_srcalpha``: tight SRCALPHA crop precomposited onto the normal
      screen clear color, so every pixel has alpha 255 (C);
    * ``compact_opaque_rgb``: the same precomposited RGB pixels in an explicit
      32-bit surface with alpha mask 0 and SRCALPHA disabled (D).

The wrappers publish ``scale_*`` metadata so formal snapshots self-identify the
active experiment. Default behavior is untouched when all switches are unset.
"""

from __future__ import annotations

import os
from typing import Callable, Optional

import pygame

from framework.ecs import profiling
from framework.engine import RMS

_TRUE_VALUES = {"1", "true", "yes", "on"}
_FOG_ENV = "STAR_RENDER_ABLATE_FOG_PRESENT"
_TERRAIN_ENV = "STAR_RENDER_ABLATE_TERRAIN_PRESENT"
_TERRAIN_ALPHA_DIAG_ENV = "STAR_RENDER_TERRAIN_ALPHA_DIAGNOSTICS"
_TERRAIN_VARIANT_ENV = "STAR_RENDER_TERRAIN_PRESENT_VARIANT"

_TERRAIN_VARIANT_ORIGINAL = "original"
_TERRAIN_VARIANT_COMPACT_ALPHA = "compact_alpha"
_TERRAIN_VARIANT_COMPACT_FLAT_SRCALPHA = "compact_flat_srcalpha"
_TERRAIN_VARIANT_COMPACT_OPAQUE_RGB = "compact_opaque_rgb"
_TERRAIN_VARIANTS = {
    _TERRAIN_VARIANT_ORIGINAL,
    _TERRAIN_VARIANT_COMPACT_ALPHA,
    _TERRAIN_VARIANT_COMPACT_FLAT_SRCALPHA,
    _TERRAIN_VARIANT_COMPACT_OPAQUE_RGB,
}

_SCREEN_CLEAR_COLOR = (135, 141, 106)


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in _TRUE_VALUES


def _terrain_variant() -> str:
    return os.environ.get(_TERRAIN_VARIANT_ENV, "").strip().lower()


def _serial_color(value):
    if value is None:
        return None
    return [int(channel) for channel in value]


def _surface_format_metadata(prefix: str, surface: Optional[pygame.Surface]) -> dict:
    if surface is None:
        return {
            f"{prefix}_present": False,
        }
    flags = int(surface.get_flags())
    return {
        f"{prefix}_present": True,
        f"{prefix}_flags": flags,
        f"{prefix}_srcalpha": bool(flags & pygame.SRCALPHA),
        f"{prefix}_bitsize": int(surface.get_bitsize()),
        f"{prefix}_bytesize": int(surface.get_bytesize()),
        f"{prefix}_pitch": int(surface.get_pitch()),
        f"{prefix}_masks": [int(value) for value in surface.get_masks()],
        f"{prefix}_shifts": [int(value) for value in surface.get_shifts()],
        f"{prefix}_losses": [int(value) for value in surface.get_losses()],
        f"{prefix}_alpha": surface.get_alpha(),
        f"{prefix}_colorkey": _serial_color(surface.get_colorkey()),
    }


def _alpha_coverage(surface: pygame.Surface) -> tuple[int, int, int, int]:
    total_pixels = int(surface.get_width()) * int(surface.get_height())
    if surface.get_flags() & pygame.SRCALPHA:
        nonzero_alpha = pygame.mask.from_surface(surface, 0).count()
        opaque_alpha = pygame.mask.from_surface(surface, 254).count()
    else:
        nonzero_alpha = total_pixels
        opaque_alpha = total_pixels
    partial_alpha = max(0, int(nonzero_alpha) - int(opaque_alpha))
    transparent_alpha = max(0, total_pixels - int(nonzero_alpha))
    return total_pixels, int(opaque_alpha), partial_alpha, transparent_alpha


def _alpha_coverage_metadata(prefix: str, surface: pygame.Surface) -> dict:
    total, opaque, partial, transparent = _alpha_coverage(surface)
    return {
        f"{prefix}_total_pixels": total,
        f"{prefix}_opaque_pixels": opaque,
        f"{prefix}_partial_pixels": partial,
        f"{prefix}_transparent_pixels": transparent,
        f"{prefix}_opaque_ratio": float(opaque) / float(total) if total else 0.0,
    }


def _make_explicit_opaque_rgb_surface(
    size: tuple[int, int], screen: pygame.Surface
) -> pygame.Surface:
    """Create 32-bit RGB storage with screen RGB channel layout and no alpha mask."""
    screen_masks = screen.get_masks()
    rgb_masks = (
        int(screen_masks[0]),
        int(screen_masks[1]),
        int(screen_masks[2]),
        0,
    )
    opaque = pygame.Surface(size, 0, 32, rgb_masks)
    if opaque.get_flags() & pygame.SRCALPHA:
        raise RuntimeError("explicit opaque terrain surface unexpectedly has SRCALPHA")
    if opaque.get_masks()[3] != 0:
        raise RuntimeError("explicit opaque terrain surface unexpectedly has an alpha mask")
    return opaque


def _build_terrain_variant_surface(
    surface: pygame.Surface,
    content: pygame.Rect,
    screen: pygame.Surface,
    variant: str,
) -> pygame.Surface:
    """Build only the source representation changed by the requested A-D variant."""
    content_view = surface.subsurface(content)

    if variant == _TERRAIN_VARIANT_ORIGINAL:
        return surface

    if variant == _TERRAIN_VARIANT_COMPACT_ALPHA:
        # Exact pixels, exact SRCALPHA semantics, only a tight backing store/pitch.
        return content_view.copy()

    if variant == _TERRAIN_VARIANT_COMPACT_FLAT_SRCALPHA:
        # Preserve the SRCALPHA blit path but remove all non-255 alpha values by
        # precompositing once against the framebuffer clear color.
        flattened = pygame.Surface(
            content.size,
            pygame.SRCALPHA,
            surface.get_bitsize(),
            surface.get_masks(),
        )
        flattened.fill((*_SCREEN_CLEAR_COLOR, 255))
        flattened.blit(surface, (0, 0), content)
        return flattened

    if variant == _TERRAIN_VARIANT_COMPACT_OPAQUE_RGB:
        # Same precomposited RGB result as C, but explicitly remove both the
        # alpha mask and SRCALPHA flag so the final blit can take the opaque path.
        opaque = _make_explicit_opaque_rgb_surface(content.size, screen)
        opaque.fill(_SCREEN_CLEAR_COLOR)
        opaque.blit(surface, (0, 0), content)
        return opaque

    raise ValueError(f"Unsupported terrain presentation variant: {variant!r}")


def _capture_terrain_surface_state(self, *, variant: str = "") -> None:
    """Capture one-build terrain evidence and prepare the selected A-D source."""
    surface = getattr(self, "_overscan_surface", None)
    rect = getattr(self, "_overscan_content_rect", None)
    if surface is None or rect is None:
        return

    content = rect.clip(surface.get_rect())
    if content.width <= 0 or content.height <= 0:
        return

    screen = getattr(RMS, "_screen", None)
    metadata = {}
    metadata.update(_surface_format_metadata("scale_render_terrain_source", surface))
    metadata.update(_surface_format_metadata("scale_render_screen", screen))
    metadata["scale_render_terrain_content_rect"] = [
        int(content.x),
        int(content.y),
        int(content.width),
        int(content.height),
    ]
    metadata["scale_render_terrain_content_pixels"] = int(content.width) * int(
        content.height
    )

    if screen is not None:
        metadata["scale_render_terrain_screen_format_match"] = bool(
            surface.get_bitsize() == screen.get_bitsize()
            and surface.get_masks() == screen.get_masks()
        )
        metadata["scale_render_terrain_screen_rgb_format_match"] = bool(
            surface.get_bitsize() == screen.get_bitsize()
            and surface.get_masks()[:3] == screen.get_masks()[:3]
        )

    # Scan only the actual content rectangle, once per cache build. This is
    # diagnostic/build-time work and does not enter steady-state presentation.
    content_view = surface.subsurface(content)
    metadata.update(
        _alpha_coverage_metadata("scale_render_terrain_alpha", content_view)
    )

    if variant:
        if screen is None:
            raise RuntimeError(
                "terrain presentation variant requires an initialized display surface"
            )
        variant_surface = _build_terrain_variant_surface(
            surface, content, screen, variant
        )
        self._star_terrain_variant_surface = variant_surface
        self._star_terrain_variant_content_rect = content.copy()
        self._star_terrain_variant_name = variant

        metadata["scale_render_terrain_present_variant"] = variant
        metadata.update(
            _surface_format_metadata(
                "scale_render_terrain_variant_surface", variant_surface
            )
        )
        metadata.update(
            _alpha_coverage_metadata(
                "scale_render_terrain_variant_alpha", variant_surface
            )
        )
        metadata["scale_render_terrain_variant_surface_pixels"] = int(
            variant_surface.get_width()
        ) * int(variant_surface.get_height())
        metadata["scale_render_terrain_variant_surface_rgb_format_match"] = bool(
            variant_surface.get_bitsize() == screen.get_bitsize()
            and variant_surface.get_masks()[:3] == screen.get_masks()[:3]
        )

    profiling.profiler.set_metadata(**metadata)


def _make_install_with_terrain_diagnostics(
    original: Callable, *, variant: str
) -> Callable:
    def _install(self, *args, **kwargs):
        result = original(self, *args, **kwargs)
        _capture_terrain_surface_state(self, variant=variant)
        return result

    return _install


def _fog_render_without_present(self, visible_tiles, camera_offset, zoom: float) -> None:
    """Run normal fog semantic/pixel update but suppress the final RMS.draw."""
    surface = self.update_surface(visible_tiles, camera_offset, zoom)
    pixels = 0
    if surface is not None:
        rect = getattr(self, "presentation_rect", None)
        if rect is not None:
            clipped = rect.clip(surface.get_rect())
            pixels = int(clipped.width) * int(clipped.height)
        else:
            width, height = surface.get_size()
            pixels = int(width) * int(height)

    profiler = profiling.profiler
    profiler.set_frame_metric("fog_present_ablation", 1)
    profiler.set_frame_metric("fog_present_suppressed_pixels", pixels)
    profiler.set_metadata(
        scale_render_ablate_fog_present=True,
        scale_render_fog_present_last_suppressed_pixels=pixels,
    )


def _make_terrain_draw_without_present(original: Callable) -> Callable:
    """Return a wrapper that removes only the overscan command just enqueued."""

    def _draw_without_present(self, camera_offset):
        queue = getattr(RMS, "_render_queue", None)
        layer = getattr(RMS, "current_layer", 0)
        before_count = 0
        if queue is not None:
            before_count = len(queue.get(layer, ()))

        pixels = original(self, camera_offset)

        suppressed = 0
        if pixels and queue is not None:
            commands = queue.get(layer)
            if commands is not None and len(commands) > before_count:
                overscan_surface = getattr(self, "_overscan_surface", None)
                for index in range(len(commands) - 1, before_count - 1, -1):
                    command = commands[index]
                    if getattr(command, "surface", None) is overscan_surface:
                        commands.pop(index)
                        suppressed = 1
                        break

        missed = int(bool(pixels) and not bool(suppressed))
        suppressed_pixels = int(pixels) if suppressed else 0
        profiler = profiling.profiler
        profiler.set_frame_metric("map_terrain_present_ablation", 1)
        profiler.set_frame_metric(
            "map_terrain_present_suppressed_commands", suppressed
        )
        profiler.set_frame_metric(
            "map_terrain_present_suppressed_pixels", suppressed_pixels
        )
        profiler.set_frame_metric(
            "map_terrain_present_suppression_missed", missed
        )
        profiler.set_metadata(
            scale_render_ablate_terrain_present=True,
            scale_render_terrain_present_last_suppressed_commands=suppressed,
            scale_render_terrain_present_last_suppressed_pixels=suppressed_pixels,
            scale_render_terrain_present_last_suppression_missed=bool(missed),
        )
        return pixels

    return _draw_without_present


def _make_terrain_draw_variant(original: Callable, variant: str) -> Callable:
    """Preserve geometry/area while replacing only B-D source representation."""

    def _draw_variant(self, camera_offset):
        queue = getattr(RMS, "_render_queue", None)
        layer = getattr(RMS, "current_layer", 0)
        before_count = 0
        if queue is not None:
            before_count = len(queue.get(layer, ()))

        pixels = original(self, camera_offset)

        replaced = 0
        source_surface = getattr(self, "_overscan_surface", None)
        if (
            pixels
            and variant != _TERRAIN_VARIANT_ORIGINAL
            and queue is not None
            and source_surface is not None
        ):
            commands = queue.get(layer)
            variant_surface = getattr(self, "_star_terrain_variant_surface", None)
            variant_content = getattr(
                self, "_star_terrain_variant_content_rect", None
            )
            if (
                commands is not None
                and variant_surface is not None
                and variant_content is not None
            ):
                for index in range(len(commands) - 1, before_count - 1, -1):
                    command = commands[index]
                    if getattr(command, "surface", None) is not source_surface:
                        continue
                    area = getattr(command, "area", None)
                    if area is None:
                        continue
                    relative = area.move(-variant_content.x, -variant_content.y)
                    if not variant_surface.get_rect().contains(relative):
                        continue
                    command.surface = variant_surface
                    command.area = relative
                    replaced = 1
                    break

        replacement_required = bool(pixels) and variant != _TERRAIN_VARIANT_ORIGINAL
        missed = int(replacement_required and not replaced)
        profiling.profiler.set_frame_metric("map_terrain_present_variant", variant)
        profiling.profiler.set_frame_metric(
            "map_terrain_present_variant_replaced_commands", replaced
        )
        profiling.profiler.set_frame_metric(
            "map_terrain_present_variant_replacement_missed", missed
        )
        profiling.profiler.set_metadata(
            scale_render_terrain_present_variant=variant,
            scale_render_terrain_present_variant_last_pixels=int(pixels),
            scale_render_terrain_present_variant_last_replaced_commands=replaced,
            scale_render_terrain_present_variant_last_replacement_missed=bool(missed),
        )
        return pixels

    return _draw_variant


def install_render_presentation_ablations() -> bool:
    """Install process-scoped experiment wrappers when a render flag is enabled."""
    fog_enabled = _env_flag(_FOG_ENV)
    terrain_enabled = _env_flag(_TERRAIN_ENV)
    terrain_diag = _env_flag(_TERRAIN_ALPHA_DIAG_ENV)
    variant = _terrain_variant()
    variant_enabled = bool(variant)

    if variant_enabled and variant not in _TERRAIN_VARIANTS:
        expected = ", ".join(sorted(_TERRAIN_VARIANTS))
        raise ValueError(
            f"Unsupported {_TERRAIN_VARIANT_ENV}={variant!r}; expected one of: {expected}"
        )
    if terrain_enabled and variant_enabled:
        raise ValueError(
            "Terrain present ablation and terrain present variant cannot be enabled together"
        )
    if not fog_enabled and not terrain_enabled and not terrain_diag and not variant_enabled:
        return False

    installed = False

    if fog_enabled:
        from ..systems.fog_surface_presenter import IncrementalFogSurfacePresenter

        if not getattr(
            IncrementalFogSurfacePresenter,
            "_star_fog_present_ablation_installed",
            False,
        ):
            IncrementalFogSurfacePresenter.render = _fog_render_without_present
            IncrementalFogSurfacePresenter._star_fog_present_ablation_installed = True
        installed = True

    if terrain_enabled or terrain_diag or variant_enabled:
        from ..systems.scale_map_render_system import ScaleMapRenderSystem

        if terrain_diag or variant_enabled:
            if not getattr(
                ScaleMapRenderSystem,
                "_star_terrain_surface_diagnostics_installed",
                False,
            ):
                capture_variant = variant if variant_enabled else ""
                ScaleMapRenderSystem._install_completed_job = (
                    _make_install_with_terrain_diagnostics(
                        ScaleMapRenderSystem._install_completed_job,
                        variant=capture_variant,
                    )
                )
                ScaleMapRenderSystem._install_overscan = (
                    _make_install_with_terrain_diagnostics(
                        ScaleMapRenderSystem._install_overscan,
                        variant=capture_variant,
                    )
                )
                ScaleMapRenderSystem._star_terrain_surface_diagnostics_installed = True
            installed = True

        if terrain_enabled:
            if not getattr(
                ScaleMapRenderSystem,
                "_star_terrain_present_ablation_installed",
                False,
            ):
                ScaleMapRenderSystem._draw_overscan = _make_terrain_draw_without_present(
                    ScaleMapRenderSystem._draw_overscan
                )
                ScaleMapRenderSystem._star_terrain_present_ablation_installed = True
            installed = True
        elif variant_enabled:
            if not getattr(
                ScaleMapRenderSystem,
                "_star_terrain_present_variant_installed",
                False,
            ):
                ScaleMapRenderSystem._draw_overscan = _make_terrain_draw_variant(
                    ScaleMapRenderSystem._draw_overscan, variant
                )
                ScaleMapRenderSystem._star_terrain_present_variant_installed = True
            installed = True

    return installed


__all__ = [
    "install_render_presentation_ablations",
]
