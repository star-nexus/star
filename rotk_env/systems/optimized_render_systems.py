"""Production window renderers assembled from the optimized implementations."""

from ..components import Camera, HexPosition
from .window_render_systems_base import (
    EffectRenderSystem,
    MapRenderSystem as _BaseMapRenderSystem,
    MiniMapSystem,
    UnitRenderSystem as _BaseUnitRenderSystem,
)
from .terrain_presentation_cache import OpaqueTerrainPresentationMixin


class UnitRenderSystem(_BaseUnitRenderSystem):
    """Window unit renderer without animation-position dead zones."""

    _ANIMATION_POSITION_EPSILON_SQ = 1e-12

    def _animation_screen_position(
        self,
        entity,
        animation_system,
        camera_offset,
        zoom,
    ):
        """Return any real animation displacement, however small.

        The previous rich path ignored animation offsets <=5 world pixels and
        the batch path ignored offsets <=1 pixel. At the default 2 tiles/s and
        60 Hz, one movement frame is only ~2.9 world pixels, so those dead zones
        visibly froze a token after committed hex transitions before jumping it
        back onto the interpolated trajectory.
        """
        if animation_system is None:
            return None

        render_pos = animation_system.get_unit_render_position(entity)
        position = self.world.get_component(entity, HexPosition)
        if render_pos is None or position is None:
            return None

        base_x, base_y = self.hex_converter.hex_to_pixel(position.col, position.row)
        dx = render_pos[0] - base_x
        dy = render_pos[1] - base_y
        if dx * dx + dy * dy <= self._ANIMATION_POSITION_EPSILON_SQ:
            return None

        return (
            render_pos[0] * zoom + camera_offset[0],
            render_pos[1] * zoom + camera_offset[1],
        )

    def _render_single_unit_full(
        self, entity, screen_x, screen_y, zoom, animation_system
    ):
        """Feed small animation offsets into the rich renderer before its legacy gate."""
        camera = self.world.get_singleton_component(Camera)
        if camera is not None:
            animated_screen_pos = self._animation_screen_position(
                entity,
                animation_system,
                [camera.offset_x, camera.offset_y],
                zoom,
            )
            if animated_screen_pos is not None:
                screen_x, screen_y = animated_screen_pos

        return super()._render_single_unit_full(
            entity, screen_x, screen_y, zoom, animation_system
        )

    def _get_fast_animation_screen_position(
        self, entity, animation_system, camera_offset, zoom
    ):
        """Use the same zero-dead-zone semantics for the batch path."""
        return self._animation_screen_position(
            entity,
            animation_system,
            camera_offset,
            zoom,
        )


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
