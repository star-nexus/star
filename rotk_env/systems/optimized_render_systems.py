"""Compatibility-named scale renderers used by the interactive world.

Several legacy UI helpers discover render systems by ``type(system).__name__``.
Keep those public class names stable while the implementation lives in the
Fast* subclasses.
"""

from .fast_render_systems import (
    FastEffectRenderSystem,
    FastMapRenderSystem,
    FastMiniMapSystem,
    FastUnitRenderSystem,
)


class MapRenderSystem(FastMapRenderSystem):
    pass


class UnitRenderSystem(FastUnitRenderSystem):
    pass


class EffectRenderSystem(FastEffectRenderSystem):
    pass


class MiniMapSystem(FastMiniMapSystem):
    def _render_minimap(self, minimap):
        # The cached frame surface is intentionally reused. Clear dynamic unit/
        # viewport pixels before restoring the cached static terrain layer.
        if self._frame_surface is not None:
            self._frame_surface.fill((0, 0, 0, 0))
        super()._render_minimap(minimap)
