"""Scale-friendly renderers for large STAR maps and unit counts.

These classes keep the existing renderers as the source of visual semantics and
only replace hot paths that were doing expensive work every frame:

* map terrain uses cached texture scaling plus an adaptive direct/raster path;
* terrain/unit texture scaling is cached by pixel size;
* fog and minimap surfaces are reused/cached instead of allocated and redrawn
  from scratch every frame;
* selected-unit movement reachability is recomputed only when the state that
  affects it changes, and one cached hex overlay is reused for all cells;
* unit visibility fetches frame-level singleton state once instead of once per
  unit.

The simulation/rules are untouched. These classes are installed only for the
interactive ``display='window'`` path by ``world_builder``.
"""

from __future__ import annotations

from collections import OrderedDict
from typing import Dict, List, Optional, Tuple

import pygame

from framework.engine import RMS
from framework.ecs import profiling
from ..components import (
    Camera,
    Combat,
    FogOfWar,
    GameState,
    HexPosition,
    MapData,
    MiniMap,
    MovementPoints,
    Terrain,
    UIState,
    Unit,
    UnitCount,
)
from ..prefabs.config import GameConfig, TerrainType
from .effect_render_system import EffectRenderSystem
from .map_render_system import MapRenderSystem
from .minimap_system import MiniMapSystem
from .unit_render_system import UnitRenderSystem


class FastMapRenderSystem(MapRenderSystem):
    """Map renderer with adaptive terrain, texture-scale, and fog caches.

    A viewport raster is excellent while the camera is stationary, but the old
    fast path rebuilt a full-window Surface every frame while panning/zooming.
    Under sustained camera movement that made ``MapRenderSystem`` cost 5-10 ms.

    The adaptive path renders cached per-tile textures directly while the camera
    state is changing, then builds a viewport raster only after the exact camera
    state is observed for a second frame. Once stationary, subsequent frames go
    back to the single cached-raster blit.
    """

    def __init__(self):
        super().__init__()
        self._scaled_terrain_size: Optional[int] = None
        self._scaled_terrain_cache: Dict[int, pygame.Surface] = {}
        self._terrain_surface: Optional[pygame.Surface] = None
        self._terrain_surface_key = None
        self._terrain_candidate_key = None
        self._terrain_stable_frames = 0
        self._terrain_raster_stable_frames = 2
        self._fog_cached_surface: Optional[pygame.Surface] = None
        self._fog_cache_key = None

    def _invalidate_fast_caches(self) -> None:
        self._scaled_terrain_cache.clear()
        self._scaled_terrain_size = None
        self._terrain_surface = None
        self._terrain_surface_key = None
        self._terrain_candidate_key = None
        self._terrain_stable_frames = 0
        self._fog_cached_surface = None
        self._fog_cache_key = None

    def set_hex_orientation(self, orientation) -> None:
        old = self.hex_converter.orientation
        super().set_hex_orientation(orientation)
        if self.hex_converter.orientation != old:
            self._invalidate_fast_caches()

    def _scaled_terrain_texture(
        self, texture: pygame.Surface, zoom: float
    ) -> pygame.Surface:
        size = max(1, int(GameConfig.HEX_SIZE * 2 * zoom))
        if size == GameConfig.HEX_SIZE * 2:
            return texture
        if size != self._scaled_terrain_size:
            # Smooth zoom may visit many sizes. Keep only the active size so the
            # cache stays bounded while each source texture is scaled at most
            # once for that size.
            self._scaled_terrain_size = size
            self._scaled_terrain_cache.clear()
        key = id(texture)
        scaled = self._scaled_terrain_cache.get(key)
        if scaled is None:
            scaled = pygame.transform.scale(texture, (size, size))
            self._scaled_terrain_cache[key] = scaled
        return scaled

    def _terrain_view_key(self, map_data, camera_offset, zoom):
        return (
            id(map_data),
            map_data.map_id,
            (GameConfig.WINDOW_WIDTH, GameConfig.WINDOW_HEIGHT),
            round(float(camera_offset[0]), 3),
            round(float(camera_offset[1]), 3),
            round(float(zoom), 5),
            self.hex_converter.orientation,
        )

    def _render_terrain_direct(
        self,
        map_data: MapData,
        visible_tiles,
        camera_offset: List[float],
        zoom: float,
    ) -> None:
        """Queue visible terrain directly; scaled textures are already cached."""
        for q, r in visible_tiles:
            tile_entity = map_data.tiles.get((q, r))
            if tile_entity is None:
                continue
            terrain = self.world.get_component(tile_entity, Terrain)
            if terrain is None:
                continue

            world_x, world_y = self.hex_converter.hex_to_pixel(q, r)
            screen_x = world_x * zoom + camera_offset[0]
            screen_y = world_y * zoom + camera_offset[1]
            texture = self._get_terrain_texture(terrain.terrain_type, (q, r))

            if texture is not None and self.texture_loaded:
                scaled = self._scaled_terrain_texture(texture, zoom)
                rect = scaled.get_rect(center=(int(screen_x), int(screen_y)))
                RMS.draw(scaled, rect.topleft)
                if terrain.terrain_type == TerrainType.CITY:
                    self._render_city_marker(q, r, camera_offset, zoom)
            else:
                self._render_hex_with_color(
                    terrain.terrain_type, q, r, camera_offset, zoom
                )

    def _build_terrain_surface(
        self,
        map_data: MapData,
        visible_tiles,
        camera_offset: List[float],
        zoom: float,
    ) -> pygame.Surface:
        """Rasterize the current stationary viewport once."""
        viewport = (GameConfig.WINDOW_WIDTH, GameConfig.WINDOW_HEIGHT)
        surface = pygame.Surface(viewport, pygame.SRCALPHA)

        for q, r in visible_tiles:
            tile_entity = map_data.tiles.get((q, r))
            if tile_entity is None:
                continue
            terrain = self.world.get_component(tile_entity, Terrain)
            if terrain is None:
                continue

            world_x, world_y = self.hex_converter.hex_to_pixel(q, r)
            screen_x = world_x * zoom + camera_offset[0]
            screen_y = world_y * zoom + camera_offset[1]
            texture = self._get_terrain_texture(terrain.terrain_type, (q, r))

            if texture is not None and self.texture_loaded:
                scaled = self._scaled_terrain_texture(texture, zoom)
                rect = scaled.get_rect(center=(int(screen_x), int(screen_y)))
                surface.blit(scaled, rect.topleft)
            else:
                color = GameConfig.TERRAIN_COLORS.get(
                    terrain.terrain_type, (128, 128, 128)
                )
                corners = self.hex_converter.get_hex_corners(q, r)
                screen_corners = [
                    (x * zoom + camera_offset[0], y * zoom + camera_offset[1])
                    for x, y in corners
                ]
                pygame.draw.polygon(surface, color, screen_corners)
                pygame.draw.polygon(surface, (0, 0, 0), screen_corners, 1)

            if terrain.terrain_type == TerrainType.CITY:
                marker_size = max(1, int(12 * zoom))
                pygame.draw.circle(
                    surface,
                    (211, 211, 211),
                    (int(screen_x), int(screen_y)),
                    marker_size,
                )
                pygame.draw.circle(
                    surface,
                    (0, 0, 0),
                    (int(screen_x), int(screen_y)),
                    marker_size,
                    2,
                )

        return surface

    def _render_map_optimized(
        self,
        visible_tiles,
        camera_offset: List[float],
        zoom: float,
    ):
        """Use direct rendering while moving; raster cache while stationary."""
        map_data = self.world.get_singleton_component(MapData)
        if not map_data:
            return

        key = self._terrain_view_key(map_data, camera_offset, zoom)
        profiling.profiler.set_frame_metric("map_visible_tiles", len(visible_tiles))

        if self._terrain_surface is not None and key == self._terrain_surface_key:
            profiling.profiler.set_frame_metric("map_render_mode", "cached_raster")
            RMS.draw(self._terrain_surface, (0, 0))
            return

        if key == self._terrain_candidate_key:
            self._terrain_stable_frames += 1
        else:
            self._terrain_candidate_key = key
            self._terrain_stable_frames = 1

        if self._terrain_stable_frames >= self._terrain_raster_stable_frames:
            self._terrain_surface = self._build_terrain_surface(
                map_data, visible_tiles, camera_offset, zoom
            )
            self._terrain_surface_key = key
            profiling.profiler.set_frame_metric("map_render_mode", "raster_build")
            RMS.draw(self._terrain_surface, (0, 0))
            return

        # A changing camera used to allocate/rasterize a full viewport here on
        # every frame. Queueing cached tile blits is substantially cheaper, and
        # RenderEngine batches consecutive simple blits before submitting them.
        profiling.profiler.set_frame_metric("map_render_mode", "direct_moving")
        self._render_terrain_direct(map_data, visible_tiles, camera_offset, zoom)

    def _render_fog_of_war_optimized(
        self,
        visible_tiles,
        camera_offset: List[float],
        zoom: float = 1.0,
    ):
        """Cache the fog raster while camera and visibility are unchanged."""
        game_state = self.world.get_singleton_component(GameState)
        fog = self.world.get_singleton_component(FogOfWar)
        ui_state = self.world.get_singleton_component(UIState)
        if not fog or not fog.enabled or not game_state or not ui_state:
            return

        view_faction = ui_state.view_faction or game_state.current_player
        visible = fog.faction_vision.get(view_faction, set())
        explored = fog.explored_tiles.get(view_faction, set())
        viewport = (GameConfig.WINDOW_WIDTH, GameConfig.WINDOW_HEIGHT)
        key = (
            viewport,
            view_faction,
            round(float(camera_offset[0]), 3),
            round(float(camera_offset[1]), 3),
            round(float(zoom), 5),
            hash(frozenset(visible)),
            hash(frozenset(explored)),
        )
        if self._fog_cached_surface is not None and key == self._fog_cache_key:
            RMS.draw(self._fog_cached_surface, (0, 0))
            return

        surface = pygame.Surface(viewport, pygame.SRCALPHA)
        for q, r in visible_tiles:
            if (q, r) in visible:
                continue
            corners = self.hex_converter.get_hex_corners(q, r)
            screen_corners = [
                (x * zoom + camera_offset[0], y * zoom + camera_offset[1])
                for x, y in corners
            ]
            color = (
                GameConfig.FOG_EXPLORED_COLOR
                if (q, r) in explored
                else GameConfig.FOG_UNEXPLORED_COLOR
            )
            pygame.draw.polygon(surface, color, screen_corners)

        self._fog_cached_surface = surface
        self._fog_cache_key = key
        RMS.draw(surface, (0, 0))


class FastUnitRenderSystem(UnitRenderSystem):
    """Unit renderer with bounded dynamic scale cache and cheaper visibility."""

    def __init__(self):
        super().__init__()
        self._dynamic_texture_cache: OrderedDict[
            Tuple[str, int], pygame.Surface
        ] = OrderedDict()
        self._dynamic_texture_cache_limit = 96

    def _get_cached_texture(self, faction, unit_type, size: int):
        size = max(1, int(size))
        key = f"{faction.value}_{unit_type.value}"
        cache_key = (key, size)

        # Keep the parent's pre-scaled common sizes as the first tier.
        cached = self.scaled_texture_cache.get(cache_key)
        if cached is not None:
            self.cache_hits += 1
            return cached

        cached = self._dynamic_texture_cache.get(cache_key)
        if cached is not None:
            self.cache_hits += 1
            self._dynamic_texture_cache.move_to_end(cache_key)
            return cached

        original = self.unit_textures.get(key)
        if original is None:
            return None

        self.cache_misses += 1
        scaled = pygame.transform.scale(original, (size, size))
        self._dynamic_texture_cache[cache_key] = scaled
        self._dynamic_texture_cache.move_to_end(cache_key)
        while len(self._dynamic_texture_cache) > self._dynamic_texture_cache_limit:
            self._dynamic_texture_cache.popitem(last=False)
        return scaled

    def _get_visible_units(
        self, camera_offset: List[float], zoom: float
    ) -> List[int]:
        """Cull screen first and fetch fog/view state once per frame."""
        margin = 100
        screen_left = (-camera_offset[0] - margin) / zoom
        screen_right = (GameConfig.WINDOW_WIDTH - camera_offset[0] + margin) / zoom
        screen_top = (-camera_offset[1] - margin) / zoom
        screen_bottom = (GameConfig.WINDOW_HEIGHT - camera_offset[1] + margin) / zoom

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

        visible_units: List[int] = []
        entities = self.world.query().with_all(HexPosition, Unit, UnitCount).entities()
        for entity in entities:
            position = self.world.get_component(entity, HexPosition)
            unit = self.world.get_component(entity, Unit)
            if position is None or unit is None:
                continue

            world_x, world_y = self.hex_converter.hex_to_pixel(
                position.col, position.row
            )
            if not (
                screen_left <= world_x <= screen_right
                and screen_top <= world_y <= screen_bottom
            ):
                continue

            if fog_filter and unit.faction != view_faction:
                if (position.col, position.row) not in current_vision:
                    continue
            visible_units.append(entity)

        return visible_units


class FastEffectRenderSystem(EffectRenderSystem):
    """Effect renderer that removes pathfinding and Surface churn per frame."""

    def __init__(self):
        super().__init__()
        self._movement_cache_key = None
        self._movement_cache = set()
        self._move_overlay_cache: Dict[int, pygame.Surface] = {}
        self._unit_position_index: Dict[Tuple[int, int], List[Tuple[int, object]]] = {}

    def update(self, delta_time: float) -> None:
        # One O(units) position index replaces attack-range O(tiles * units)
        # scans in the inherited renderer.
        index: Dict[Tuple[int, int], List[Tuple[int, object]]] = {}
        for entity in self.world.query().with_all(HexPosition, Unit).entities():
            pos = self.world.get_component(entity, HexPosition)
            unit = self.world.get_component(entity, Unit)
            if pos is not None and unit is not None:
                index.setdefault((pos.col, pos.row), []).append((entity, unit.faction))
        self._unit_position_index = index
        super().update(delta_time)

    def _get_enemy_unit_at_position(self, position, friendly_faction):
        for entity, faction in self._unit_position_index.get(position, ()):  # O(1) lookup
            if faction != friendly_faction:
                return entity
        return None

    def _movement_state_key(
        self,
        unit_entity: int,
        position: HexPosition,
        movement: MovementPoints,
        unit_count: Optional[UnitCount],
    ):
        occupancy = tuple(
            sorted(
                (
                    entity,
                    pos.col,
                    pos.row,
                    getattr(unit.faction, "value", str(unit.faction)),
                )
                for entity in self.world.query().with_all(HexPosition, Unit).entities()
                for pos in [self.world.get_component(entity, HexPosition)]
                for unit in [self.world.get_component(entity, Unit)]
                if pos is not None and unit is not None
            )
        )
        map_data = self.world.get_singleton_component(MapData)
        return (
            unit_entity,
            position.col,
            position.row,
            movement.current_mp,
            movement.max_mp,
            unit_count.current_count if unit_count else None,
            id(map_data),
            occupancy,
        )

    def _movement_overlay(self, zoom: float) -> Tuple[pygame.Surface, int]:
        radius = max(1, int(GameConfig.HEX_SIZE * zoom))
        cached = self._move_overlay_cache.get(radius)
        if cached is not None:
            return cached, radius

        surface = pygame.Surface((radius * 2 + 2, radius * 2 + 2), pygame.SRCALPHA)
        corners = self.hex_converter.get_hex_corners(0, 0)
        points = [
            (x * zoom + radius + 1, y * zoom + radius + 1) for x, y in corners
        ]
        pygame.draw.polygon(surface, (0, 0, 255, 100), points)
        # Smooth zoom can produce many pixel radii; a small bounded cache is enough.
        if len(self._move_overlay_cache) >= 32:
            self._move_overlay_cache.clear()
        self._move_overlay_cache[radius] = surface
        return surface, radius

    def _render_movement_range(
        self, unit_entity: int, camera_offset: List[float], zoom: float = 1.0
    ):
        position = self.world.get_component(unit_entity, HexPosition)
        movement = self.world.get_component(unit_entity, MovementPoints)
        unit = self.world.get_component(unit_entity, Unit)
        unit_count = self.world.get_component(unit_entity, UnitCount)
        if not position or not movement or not unit:
            return

        key = self._movement_state_key(unit_entity, position, movement, unit_count)
        if key != self._movement_cache_key:
            from ..utils.map_query import reachable_hexes

            self._movement_cache = reachable_hexes(
                self.world,
                (position.col, position.row),
                movement.spendable(unit_count),
                mover=unit_entity,
            )
            self._movement_cache_key = key

        overlay, radius = self._movement_overlay(zoom)
        margin = radius + 2
        for q, r in self._movement_cache:
            if (q, r) == (position.col, position.row):
                continue
            world_x, world_y = self.hex_converter.hex_to_pixel(q, r)
            screen_x = world_x * zoom + camera_offset[0]
            screen_y = world_y * zoom + camera_offset[1]
            if not (
                -margin <= screen_x <= GameConfig.WINDOW_WIDTH + margin
                and -margin <= screen_y <= GameConfig.WINDOW_HEIGHT + margin
            ):
                continue
            RMS.draw(overlay, (screen_x - radius - 1, screen_y - radius - 1))


class FastMiniMapSystem(MiniMapSystem):
    """Minimap renderer with a cached static terrain/background layer."""

    def __init__(self):
        super().__init__()
        self._static_surface: Optional[pygame.Surface] = None
        self._static_key = None
        self._frame_surface: Optional[pygame.Surface] = None
        self._frame_size: Optional[Tuple[int, int]] = None

    def _render_minimap(self, minimap: MiniMap):
        map_data = self.world.get_singleton_component(MapData)
        camera = self.world.get_singleton_component(Camera)
        if not map_data or not map_data.tiles:
            return

        rect_x, rect_y, rect_w, rect_h = self._get_screen_rect(minimap)
        static_key = (
            id(map_data),
            map_data.map_id,
            len(map_data.tiles),
            rect_w,
            rect_h,
            bool(minimap.show_terrain),
            float(minimap.scale),
            minimap.background_alpha,
        )

        min_q = min(q for q, _ in map_data.tiles)
        max_q = max(q for q, _ in map_data.tiles)
        min_r = min(r for _, r in map_data.tiles)
        max_r = max(r for _, r in map_data.tiles)
        map_width = max_q - min_q + 1
        map_height = max_r - min_r + 1

        if self._static_surface is None or static_key != self._static_key:
            base = pygame.Surface((rect_w, rect_h), pygame.SRCALPHA)
            base.fill((0, 0, 0, minimap.background_alpha))
            self._calculate_world_bounds(map_data)
            if minimap.show_terrain:
                self._render_terrain(
                    base,
                    minimap,
                    map_data,
                    min_q,
                    min_r,
                    map_width,
                    map_height,
                )
            self._static_surface = base
            self._static_key = static_key

        if self._frame_surface is None or self._frame_size != (rect_w, rect_h):
            self._frame_surface = pygame.Surface((rect_w, rect_h), pygame.SRCALPHA)
            self._frame_size = (rect_w, rect_h)

        frame = self._frame_surface
        frame.blit(self._static_surface, (0, 0))
        if minimap.show_units:
            self._render_units(
                frame, minimap, min_q, min_r, map_width, map_height
            )
        if minimap.show_camera_viewport and camera:
            self._render_camera_viewport(
                frame,
                minimap,
                camera,
                min_q,
                min_r,
                map_width,
                map_height,
            )
        pygame.draw.rect(
            frame,
            minimap.border_color,
            (0, 0, rect_w, rect_h),
            minimap.border_width,
        )
        RMS.draw(frame, (rect_x, rect_y))