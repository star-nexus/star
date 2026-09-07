"""Production window renderers assembled from the optimized implementations."""

from framework.engine import RMS
from ..components import Camera, HexPosition, Unit, UnitCount
from ..prefabs.config import GameConfig
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

    def _render_units_batch(self, visible_units, camera_offset, zoom):
        """Share texture preparation only during one synchronous render pass."""
        previous = getattr(self, "_frame_fast_styles", None)
        self._frame_fast_styles = {}
        try:
            return super()._render_units_batch(visible_units, camera_offset, zoom)
        finally:
            self._frame_fast_styles = previous

    def _render_single_unit_fast(self, entity, screen_x, screen_y, zoom):
        styles = getattr(self, "_frame_fast_styles", None)
        if styles is None:
            return super()._render_single_unit_fast(entity, screen_x, screen_y, zoom)
        unit = self.world.get_component(entity, Unit)
        unit_count = self.world.get_component(entity, UnitCount)
        if not unit or not unit_count:
            return
        base_size = int(GameConfig.HEX_SIZE * zoom)
        key = (unit.faction, unit.unit_type, base_size)
        style = styles.get(key)
        if style is None:
            texture = self._get_cached_texture(unit.faction, unit.unit_type, base_size)
            if texture and self.textures_loaded:
                style = (texture, texture.get_width() // 2, texture.get_height() // 2)
            else:
                style = (None, 0, 0)
            styles[key] = style
        texture, half_width, half_height = style
        if texture is not None:
            # Equivalent to get_rect(center=(int(x), int(y))).topleft, including
            # negative coordinates and odd dimensions. Keep painter order intact.
            RMS.draw(texture, (int(screen_x) - half_width, int(screen_y) - half_height))
        else:
            unit_radius = int(base_size // 2)
            color = GameConfig.FACTION_COLORS.get(unit.faction, (255, 255, 255))
            RMS.circle(color, (int(screen_x), int(screen_y)), unit_radius)
            RMS.circle((0, 0, 0), (int(screen_x), int(screen_y)), unit_radius, 2)
        if unit_count.current_count < unit_count.max_count:
            self._render_simple_health_bar(screen_x, screen_y, unit_count, base_size)

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
