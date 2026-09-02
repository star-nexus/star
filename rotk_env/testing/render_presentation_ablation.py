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
  content rectangle once per cache build and publish source/display pixel-format
  plus alpha-coverage metadata.
- ``STAR_RENDER_TERRAIN_PRESENT_VARIANT=opaque_flatten``: build a display-native
  opaque copy of the terrain content rectangle against the normal screen clear
  color, then replace only the final terrain source surface while preserving the
  original destination and ``area=`` blit geometry.

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
_TERRAIN_VARIANT_OPAQUE = "opaque_flatten"
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
        f"{prefix}_masks": [int(value) for value in surface.get_masks()],
        f"{prefix}_shifts": [int(value) for value in surface.get_shifts()],
        f"{prefix}_losses": [int(value) for value in surface.get_losses()],
        f"{prefix}_alpha": surface.get_alpha(),
        f"{prefix}_colorkey": _serial_color(surface.get_colorkey()),
    }


def _capture_terrain_surface_state(self, *, build_opaque: bool) -> None:
    """Capture one-build terrain format/alpha evidence and optional opaque clone."""
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

    # ``pygame.mask.from_surface`` performs the scan in native code. Restrict it
    # to the actual content rectangle and run only once per cache build so the
    # diagnostic does not enter the steady-state presentation timing window.
    content_view = surface.subsurface(content)
    total_pixels = int(content.width) * int(content.height)
    if surface.get_flags() & pygame.SRCALPHA:
        nonzero_alpha = pygame.mask.from_surface(content_view, 0).count()
        opaque_alpha = pygame.mask.from_surface(content_view, 254).count()
    else:
        nonzero_alpha = total_pixels
        opaque_alpha = total_pixels
    partial_alpha = max(0, int(nonzero_alpha) - int(opaque_alpha))
    transparent_alpha = max(0, total_pixels - int(nonzero_alpha))
    metadata.update(
        {
            "scale_render_terrain_alpha_total_pixels": total_pixels,
            "scale_render_terrain_alpha_opaque_pixels": int(opaque_alpha),
            "scale_render_terrain_alpha_partial_pixels": partial_alpha,
            "scale_render_terrain_alpha_transparent_pixels": transparent_alpha,
            "scale_render_terrain_alpha_opaque_ratio": (
                float(opaque_alpha) / float(total_pixels) if total_pixels else 0.0
            ),
        }
    )

    if build_opaque:
        if screen is None:
            raise RuntimeError(
                "opaque_flatten terrain diagnostic requires an initialized display surface"
            )
        opaque = pygame.Surface(content.size).convert(screen)
        opaque.fill(_SCREEN_CLEAR_COLOR)
        opaque.blit(surface, (0, 0), content)
        self._star_terrain_opaque_surface = opaque
        self._star_terrain_opaque_content_rect = content.copy()
        metadata.update(
            _surface_format_metadata("scale_render_terrain_opaque", opaque)
        )
        metadata["scale_render_terrain_opaque_pixels"] = total_pixels

    profiling.profiler.set_metadata(**metadata)


def _make_install_with_terrain_diagnostics(
    original: Callable, *, build_opaque: bool
) -> Callable:
    def _install(self, *args, **kwargs):
        result = original(self, *args, **kwargs)
        _capture_terrain_surface_state(self, build_opaque=build_opaque)
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
            # Compatibility fallback for simple test doubles and older presenter
            # implementations that still present the whole semantic surface.
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
    """Replace only the final terrain source surface for a causal blit-path test."""

    def _draw_variant(self, camera_offset):
        queue = getattr(RMS, "_render_queue", None)
        layer = getattr(RMS, "current_layer", 0)
        before_count = 0
        if queue is not None:
            before_count = len(queue.get(layer, ()))

        pixels = original(self, camera_offset)
        replaced = 0

        if pixels and variant == _TERRAIN_VARIANT_OPAQUE and queue is not None:
            commands = queue.get(layer)
            source_surface = getattr(self, "_overscan_surface", None)
            opaque_surface = getattr(self, "_star_terrain_opaque_surface", None)
            opaque_content = getattr(
                self, "_star_terrain_opaque_content_rect", None
            )
            if (
                commands is not None
                and source_surface is not None
                and opaque_surface is not None
                and opaque_content is not None
            ):
                for index in range(len(commands) - 1, before_count - 1, -1):
                    command = commands[index]
                    if getattr(command, "surface", None) is not source_surface:
                        continue
                    area = getattr(command, "area", None)
                    if area is None:
                        continue
                    relative = area.move(-opaque_content.x, -opaque_content.y)
                    if not opaque_surface.get_rect().contains(relative):
                        continue
                    command.surface = opaque_surface
                    command.area = relative
                    replaced = 1
                    break

        missed = int(bool(pixels) and variant == _TERRAIN_VARIANT_OPAQUE and not replaced)
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

    if variant_enabled and variant != _TERRAIN_VARIANT_OPAQUE:
        raise ValueError(
            f"Unsupported {_TERRAIN_VARIANT_ENV}={variant!r}; "
            f"expected {_TERRAIN_VARIANT_OPAQUE!r}"
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
                ScaleMapRenderSystem._install_completed_job = (
                    _make_install_with_terrain_diagnostics(
                        ScaleMapRenderSystem._install_completed_job,
                        build_opaque=variant_enabled,
                    )
                )
                ScaleMapRenderSystem._install_overscan = (
                    _make_install_with_terrain_diagnostics(
                        ScaleMapRenderSystem._install_overscan,
                        build_opaque=variant_enabled,
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
