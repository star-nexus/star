"""Incremental fog-of-war presentation for the interactive map renderer.

The authoritative semantic state remains ``FogOfWar``. This presenter consumes
``FogVisibilityChangeJournal`` revisions and patches only the affected hexes while
camera/view geometry is unchanged. It falls back to a full rebuild for first use,
camera/zoom/viewport/faction changes, or journal history gaps.

The semantic surface remains viewport-sized so dirty-tile patch coordinates stay
stable. Presentation is content-bounded: only the screen-space rectangle covered
by visible map hexes is composited into the final framebuffer.
"""

from __future__ import annotations

import time
from collections import Counter
from typing import Dict, Iterable, List, Optional, Set, Tuple

import pygame

from framework.ecs import profiling
from framework.engine import RMS

from ..components import FogOfWar, GameState, UIState
from ..prefabs.config import GameConfig
from ..utils.fog_visibility_journal import get_fog_visibility_journal
from ..utils.hex_utils import HexMath

Hex = Tuple[int, int]

FOG_GEOMETRY_COMPONENTS = (
    "viewport",
    "view_faction",
    "offset_x",
    "offset_y",
    "zoom",
    "orientation",
)
FOG_GEOMETRY_BITS = {
    name: 1 << index for index, name in enumerate(FOG_GEOMETRY_COMPONENTS)
}


class IncrementalFogSurfacePresenter:
    """Own one viewport-sized semantic fog surface with bounded presentation."""

    def __init__(self, renderer):
        self.renderer = renderer
        self.surface: Optional[pygame.Surface] = None
        self.presentation_rect: Optional[pygame.Rect] = None
        self.geometry_key = None
        self.journal_revision: Optional[int] = None
        self.full_builds = 0
        self.patch_updates = 0
        self.full_build_reason_counts: Counter[str] = Counter()
        self.geometry_change_component_counts: Counter[str] = Counter()
        self.geometry_change_detail_counts: Counter[str] = Counter()
        self.full_build_input_tiles = 0
        self.full_build_visible_no_fog_tiles = 0
        self.full_build_polygon_draw_tiles = 0
        self.full_build_tile_loop_time_ns = 0
        self.full_build_polygon_time_ns = 0
        self._polygon_attribution_enabled = False
        self._attribution_events: List[Dict[str, object]] = []
        self._camera_geometry = None

    def reset(self) -> None:
        self.surface = None
        self.presentation_rect = None
        self.geometry_key = None
        self.journal_revision = None
        self._camera_geometry = None

    @staticmethod
    def _geometry_key(
        viewport: Tuple[int, int],
        view_faction,
        camera_offset: List[float],
        zoom: float,
        orientation,
    ) -> Tuple[object, ...]:
        """Return the existing rounded Fog cache key without changing policy."""
        return (
            viewport,
            view_faction,
            round(float(camera_offset[0]), 3),
            round(float(camera_offset[1]), 3),
            round(float(zoom), 5),
            orientation,
        )

    @staticmethod
    def _geometry_change(previous, current) -> Tuple[int, Tuple[str, ...]]:
        if previous is None:
            return 0, ()
        changed = tuple(
            name
            for index, name in enumerate(FOG_GEOMETRY_COMPONENTS)
            if previous[index] != current[index]
        )
        mask = 0
        for name in changed:
            mask |= FOG_GEOMETRY_BITS[name]
        return mask, changed

    def set_full_build_attribution_enabled(
        self, enabled: bool, *, clear_events: bool = False
    ) -> None:
        """Gate per-polygon timing and experiment-only rebuild event capture."""
        self._polygon_attribution_enabled = bool(enabled)
        if clear_events:
            self._attribution_events.clear()

    def diagnostic_snapshot(self) -> Dict[str, object]:
        """Return cumulative counters suitable for exact experiment deltas."""
        return {
            "full_builds": int(self.full_builds),
            "patch_updates": int(self.patch_updates),
            "full_build_reason_counts": dict(self.full_build_reason_counts),
            "geometry_change_component_counts": dict(
                self.geometry_change_component_counts
            ),
            "geometry_change_detail_counts": dict(
                self.geometry_change_detail_counts
            ),
            "full_build_input_tiles": int(self.full_build_input_tiles),
            "full_build_visible_no_fog_tiles": int(
                self.full_build_visible_no_fog_tiles
            ),
            "full_build_polygon_draw_tiles": int(
                self.full_build_polygon_draw_tiles
            ),
            "full_build_tile_loop_time_ns": int(self.full_build_tile_loop_time_ns),
            "full_build_polygon_time_ns": int(self.full_build_polygon_time_ns),
            "polygon_attribution_enabled": self._polygon_attribution_enabled,
            "attribution_events": [dict(event) for event in self._attribution_events],
        }

    def render(
        self,
        visible_tiles: Set[Hex],
        camera_offset: List[float],
        zoom: float,
    ) -> None:
        surface = self.update_surface(visible_tiles, camera_offset, zoom)
        metric = profiling.profiler.set_frame_metric

        if surface is None or self.presentation_rect is None:
            metric("fog_present_source_pixels", 0)
            return

        source = self.presentation_rect.clip(surface.get_rect())
        if source.width <= 0 or source.height <= 0:
            metric("fog_present_source_pixels", 0)
            return

        # ``surface`` remains viewport-sized for stable semantic patch coordinates,
        # but transparent pixels outside the map content rectangle do not need to
        # be alpha-composited every frame. Source and destination use the same
        # screen-space coordinates, preserving the exact full-surface result.
        RMS.draw(surface, source.topleft, area=source)

        source_pixels = int(source.width) * int(source.height)
        full_pixels = int(surface.get_width()) * int(surface.get_height())
        saved_pixels = max(0, full_pixels - source_pixels)
        metric("fog_present_source_pixels", source_pixels)
        metric("fog_present_full_viewport_pixels", full_pixels)
        metric("fog_present_saved_pixels", saved_pixels)
        profiling.profiler.set_metadata(
            scale_fog_present_last_source_pixels=source_pixels,
            scale_fog_present_full_viewport_pixels=full_pixels,
            scale_fog_present_last_saved_pixels=saved_pixels,
            scale_fog_present_last_rect=[
                int(source.x),
                int(source.y),
                int(source.width),
                int(source.height),
            ],
        )

    def update_surface(
        self,
        visible_tiles: Set[Hex],
        camera_offset: List[float],
        zoom: float,
    ) -> Optional[pygame.Surface]:
        """Update cached pixels and return the current fog surface.

        Kept separate from ``render`` so correctness tests can inspect pixels
        without depending on RenderManager/RMS state.
        """
        world = self.renderer.world
        fog = world.get_singleton_component(FogOfWar)
        game_state = world.get_singleton_component(GameState)
        ui_state = world.get_singleton_component(UIState)
        metric = profiling.profiler.set_frame_metric

        if not fog or not fog.enabled or not game_state or not ui_state:
            metric("fog_render_mode", "disabled")
            metric("fog_delta_tiles", 0)
            metric("fog_patch_tiles", 0)
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
        camera_geometry = (
            float(camera_offset[0]),
            float(camera_offset[1]),
            float(zoom),
        )
        journal = get_fog_visibility_journal(world)

        if self.surface is None or geometry_key != self.geometry_key:
            reason = "initial" if self.surface is None else "view_geometry_changed"
            geometry_change_mask, geometry_change_detail = self._geometry_change(
                self.geometry_key, geometry_key
            )
            previous_camera = self._camera_geometry
            camera_delta = (
                0.0
                if previous_camera is None
                else camera_geometry[0] - previous_camera[0],
                0.0
                if previous_camera is None
                else camera_geometry[1] - previous_camera[1],
                0.0
                if previous_camera is None
                else camera_geometry[2] - previous_camera[2],
            )
            self._full_rebuild(
                visible_tiles,
                camera_offset,
                zoom,
                fog,
                view_faction,
                viewport,
                reason=reason,
                geometry_change_mask=geometry_change_mask,
                geometry_change_detail=geometry_change_detail,
                camera_delta=camera_delta,
            )
            self.geometry_key = geometry_key
            self._camera_geometry = camera_geometry
            self.journal_revision = journal.revision
            return self.surface

        batch = journal.changes_since(self.journal_revision, view_faction)
        metric("fog_journal_revision", batch.revision)
        metric("fog_journal_events_scanned", batch.events_scanned)
        metric("fog_journal_history_lost", int(batch.history_lost))
        metric("fog_delta_tiles", len(batch.dirty_tiles))

        if batch.history_lost:
            self._full_rebuild(
                visible_tiles,
                camera_offset,
                zoom,
                fog,
                view_faction,
                viewport,
                reason="journal_gap",
                geometry_change_mask=0,
                geometry_change_detail=(),
                camera_delta=(0.0, 0.0, 0.0),
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
        else:
            metric("fog_render_mode", "cache_reuse")
            metric("fog_patch_tiles", 0)
            metric("fog_full_rebuild_reason", "")
            self._publish_geometry_metrics(0, (), (0.0, 0.0, 0.0))

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
        *,
        reason: str,
        geometry_change_mask: int,
        geometry_change_detail: Tuple[str, ...],
        camera_delta: Tuple[float, float, float],
    ) -> None:
        build_diagnostics: Dict[str, int] = {
            "visible_no_fog_tiles": 0,
            "polygon_draw_tiles": 0,
            "tile_loop_time_ns": 0,
            "polygon_time_ns": 0,
        }
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

            tile_loop_start_ns = (
                time.perf_counter_ns() if self._polygon_attribution_enabled else None
            )
            with profiling.profiler.time_system(
                "fog_full_build_tile_loop", category="render"
            ):
                for tile in visible_tiles:
                    tile_rect = self._draw_tile_state(
                        surface,
                        tile,
                        camera_offset,
                        zoom,
                        visible,
                        explored,
                        clear_first=False,
                        full_build_diagnostics=build_diagnostics,
                    )
                    clipped = tile_rect.clip(viewport_rect)
                    if clipped.width <= 0 or clipped.height <= 0:
                        continue
                    if content_rect is None:
                        content_rect = clipped.copy()
                    else:
                        content_rect.union_ip(clipped)
            if tile_loop_start_ns is not None:
                build_diagnostics["tile_loop_time_ns"] = (
                    time.perf_counter_ns() - tile_loop_start_ns
                )

            self.surface = surface
            self.presentation_rect = content_rect

        self.full_builds += 1
        detail_key = "|".join(geometry_change_detail)
        self.full_build_reason_counts[reason] += 1
        for component in geometry_change_detail:
            self.geometry_change_component_counts[component] += 1
        if detail_key:
            self.geometry_change_detail_counts[detail_key] += 1
        input_tiles = len(visible_tiles)
        visible_no_fog_tiles = build_diagnostics["visible_no_fog_tiles"]
        polygon_draw_tiles = build_diagnostics["polygon_draw_tiles"]
        tile_loop_time_ns = build_diagnostics["tile_loop_time_ns"]
        polygon_time_ns = build_diagnostics["polygon_time_ns"]
        self.full_build_input_tiles += input_tiles
        self.full_build_visible_no_fog_tiles += visible_no_fog_tiles
        self.full_build_polygon_draw_tiles += polygon_draw_tiles
        self.full_build_tile_loop_time_ns += tile_loop_time_ns
        self.full_build_polygon_time_ns += polygon_time_ns

        event = {
            "full_build_counter": self.full_builds,
            "coarse_reason": reason,
            "geometry_change_mask": geometry_change_mask,
            "geometry_change_detail": list(geometry_change_detail),
            "camera_dx": camera_delta[0],
            "camera_dy": camera_delta[1],
            "zoom_delta": camera_delta[2],
            "input_tile_count": input_tiles,
            "visible_no_fog_tile_count": visible_no_fog_tiles,
            "polygon_draw_tile_count": polygon_draw_tiles,
            "tile_loop_time_ns": tile_loop_time_ns,
            "tile_loop_time_ms": tile_loop_time_ns / 1_000_000.0,
            "polygon_time_ns": polygon_time_ns,
            "polygon_time_ms": polygon_time_ns / 1_000_000.0,
        }
        if self._polygon_attribution_enabled:
            self._attribution_events.append(event)

        metric = profiling.profiler.set_frame_metric
        metric("fog_render_mode", "full_build")
        metric("fog_full_rebuild_reason", reason)
        metric("fog_patch_tiles", len(visible_tiles))
        metric("fog_full_builds", self.full_builds)
        metric("fog_patch_updates", self.patch_updates)
        metric("fog_full_build_input_tiles", input_tiles)
        metric("fog_full_build_visible_no_fog_tiles", visible_no_fog_tiles)
        metric("fog_full_build_polygon_draw_tiles", polygon_draw_tiles)
        metric("fog_full_build_tile_loop_time_ns", tile_loop_time_ns)
        metric("fog_full_build_tile_loop_time_ms", tile_loop_time_ns / 1_000_000.0)
        metric("fog_full_build_polygon_time_ns", polygon_time_ns)
        metric("fog_full_build_polygon_time_ms", polygon_time_ns / 1_000_000.0)
        metric(
            "fog_full_build_polygon_timing_enabled",
            int(self._polygon_attribution_enabled),
        )
        self._publish_geometry_metrics(
            geometry_change_mask, geometry_change_detail, camera_delta
        )

    @staticmethod
    def _publish_geometry_metrics(
        geometry_change_mask: int,
        geometry_change_detail: Tuple[str, ...],
        camera_delta: Tuple[float, float, float],
    ) -> None:
        metric = profiling.profiler.set_frame_metric
        metric("fog_geometry_change_mask", geometry_change_mask)
        metric("fog_geometry_change_detail", "|".join(geometry_change_detail))
        metric("fog_rebuild_camera_dx", camera_delta[0])
        metric("fog_rebuild_camera_dy", camera_delta[1])
        metric("fog_rebuild_zoom_delta", camera_delta[2])

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

        # Polygon rasterization includes edge pixels shared by adjacent hexes.
        # Redraw one ring around each semantic dirty tile so clearing one polygon
        # cannot leave a transparent seam on a still-fogged neighbor.
        patch_candidates: Set[Hex] = set()
        for q, r in dirty_tiles:
            patch_candidates.update(HexMath.hex_in_range(q, r, 1))
        patch_tiles = patch_candidates.intersection(visible_tiles)

        visible = fog.faction_vision.get(view_faction, set())
        explored = fog.explored_tiles.get(view_faction, set())
        with profiling.profiler.time_system("fog_surface_patch", category="render"):
            for tile in patch_tiles:
                self._draw_tile_state(
                    self.surface,
                    tile,
                    camera_offset,
                    zoom,
                    visible,
                    explored,
                    clear_first=True,
                )

        self.patch_updates += 1
        metric = profiling.profiler.set_frame_metric
        metric("fog_render_mode", "incremental_patch")
        metric("fog_patch_tiles", len(patch_tiles))
        metric("fog_full_rebuild_reason", "")
        metric("fog_full_builds", self.full_builds)
        metric("fog_patch_updates", self.patch_updates)
        self._publish_geometry_metrics(0, (), (0.0, 0.0, 0.0))

    def _draw_tile_state(
        self,
        surface: pygame.Surface,
        tile: Hex,
        camera_offset: List[float],
        zoom: float,
        visible: Set[Hex],
        explored: Set[Hex],
        *,
        clear_first: bool,
        full_build_diagnostics: Optional[Dict[str, int]] = None,
    ) -> pygame.Rect:
        q, r = tile
        corners = self.renderer.hex_converter.get_hex_corners(q, r)
        points = [
            (
                int(round(x * zoom + camera_offset[0])),
                int(round(y * zoom + camera_offset[1])),
            )
            for x, y in corners
        ]
        min_x = min(point[0] for point in points)
        max_x = max(point[0] for point in points)
        min_y = min(point[1] for point in points)
        max_y = max(point[1] for point in points)
        tile_rect = pygame.Rect(
            min_x,
            min_y,
            max_x - min_x + 1,
            max_y - min_y + 1,
        )

        if clear_first:
            pygame.draw.polygon(surface, (0, 0, 0, 0), points)

        if tile in visible:
            if full_build_diagnostics is not None:
                full_build_diagnostics["visible_no_fog_tiles"] += 1
            return tile_rect

        color = (
            GameConfig.FOG_EXPLORED_COLOR
            if tile in explored
            else GameConfig.FOG_UNEXPLORED_COLOR
        )
        if full_build_diagnostics is not None:
            full_build_diagnostics["polygon_draw_tiles"] += 1
        if full_build_diagnostics is not None and self._polygon_attribution_enabled:
            polygon_start_ns = time.perf_counter_ns()
            pygame.draw.polygon(surface, color, points)
            full_build_diagnostics["polygon_time_ns"] += (
                time.perf_counter_ns() - polygon_start_ns
            )
        else:
            pygame.draw.polygon(surface, color, points)
        return tile_rect
