"""Opt-in causal presentation ablations for scale profiling.

These switches are experiment instrumentation, not production optimizations.
They leave semantic/cache update work intact and remove only the final render
command whose cost we want to isolate.

Environment variables (read once at process import):

- ``STAR_RENDER_ABLATE_FOG_PRESENT=1``: keep incremental fog-surface updates but
  do not enqueue the viewport fog surface for presentation.
- ``STAR_RENDER_ABLATE_TERRAIN_PRESENT=1``: let ``_draw_overscan`` perform its
  normal geometry/source-rect work and enqueue its command, then remove exactly
  that just-created overscan command before RenderEngine consumes the queue.

The wrappers publish ``scale_*`` metadata so formal snapshots self-identify the
active causal ablation. Default behavior is untouched when both flags are off.
"""

from __future__ import annotations

import os
from typing import Callable

from framework.ecs import profiling
from framework.engine import RMS

_TRUE_VALUES = {"1", "true", "yes", "on"}
_FOG_ENV = "STAR_RENDER_ABLATE_FOG_PRESENT"
_TERRAIN_ENV = "STAR_RENDER_ABLATE_TERRAIN_PRESENT"


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in _TRUE_VALUES


def _fog_render_without_present(self, visible_tiles, camera_offset, zoom: float) -> None:
    """Run normal fog semantic/pixel update but suppress the final RMS.draw."""
    surface = self.update_surface(visible_tiles, camera_offset, zoom)
    pixels = 0
    if surface is not None:
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
    """Return a wrapper that removes only the overscan command just enqueued.

    Calling the original method first preserves its source-rectangle clipping,
    cache/accounting work, and RenderCommand allocation. The wrapper then removes
    the newly-added command whose surface is the active overscan raster. This
    makes the RenderEngine delta substantially cleaner than short-circuiting the
    terrain method before it performs normal preparation work.
    """

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
                # Search only commands created by this original call. In the
                # current implementation there is exactly one, but the bounded
                # reverse scan keeps the ablation robust to adjacent diagnostics.
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


def install_render_presentation_ablations() -> bool:
    """Install process-scoped class wrappers when an experiment flag is enabled."""
    fog_enabled = _env_flag(_FOG_ENV)
    terrain_enabled = _env_flag(_TERRAIN_ENV)
    if not fog_enabled and not terrain_enabled:
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

    if terrain_enabled:
        from ..systems.scale_map_render_system import ScaleMapRenderSystem

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

    return installed


__all__ = [
    "install_render_presentation_ablations",
]
