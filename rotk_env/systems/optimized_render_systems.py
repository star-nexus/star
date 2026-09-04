"""Production window renderers assembled from the optimized implementations."""

from .window_render_systems_base import (
    EffectRenderSystem,
    MapRenderSystem as _BaseMapRenderSystem,
    MiniMapSystem,
    UnitRenderSystem,
)
from .terrain_presentation_cache import OpaqueTerrainPresentationMixin


class MapRenderSystem(OpaqueTerrainPresentationMixin, _BaseMapRenderSystem):
    """Map renderer with opaque terrain presentation and incremental Fog."""

    def _render_fog_of_war_optimized(
        self,
        visible_tiles,
        camera_offset,
        zoom: float = 1.0,
    ) -> None:
        self._fog_presenter.render(visible_tiles, camera_offset, zoom)


__all__ = ["EffectRenderSystem", "MapRenderSystem", "MiniMapSystem", "UnitRenderSystem"]
