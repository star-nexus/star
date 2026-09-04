"""Core render-system implementations used by the interactive window.

Several UI helpers discover render systems by class name, so these stable names
wrap the optimized implementations used by the window runtime.
"""

from __future__ import annotations

import pygame

from framework.ecs import profiling
from framework.engine import RMS

from ..components import (
    Camera,
    FogOfWar,
    GameState,
    HexPosition,
    UIState,
    Unit,
    UnitCount,
)
from ..prefabs.config import Faction, GameConfig, UnitType
from .fast_render_systems import (
    FastEffectRenderSystem,
    FastMiniMapSystem,
    FastUnitRenderSystem,
)
from .window_map_render_system import WindowMapRenderSystem


class MapRenderSystem(WindowMapRenderSystem):
    pass


class UnitRenderSystem(FastUnitRenderSystem):
    """Renderer retaining rich visuals for small visible sets."""

    COMBAT_FONT_SIZES = (20, 24, 28)
    COMBAT_FONT_PREWARM_TEXT = "0123456789MISSCRIT!+-"
    UNIT_LABEL_FONT_SIZES = (8, 10, 12, 14, 16, 20, 24, 28, 34, 42)
    UNIT_LABELS = {
        UnitType.INFANTRY: "Infantry",
        UnitType.CAVALRY: "Cavalry",
        UnitType.ARCHER: "Archer",
    }

    def __init__(self):
        super().__init__()
        self._full_featured_occupancy_index = None
        self._unit_label_surface_cache = {}

    def initialize(self, world) -> None:
        super().initialize(world)
        animation_system = self._get_animation_system()
        if animation_system:
            self._prewarm_combat_fonts(animation_system)
        self._prewarm_unit_label_surfaces()

    def _prewarm_combat_fonts(self, animation_system) -> None:
        """Prime runtime combat glyphs before the first visible effect."""
        if not animation_system.damage_font:
            return
        try:
            for font_size in self.COMBAT_FONT_SIZES:
                if font_size == 24:
                    font = animation_system.damage_font
                else:
                    font = animation_system.font_dict.get(font_size)
                    if font is None:
                        font = pygame.font.Font(
                            animation_system.font_file_path, font_size
                        )
                        animation_system.font_dict[font_size] = font
                font.render(self.COMBAT_FONT_PREWARM_TEXT, True, (255, 255, 255))
        except (pygame.error, FileNotFoundError) as exc:
            print(f"[UnitRenderSystem] Combat font prewarm skipped: {exc}")

    def _prewarm_unit_label_surfaces(self) -> None:
        """Pre-render the finite rich-unit label set."""
        self._unit_label_surface_cache.clear()
        try:
            for font_size in self.UNIT_LABEL_FONT_SIZES:
                font = self._get_font(font_size)
                if font is None:
                    continue
                for faction in Faction:
                    color = GameConfig.FACTION_COLORS.get(
                        faction, (255, 255, 255)
                    )
                    for unit_type, label in self.UNIT_LABELS.items():
                        self._unit_label_surface_cache[
                            (unit_type, faction, font_size)
                        ] = font.render(label, True, color)
        except (pygame.error, FileNotFoundError) as exc:
            print(f"[UnitRenderSystem] Unit label prewarm skipped: {exc}")

    def _quantize_unit_label_font_size(self, requested_size: int) -> int:
        return min(
            self.UNIT_LABEL_FONT_SIZES,
            key=lambda size: (abs(size - requested_size), size),
        )

    def update(self, delta_time: float) -> None:
        camera = self.world.get_singleton_component(Camera)
        if not camera:
            return

        camera_offset = [camera.offset_x, camera.offset_y]
        zoom = getattr(camera, "zoom", 1.0)
        with profiling.profiler.time_system("unit_visible_cull", category="render"):
            visible_units = self._get_visible_units(camera_offset, zoom)

        if len(visible_units) <= 20:
            self._full_featured_occupancy_index = (
                self._build_full_featured_occupancy_snapshot()
                if visible_units
                else {}
            )
            try:
                self._render_units_full_featured(
                    visible_units, camera_offset, zoom
                )
            finally:
                self._full_featured_occupancy_index = None
        else:
            self._render_units_batch(visible_units, camera_offset, zoom)

        animation_system = self._get_animation_system()
        if animation_system:
            animation_system.render_damage_numbers()

    def _build_full_featured_occupancy_snapshot(self):
        """Build one visibility-correct same-hex index for the rich pass."""
        game_state = self.world.get_singleton_component(GameState)
        fog = self.world.get_singleton_component(FogOfWar)
        ui_state = self.world.get_singleton_component(UIState)
        fog_filter = bool(game_state and fog and fog.enabled and ui_state)
        view_faction = (
            (ui_state.view_faction or game_state.current_player)
            if fog_filter
            else None
        )
        current_vision = (
            fog.faction_vision.get(view_faction, set()) if fog_filter else None
        )

        index = {}
        for entity in self.world.query().with_all(
            HexPosition, Unit, UnitCount
        ).entities():
            position = self.world.get_component(entity, HexPosition)
            unit = self.world.get_component(entity, Unit)
            if position is None or unit is None:
                continue
            if (
                fog_filter
                and unit.faction != view_faction
                and (position.col, position.row) not in current_vision
            ):
                continue
            index.setdefault((position.col, position.row), []).append(entity)
        return index

    def _get_units_in_same_hex(self, target_entity):
        if self._full_featured_occupancy_index is None:
            return super()._get_units_in_same_hex(target_entity)
        target_position = self.world.get_component(target_entity, HexPosition)
        if not target_position:
            return [target_entity]
        return self._full_featured_occupancy_index.get(
            (target_position.col, target_position.row), [target_entity]
        )

    def _render_unit_icon(self, screen_x, screen_y, unit, zoom, scale=1.0):
        requested_size = int(14 * zoom * scale)
        if requested_size < 8:
            return

        font_size = self._quantize_unit_label_font_size(requested_size)
        cache_key = (unit.unit_type, unit.faction, font_size)
        surface = self._unit_label_surface_cache.get(cache_key)
        if surface is None:
            label = self.UNIT_LABELS.get(unit.unit_type, "?")
            font = self._get_font(font_size)
            if font is None:
                return
            color = GameConfig.FACTION_COLORS.get(
                unit.faction, (255, 255, 255)
            )
            surface = font.render(label, True, color)
            self._unit_label_surface_cache[cache_key] = surface
        RMS.draw(surface, surface.get_rect(center=(int(screen_x), int(screen_y))))

    def _render_units_batch(self, visible_units, camera_offset, zoom):
        if not visible_units:
            return

        animation_system = self._get_animation_system()
        units_by_position = {}
        animated_units = []
        for entity in visible_units:
            animated_screen_pos = self._get_fast_animation_screen_position(
                entity, animation_system, camera_offset, zoom
            )
            if animated_screen_pos is not None:
                animated_units.append((entity, animated_screen_pos))
                continue
            position = self.world.get_component(entity, HexPosition)
            if position:
                units_by_position.setdefault(
                    (position.col, position.row), []
                ).append(entity)

        for pos_key, units in units_by_position.items():
            self._render_unit_group_optimized(pos_key, units, camera_offset, zoom)
        for entity, (screen_x, screen_y) in animated_units:
            self._render_single_unit_fast(entity, screen_x, screen_y, zoom)

    def _get_fast_animation_screen_position(
        self, entity, animation_system, camera_offset, zoom
    ):
        """Return the interpolated screen position for an actively moving token."""
        if animation_system is None:
            return None
        render_pos = animation_system.get_unit_render_position(entity)
        position = self.world.get_component(entity, HexPosition)
        if render_pos is None or position is None:
            return None

        base_x, base_y = self.hex_converter.hex_to_pixel(
            position.col, position.row
        )
        dx = render_pos[0] - base_x
        dy = render_pos[1] - base_y
        if dx * dx + dy * dy <= 1.0:
            return None
        return (
            render_pos[0] * zoom + camera_offset[0],
            render_pos[1] * zoom + camera_offset[1],
        )


class EffectRenderSystem(FastEffectRenderSystem):
    pass


class MiniMapSystem(FastMiniMapSystem):
    def _render_minimap(self, minimap):
        if self._frame_surface is not None:
            self._frame_surface.fill((0, 0, 0, 0))
        super()._render_minimap(minimap)
