"""Incremental Fog-of-War presentation for the interactive map renderer.

The authoritative semantic state remains :class:`FogOfWar`. This presenter
consumes revisioned visibility changes and patches affected hexes while camera
geometry is unchanged. Camera, zoom, viewport, faction, or journal gaps trigger
a canonical full rebuild.

The semantic surface remains viewport-sized so patch coordinates are stable.
Only the conservative rectangle containing rendered Fog pixels is submitted.
"""

from __future__ import annotations

from typing import Iterable, List, Optional, Set, Tuple

import pygame

from framework.ecs import profiling
from framework.engine import RMS

from ..components import FogOfWar, GameState, UIState
from ..prefabs.config import GameConfig
from ..utils.fog_visibility_journal import get_fog_visibility_journal
from ..utils.hex_utils import HexMath

Hex = Tuple[int, int]
WorldCorners = Tuple[Tuple[float, float], ...]


class IncrementalFogSurfacePresenter:
    """Own one viewport-sized semantic Fog surface with bounded presentation."""

    def __init__(self, renderer):
        self.renderer = renderer
        self.surface: Optional[pygame.Surface] = None
        self.presentation_rect: Optional[pygame.Rect] = None
        self.geometry_key = None
        self.journal_revision: Optional[int] = None
        self._tile_world_corner_cache: dict[Hex, WorldCorners] = {}
        self._tile_world_corner_cache_geometry_signature = None

    def reset(self) -> None:
        self.surface = None
        self.presentation_rect = None
        self.geometry_key = None
        self.journal_revision = None

    @staticmethod
    def _geometry_key(
        viewport: Tuple[int, int],
        view_faction,
        camera_offset: List[float],
        zoom: float,
        orientation,
    ) -> Tuple[object, ...]:
        return (
            viewport,
            view_faction,
            round(float(camera_offset[0]), 3),
            round(float(camera_offset[1]), 3),
            round(float(zoom), 5),
            orientation,
        )

    def _tile_world_corners(self, tile: Hex) -> WorldCorners:
        """Return immutable canonical corners from the Fog-local geometry cache."""
        converter = self.renderer.hex_converter
        signature = (converter.size, converter.orientation)
        if self._tile_world_corner_cache_geometry_signature != signature:
            self._tile_world_corner_cache.clear()
            self._tile_world_corner_cache_geometry_signature = signature

        corners = self._tile_world_corner_cache.get(tile)
        if corners is None:
            corners = tuple(converter.get_hex_corners(*tile))
            self._tile_world_corner_cache[tile] = corners
        return corners

    def render(
        self,
        visible_tiles: Set[Hex],
        camera_offset: List[float],
        zoom: float,
    ) -> None:
        surface = self.update_surface(visible_tiles, camera_offset, zoom)
        if surface is None or self.presentation_rect is None:
            return

        source = self.presentation_rect.clip(surface.get_rect())
        if source.width > 0 and source.height > 0:
            RMS.draw(surface, source.topleft, area=source)

    def update_surface(
        self,
        visible_tiles: Set[Hex],
        camera_offset: List[float],
        zoom: float,
    ) -> Optional[pygame.Surface]:
        """Update cached Fog pixels and return the current semantic surface."""
        world = self.renderer.world
        fog = world.get_singleton_component(FogOfWar)
        game_state = world.get_singleton_component(GameState)
        ui_state = world.get_singleton_component(UIState)

        if not fog or not fog.enabled or not game_state or not ui_state:
            return None

        view_faction = ui_state.view_faction or game_state.current_player
        viewport = (GameConfig.WINDOW_WIDTH, GameConfig.WINDOW_HEIGHT)
        geometry_key = self._geometry_key(
            viewport,
            view_faction,
            camera_offset,
            zoom,
            self.renderer.hex_converter.orientation,
        )
        journal = get_fog_visibility_journal(world)

        if self.surface is None or geometry_key != self.geometry_key:
            self._full_rebuild(
                visible_tiles,
                camera_offset,
                zoom,
                fog,
                view_faction,
                viewport,
            )
            self.geometry_key = geometry_key
            self.journal_revision = journal.revision
            return self.surface

        batch = journal.changes_since(self.journal_revision, view_faction)
        if batch.history_lost:
            self._full_rebuild(
                visible_tiles,
                camera_offset,
                zoom,
                fog,
                view_faction,
                viewport,
            )
        elif batch.dirty_tiles:
            self._patch_tiles(
                batch.dirty_tiles,
                visible_tiles,
                camera_offset,
                zoom,
                fog,
                view_faction,
            )

        self.journal_revision = batch.revision
        return self.surface

    def _full_rebuild(
        self,
        visible_tiles: Set[Hex],
        camera_offset: List[float],
        zoom: float,
        fog: FogOfWar,
        view_faction,
        viewport: Tuple[int, int],
    ) -> None:
        with profiling.profiler.time_system(
            "fog_surface_full_build", category="render"
        ):
            with profiling.profiler.time_system(
                "fog_full_build_surface_allocate", category="render"
            ):
                surface = pygame.Surface(viewport, pygame.SRCALPHA)

            visible = fog.faction_vision.get(view_faction, set())
            explored = fog.explored_tiles.get(view_faction, set())
            viewport_rect = surface.get_rect()
            content_rect: Optional[pygame.Rect] = None

            with profiling.profiler.time_system(
                "fog_full_build_tile_loop", category="render"
            ):
                for tile in visible_tiles:
                    # Visible tiles contribute no Fog pixels and therefore need
                    # neither geometry nor inclusion in presentation bounds.
                    if tile in visible:
                        continue
                    tile_rect = self._draw_tile_state(
                        surface,
                        tile,
                        camera_offset,
                        zoom,
                        explored,
                        clear_first=False,
                        tile_is_fogged=True,
                    )
                    clipped = tile_rect.clip(viewport_rect)
                    if clipped.width <= 0 or clipped.height <= 0:
                        continue
                    if content_rect is None:
                        content_rect = clipped.copy()
                    else:
                        content_rect.union_ip(clipped)

            self.surface = surface
            self.presentation_rect = content_rect

    def _patch_tiles(
        self,
        dirty_tiles: Iterable[Hex],
        visible_tiles: Set[Hex],
        camera_offset: List[float],
        zoom: float,
        fog: FogOfWar,
        view_faction,
    ) -> None:
        if self.surface is None:
            return

        # Polygon edges overlap neighboring hexes. Clear only semantic dirty
        # polygons, then redraw fogged tiles in their one-ring repair set.
        dirty_tile_set = set(dirty_tiles)
        patch_candidates: Set[Hex] = set()
        for q, r in dirty_tile_set:
            patch_candidates.update(HexMath.hex_in_range(q, r, 1))
        patch_tiles = patch_candidates.intersection(visible_tiles)

        visible = fog.faction_vision.get(view_faction, set())
        explored = fog.explored_tiles.get(view_faction, set())
        dirty_draw_tiles = [tile for tile in visible_tiles if tile in dirty_tile_set]
        fogged_patch_tiles = [
            tile for tile in visible_tiles if tile in patch_tiles and tile not in visible
        ]

        with profiling.profiler.time_system("fog_surface_patch", category="render"):
            for tile in dirty_draw_tiles:
                self._draw_tile_state(
                    self.surface,
                    tile,
                    camera_offset,
                    zoom,
                    explored,
                    clear_first=True,
                    tile_is_fogged=False,
                )

            for tile in fogged_patch_tiles:
                tile_rect = self._draw_tile_state(
                    self.surface,
                    tile,
                    camera_offset,
                    zoom,
                    explored,
                    clear_first=True,
                    tile_is_fogged=True,
                )
                clipped = tile_rect.clip(self.surface.get_rect())
                if clipped.width > 0 and clipped.height > 0:
                    if self.presentation_rect is None:
                        self.presentation_rect = clipped.copy()
                    else:
                        # Reveals never shrink bounds. Newly fogged patch tiles
                        # expand them immediately; the next full rebuild retightens.
                        self.presentation_rect.union_ip(clipped)

    def _draw_tile_state(
        self,
        surface: pygame.Surface,
        tile: Hex,
        camera_offset: List[float],
        zoom: float,
        explored: Set[Hex],
        *,
        clear_first: bool,
        tile_is_fogged: bool,
    ) -> pygame.Rect:
        corners = self._tile_world_corners(tile)
        points = []
        for index, (world_x, world_y) in enumerate(corners):
            screen_x = int(round(world_x * zoom + camera_offset[0]))
            screen_y = int(round(world_y * zoom + camera_offset[1]))
            points.append((screen_x, screen_y))
            if index == 0:
                min_x = max_x = screen_x
                min_y = max_y = screen_y
            else:
                min_x = min(min_x, screen_x)
                max_x = max(max_x, screen_x)
                min_y = min(min_y, screen_y)
                max_y = max(max_y, screen_y)

        tile_rect = pygame.Rect(
            min_x,
            min_y,
            max_x - min_x + 1,
            max_y - min_y + 1,
        )

        if clear_first:
            pygame.draw.polygon(surface, (0, 0, 0, 0), points)
        if tile_is_fogged:
            color = (
                GameConfig.FOG_EXPLORED_COLOR
                if tile in explored
                else GameConfig.FOG_UNEXPLORED_COLOR
            )
            pygame.draw.polygon(surface, color, points)
        return tile_rect
