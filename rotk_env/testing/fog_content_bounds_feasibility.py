"""Correctness oracles for Fog-content presentation bounds.

This module is experiment/test-only. Production rendering never scans surface
alpha or constructs reference framebuffers.
"""

from __future__ import annotations

from collections import Counter
from typing import Dict, Iterable, Optional, Sequence, Tuple

import pygame

from ..components import FogOfWar
from ..prefabs.config import GameConfig
from ..utils.hex_utils import HexConverter
from .fog_presentation_bounds_feasibility import (
    _screen_rect,
    direct_correctness_cases,
    legacy_presentation_bounds,
)

Hex = Tuple[int, int]

SEMANTIC_STATES = (
    "all_fogged",
    "all_visible",
    "one_visible_rest_fogged",
    "one_fogged_rest_visible",
    "mixed_explored_unexplored",
    "fog_islands",
    "visible_islands",
)


def _rect_values(rect: Optional[pygame.Rect]) -> Optional[list[int]]:
    if rect is None:
        return None
    return [int(rect.x), int(rect.y), int(rect.width), int(rect.height)]


def _normalized_rect(rect: pygame.Rect) -> Optional[pygame.Rect]:
    return rect.copy() if rect.width > 0 and rect.height > 0 else None


def alpha_support_bounds(surface: pygame.Surface) -> Optional[pygame.Rect]:
    """Return the exact non-transparent support; correctness oracle only."""
    return _normalized_rect(surface.get_bounding_rect(min_alpha=1))


def alpha_support_is_contained(
    surface: pygame.Surface, presentation_rect: Optional[pygame.Rect]
) -> bool:
    support = alpha_support_bounds(surface)
    if support is None:
        return presentation_rect is None or presentation_rect.width >= 0
    return presentation_rect is not None and presentation_rect.contains(support)


def deterministic_background(size: Sequence[int]) -> pygame.Surface:
    """Construct a nontrivial deterministic RGBA compositing destination."""
    width, height = int(size[0]), int(size[1])
    surface = pygame.Surface((width, height), pygame.SRCALPHA)
    surface.fill((17, 31, 47, 255))
    for x in range(0, width, 37):
        pygame.draw.line(
            surface,
            ((x * 11 + 23) % 256, (x * 7 + 41) % 256, (x * 3 + 89) % 256, 255),
            (x, 0),
            (x, max(0, height - 1)),
        )
    for y in range(0, height, 29):
        pygame.draw.line(
            surface,
            ((y * 5 + 61) % 256, (y * 13 + 19) % 256, (y * 17 + 7) % 256, 255),
            (0, y),
            (max(0, width - 1), y),
        )
    return surface


def compare_bounded_composites(
    fog_surface: pygame.Surface,
    *,
    legacy_rect: Optional[pygame.Rect],
    candidate_rect: Optional[pygame.Rect],
) -> Dict[str, bool]:
    """Compare legacy/candidate bounded submissions with a full viewport blit."""
    background = deterministic_background(fog_surface.get_size())
    reference = background.copy()
    legacy = background.copy()
    candidate = background.copy()
    reference.blit(fog_surface, (0, 0))
    if legacy_rect is not None:
        legacy.blit(fog_surface, legacy_rect.topleft, area=legacy_rect)
    if candidate_rect is not None:
        candidate.blit(fog_surface, candidate_rect.topleft, area=candidate_rect)
    reference_pixels = pygame.image.tostring(reference, "RGBA")
    return {
        "legacy_equals_full": pygame.image.tostring(legacy, "RGBA")
        == reference_pixels,
        "candidate_equals_full": pygame.image.tostring(candidate, "RGBA")
        == reference_pixels,
        "candidate_equals_legacy": pygame.image.tostring(candidate, "RGBA")
        == pygame.image.tostring(legacy, "RGBA"),
    }


def semantic_sets(
    tiles: Iterable[Hex], state: str
) -> Tuple[set[Hex], set[Hex]]:
    """Return deterministic visible/explored sets for the requested state."""
    ordered = tuple(sorted(tiles))
    all_tiles = set(ordered)
    if not ordered:
        return set(), set()
    if state == "all_fogged":
        return set(), set()
    if state == "all_visible":
        return all_tiles, all_tiles
    if state == "one_visible_rest_fogged":
        return {ordered[0]}, {ordered[0]}
    if state == "one_fogged_rest_visible":
        return set(ordered[1:]), set(ordered[1:])
    if state == "mixed_explored_unexplored":
        return set(), set(ordered[::2])
    if state == "fog_islands":
        fogged = set(ordered[::3])
        return all_tiles.difference(fogged), set(ordered[1::2])
    if state == "visible_islands":
        return set(ordered[::3]), set(ordered[1::2])
    raise ValueError(f"unknown Fog semantic state: {state!r}")


def draw_reference_fog(
    tiles: Iterable[Hex],
    *,
    visible: set[Hex],
    explored: set[Hex],
    hex_converter,
    camera_offset: Sequence[float],
    zoom: float,
    viewport: Sequence[int],
) -> Tuple[pygame.Surface, Optional[pygame.Rect], int]:
    """Draw canonical Fog polygons and return their per-tile clipped union."""
    surface = pygame.Surface((int(viewport[0]), int(viewport[1])), pygame.SRCALPHA)
    viewport_rect = surface.get_rect()
    content_rect = None
    polygon_tiles = 0
    for tile in tiles:
        if tile in visible:
            continue
        corners = hex_converter.get_hex_corners(*tile)
        points = [
            (
                int(round(x * zoom + camera_offset[0])),
                int(round(y * zoom + camera_offset[1])),
            )
            for x, y in corners
        ]
        tile_rect = _screen_rect(corners, camera_offset, zoom)
        color = (
            GameConfig.FOG_EXPLORED_COLOR
            if tile in explored
            else GameConfig.FOG_UNEXPLORED_COLOR
        )
        pygame.draw.polygon(surface, color, points)
        polygon_tiles += 1
        clipped = tile_rect.clip(viewport_rect)
        if clipped.width <= 0 or clipped.height <= 0:
            continue
        if content_rect is None:
            content_rect = clipped.copy()
        else:
            content_rect.union_ip(clipped)
    return surface, content_rect, polygon_tiles


def evaluate_direct_fog_content_matrix() -> Dict[str, object]:
    """Re-evaluate all 510 prior geometry cases using rendering semantics."""
    cases = direct_correctness_cases()
    mismatches = []
    state_counts: Counter[str] = Counter()
    exact = 0
    for index, (name, tiles, supported, offset, zoom, orientation, viewport) in enumerate(cases):
        state = SEMANTIC_STATES[index % len(SEMANTIC_STATES)]
        state_counts[state] += 1
        visible, explored = semantic_sets(tiles, state)
        converter = HexConverter(GameConfig.HEX_SIZE, orientation)
        surface, candidate_rect, polygon_tiles = draw_reference_fog(
            tiles,
            visible=visible,
            explored=explored,
            hex_converter=converter,
            camera_offset=offset,
            zoom=zoom,
            viewport=viewport,
        )
        legacy_rect = legacy_presentation_bounds(
            tiles, converter, offset, zoom, viewport
        )["rect"]
        support = alpha_support_bounds(surface)
        contained = alpha_support_is_contained(surface, candidate_rect)
        composites = compare_bounded_composites(
            surface, legacy_rect=legacy_rect, candidate_rect=candidate_rect
        )
        case_exact = contained and all(composites.values())
        if case_exact:
            exact += 1
            continue
        mismatches.append(
            {
                "case": name,
                "supported_production_topology": supported,
                "semantic_state": state,
                "camera_offset": list(offset),
                "zoom": float(zoom),
                "orientation": orientation.value,
                "viewport": list(viewport),
                "input_tiles": len(tiles),
                "visible_tiles": len(visible),
                "polygon_tiles": polygon_tiles,
                "legacy_rect": _rect_values(legacy_rect),
                "candidate_rect": _rect_values(candidate_rect),
                "alpha_support_rect": _rect_values(support),
                "alpha_support_contained": contained,
                **composites,
            }
        )
    return {
        "comparison_count": len(cases),
        "exact_match_count": exact,
        "mismatch_count": len(mismatches),
        "semantic_state_counts": dict(state_counts),
        "supported_production_topology_mismatches": sum(
            bool(item["supported_production_topology"]) for item in mismatches
        ),
        "unsupported_synthetic_topology_mismatches": sum(
            not bool(item["supported_production_topology"]) for item in mismatches
        ),
        "mismatches": mismatches,
    }


class FogContentBoundsCollector:
    """Validate the candidate path against pixels on every canonical rebuild."""

    def __init__(self, presenter):
        self.presenter = presenter
        self.comparisons: list[Dict[str, object]] = []
        self._previous_tiles: Optional[frozenset[Hex]] = None

    def observe(
        self,
        *,
        surface: pygame.Surface,
        presentation_rect: Optional[pygame.Rect],
        camera_offset: Sequence[float],
        zoom: float,
        visible_tiles,
        view_faction,
        orientation,
        viewport: Sequence[int],
    ) -> None:
        tiles = frozenset(visible_tiles)
        fog = self.presenter.renderer.world.get_singleton_component(FogOfWar)
        visible = set(fog.faction_vision.get(view_faction, set()))
        legacy_rect = legacy_presentation_bounds(
            tiles,
            self.presenter.renderer.hex_converter,
            camera_offset,
            zoom,
            viewport,
        )["rect"]
        candidate_rect = (
            presentation_rect.copy() if presentation_rect is not None else None
        )
        support = alpha_support_bounds(surface)
        contained = alpha_support_is_contained(surface, candidate_rect)
        composites = compare_bounded_composites(
            surface, legacy_rect=legacy_rect, candidate_rect=candidate_rect
        )
        previous = self._previous_tiles
        set_changed = previous is not None and tiles != previous
        self.comparisons.append(
            {
                "comparison_index": len(self.comparisons),
                "camera_offset": [float(camera_offset[0]), float(camera_offset[1])],
                "zoom": float(zoom),
                "viewport": [int(viewport[0]), int(viewport[1])],
                "orientation": getattr(orientation, "value", str(orientation)),
                "input_tile_count": len(tiles),
                "visible_no_fog_tile_count": len(tiles.intersection(visible)),
                "fog_polygon_tile_count": len(tiles.difference(visible)),
                "visible_tiles_set_changed": set_changed,
                "visible_tiles_added": len(tiles.difference(previous or frozenset())),
                "visible_tiles_removed": len((previous or frozenset()).difference(tiles)),
                "legacy_presentation_rect": _rect_values(legacy_rect),
                "candidate_fog_content_rect": _rect_values(candidate_rect),
                "actual_alpha_bounds": _rect_values(support),
                "legacy_source_pixels": 0
                if legacy_rect is None
                else legacy_rect.width * legacy_rect.height,
                "candidate_source_pixels": 0
                if candidate_rect is None
                else candidate_rect.width * candidate_rect.height,
                "alpha_support_contained": contained,
                **composites,
            }
        )
        self._previous_tiles = tiles

    def result(self) -> Dict[str, object]:
        comparisons = self.comparisons
        exact = [
            item
            for item in comparisons
            if item["alpha_support_contained"]
            and item["legacy_equals_full"]
            and item["candidate_equals_full"]
            and item["candidate_equals_legacy"]
        ]
        changed = [item for item in comparisons if item["visible_tiles_set_changed"]]
        exact_changed = [item for item in changed if item in exact]
        return {
            "full_rebuild_comparisons": len(comparisons),
            "exact_match_count": len(exact),
            "mismatch_count": len(comparisons) - len(exact),
            "visible_tiles_set_change_frames": len(changed),
            "exact_on_set_change_frames": len(exact_changed),
            "input_tiles_total": sum(int(item["input_tile_count"]) for item in comparisons),
            "visible_no_fog_tiles_total": sum(
                int(item["visible_no_fog_tile_count"]) for item in comparisons
            ),
            "fog_polygon_tiles_total": sum(
                int(item["fog_polygon_tile_count"]) for item in comparisons
            ),
            "legacy_source_pixels_total": sum(
                int(item["legacy_source_pixels"]) for item in comparisons
            ),
            "candidate_source_pixels_total": sum(
                int(item["candidate_source_pixels"]) for item in comparisons
            ),
            "comparisons": [dict(item) for item in comparisons],
        }


__all__ = [
    "FogContentBoundsCollector",
    "SEMANTIC_STATES",
    "alpha_support_bounds",
    "alpha_support_is_contained",
    "compare_bounded_composites",
    "deterministic_background",
    "draw_reference_fog",
    "evaluate_direct_fog_content_matrix",
    "semantic_sets",
]
