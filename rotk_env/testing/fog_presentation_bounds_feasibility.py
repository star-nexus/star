"""Correctness-only Fog presentation-bounds decoupling probe."""

from __future__ import annotations

from collections import Counter, deque
from typing import Dict, Iterable, Optional, Sequence, Tuple

import pygame

from ..prefabs.config import GameConfig, HexOrientation
from ..utils.hex_utils import HexConverter, HexMath

Hex = Tuple[int, int]
WorldBounds = Tuple[float, float, float, float]


def _rect_values(rect: Optional[pygame.Rect]) -> Optional[list[int]]:
    if rect is None:
        return None
    return [int(rect.x), int(rect.y), int(rect.width), int(rect.height)]


def _screen_rect(corners, camera_offset: Sequence[float], zoom: float) -> pygame.Rect:
    points = []
    min_x = min_y = max_x = max_y = None
    for world_x, world_y in corners:
        screen_x = int(round(world_x * zoom + camera_offset[0]))
        screen_y = int(round(world_y * zoom + camera_offset[1]))
        points.append((screen_x, screen_y))
        if min_x is None:
            min_x = max_x = screen_x
            min_y = max_y = screen_y
        else:
            min_x = min(min_x, screen_x)
            max_x = max(max_x, screen_x)
            min_y = min(min_y, screen_y)
            max_y = max(max_y, screen_y)
    if not points:
        return pygame.Rect(0, 0, 0, 0)
    return pygame.Rect(min_x, min_y, max_x - min_x + 1, max_y - min_y + 1)


def canonical_world_bounds(
    visible_tiles: Iterable[Hex], hex_converter
) -> Optional[WorldBounds]:
    """Return global extrema of the canonical six world corners per tile."""
    min_world_x = min_world_y = max_world_x = max_world_y = None
    for q, r in visible_tiles:
        for world_x, world_y in hex_converter.get_hex_corners(q, r):
            if min_world_x is None:
                min_world_x = max_world_x = world_x
                min_world_y = max_world_y = world_y
            else:
                min_world_x = min(min_world_x, world_x)
                max_world_x = max(max_world_x, world_x)
                min_world_y = min(min_world_y, world_y)
                max_world_y = max(max_world_y, world_y)
    if min_world_x is None:
        return None
    return min_world_x, min_world_y, max_world_x, max_world_y


def candidate_presentation_bounds(
    visible_tiles: Iterable[Hex],
    hex_converter,
    camera_offset: Sequence[float],
    zoom: float,
    viewport: Sequence[int],
) -> Dict[str, object]:
    """Transform four world extrema once; never changes production bounds."""
    if zoom <= 0.0:
        raise ValueError("presentation-bounds candidate requires positive zoom")
    world_bounds = canonical_world_bounds(visible_tiles, hex_converter)
    if world_bounds is None:
        return {"world_bounds": None, "unclipped_rect": None, "rect": None}
    min_world_x, min_world_y, max_world_x, max_world_y = world_bounds
    min_x = int(round(min_world_x * zoom + camera_offset[0]))
    max_x = int(round(max_world_x * zoom + camera_offset[0]))
    min_y = int(round(min_world_y * zoom + camera_offset[1]))
    max_y = int(round(max_world_y * zoom + camera_offset[1]))
    unclipped = pygame.Rect(
        min_x,
        min_y,
        max_x - min_x + 1,
        max_y - min_y + 1,
    )
    clipped = unclipped.clip(pygame.Rect(0, 0, int(viewport[0]), int(viewport[1])))
    return {
        "world_bounds": world_bounds,
        "unclipped_rect": unclipped,
        "rect": clipped if clipped.width > 0 and clipped.height > 0 else None,
    }


def legacy_presentation_bounds(
    visible_tiles: Iterable[Hex],
    hex_converter,
    camera_offset: Sequence[float],
    zoom: float,
    viewport: Sequence[int],
) -> Dict[str, object]:
    """Reproduce the authoritative per-tile clip-and-union algorithm."""
    viewport_rect = pygame.Rect(0, 0, int(viewport[0]), int(viewport[1]))
    unclipped_union = None
    clipped_union = None
    for tile in visible_tiles:
        tile_rect = _screen_rect(
            hex_converter.get_hex_corners(*tile), camera_offset, zoom
        )
        if unclipped_union is None:
            unclipped_union = tile_rect.copy()
        else:
            unclipped_union.union_ip(tile_rect)
        clipped = tile_rect.clip(viewport_rect)
        if clipped.width <= 0 or clipped.height <= 0:
            continue
        if clipped_union is None:
            clipped_union = clipped.copy()
        else:
            clipped_union.union_ip(clipped)
    return {"unclipped_rect": unclipped_union, "rect": clipped_union}


def _is_disconnected(tiles: frozenset[Hex]) -> bool:
    if len(tiles) < 2:
        return False
    remaining = set(tiles)
    queue = deque([remaining.pop()])
    while queue:
        q, r = queue.popleft()
        neighbors = set(HexMath.hex_neighbors(q, r))
        found = remaining.intersection(neighbors)
        remaining.difference_update(found)
        queue.extend(found)
    return bool(remaining)


def classify_mismatch(
    *,
    visible_tiles: frozenset[Hex],
    legacy_rect: Optional[pygame.Rect],
    recomputed_legacy_rect: Optional[pygame.Rect],
    recomputed_legacy_unclipped: Optional[pygame.Rect],
    candidate_rect: Optional[pygame.Rect],
    candidate_unclipped: Optional[pygame.Rect],
    set_changed: bool,
) -> list[str]:
    categories: list[str] = []
    if not visible_tiles or legacy_rect is None or candidate_rect is None:
        categories.append("EMPTY_OR_NO_INTERSECTION")
    if candidate_unclipped != recomputed_legacy_unclipped:
        categories.append("ROUNDING_OR_EXTREMA")
    elif candidate_rect != recomputed_legacy_rect:
        categories.append("VIEWPORT_CLIPPING")
    if _is_disconnected(visible_tiles):
        categories.append("SPARSE_OR_DISCONNECTED_TILE_SET")
    if set_changed:
        categories.append("VISIBLE_TILE_SET_CHANGE")
    if legacy_rect != recomputed_legacy_rect:
        categories.append("OTHER_LEGACY_RECOMPUTE_DIVERGENCE")
    if not categories:
        categories.append("OTHER")
    return categories


class PresentationBoundsCollector:
    """Compare candidate and authoritative legacy bounds on every full rebuild."""

    def __init__(self, hex_converter):
        self.hex_converter = hex_converter
        self.comparisons: list[Dict[str, object]] = []
        self._previous_tiles: Optional[frozenset[Hex]] = None
        self._previous_set = None
        self._set_generation = 0

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
        del surface, view_faction
        tiles = frozenset(visible_tiles)
        object_changed = self._previous_set is not None and visible_tiles is not self._previous_set
        set_changed = self._previous_tiles is not None and tiles != self._previous_tiles
        if self._previous_set is None or object_changed:
            self._set_generation += 1
        added = tiles.difference(self._previous_tiles or frozenset())
        removed = (self._previous_tiles or frozenset()).difference(tiles)
        candidate = candidate_presentation_bounds(
            tiles, self.hex_converter, camera_offset, zoom, viewport
        )
        recomputed = legacy_presentation_bounds(
            tiles, self.hex_converter, camera_offset, zoom, viewport
        )
        legacy_rect = presentation_rect.copy() if presentation_rect is not None else None
        exact = legacy_rect == candidate["rect"]
        categories = []
        if not exact:
            categories = classify_mismatch(
                visible_tiles=tiles,
                legacy_rect=legacy_rect,
                recomputed_legacy_rect=recomputed["rect"],
                recomputed_legacy_unclipped=recomputed["unclipped_rect"],
                candidate_rect=candidate["rect"],
                candidate_unclipped=candidate["unclipped_rect"],
                set_changed=set_changed,
            )
        self.comparisons.append(
            {
                "comparison_index": len(self.comparisons),
                "camera_offset": [float(camera_offset[0]), float(camera_offset[1])],
                "zoom": float(zoom),
                "viewport": [int(viewport[0]), int(viewport[1])],
                "orientation": getattr(orientation, "value", str(orientation)),
                "visible_tiles_count": len(tiles),
                "visible_tiles_object_id": id(visible_tiles),
                "visible_tiles_generation": self._set_generation,
                "set_object_changed_since_previous_rebuild": object_changed,
                "set_changed_since_previous_rebuild": set_changed,
                "visible_tiles_added": len(added),
                "visible_tiles_removed": len(removed),
                "visible_tiles_disconnected": _is_disconnected(tiles),
                "legacy_rect": _rect_values(legacy_rect),
                "recomputed_legacy_rect": _rect_values(recomputed["rect"]),
                "candidate_rect": _rect_values(candidate["rect"]),
                "candidate_unclipped_rect": _rect_values(candidate["unclipped_rect"]),
                "world_bounds": list(candidate["world_bounds"])
                if candidate["world_bounds"] is not None
                else None,
                "legacy_recomputed_exact": legacy_rect == recomputed["rect"],
                "exact_match": exact,
                "mismatch_categories": categories,
            }
        )
        self._previous_tiles = tiles
        self._previous_set = visible_tiles

    def result(self) -> Dict[str, object]:
        comparisons = self.comparisons
        mismatches = [item for item in comparisons if not item["exact_match"]]
        changed = [item for item in comparisons if item["set_changed_since_previous_rebuild"]]
        counts = Counter(
            category for item in mismatches for category in item["mismatch_categories"]
        )
        return {
            "full_rebuild_comparisons": len(comparisons),
            "exact_match_count": len(comparisons) - len(mismatches),
            "mismatch_count": len(mismatches),
            "visible_tiles_set_change_frames": len(changed),
            "exact_on_set_change_frames": sum(bool(item["exact_match"]) for item in changed),
            "visible_tiles_object_change_frames": sum(
                bool(item["set_object_changed_since_previous_rebuild"])
                for item in comparisons
            ),
            "maximum_visible_tiles": max(
                (int(item["visible_tiles_count"]) for item in comparisons), default=0
            ),
            "minimum_visible_tiles": min(
                (int(item["visible_tiles_count"]) for item in comparisons), default=0
            ),
            "mismatch_category_counts": dict(counts),
            "comparisons": [dict(item) for item in comparisons],
        }


def direct_correctness_cases():
    """Return the 510 deterministic geometry cases used by feasibility probes."""
    shapes = {
        "empty": (set(), True),
        "single": ({(0, 0)}, True),
        "two_adjacent": ({(0, 0), (1, 0)}, True),
        "small_cluster": ({(0, 0), (1, 0), (0, 1), (-1, 0), (0, -1)}, True),
        "rectangular_grid": (
            {(q, r) for q in range(-3, 4) for r in range(-2, 3)},
            True,
        ),
        "sparse": ({(-20, -10), (-3, 7), (0, 0), (8, -12), (24, 15)}, False),
        "disconnected": ({(-8, -8), (-8, -7), (12, 11), (13, 11)}, False),
    }
    offsets = (
        (1240.0, 634.0),
        (1240.25, 634.25),
        (1240.5, 634.5),
        (1240.75, 634.75),
        (1240.123456789, 634.876543211),
        (-340.625, -211.375),
        (8640.0, 4634.5),
    )
    zooms = (0.10, 0.15, 0.50, 1.00, 3.00)
    orientations = (HexOrientation.FLAT_TOP, HexOrientation.POINTY_TOP)
    cases = [
        (shape, tiles, supported, offset, zoom, orientation, (2480, 1268))
        for shape, (tiles, supported) in shapes.items()
        for offset in offsets
        for zoom in zooms
        for orientation in orientations
    ]
    production_tiles = {(q, r) for q in range(-45, 46) for r in range(-45, 46)}
    cases.extend(
        (
            "production_91x91",
            production_tiles,
            True,
            (1240.123456789, 634.876543211),
            0.15,
            orientation,
            (2480, 1268),
        )
        for orientation in orientations
    )
    viewport_cases = (
        ("map_inside", {(0, 0)}, (160.0, 120.0), 0.5),
        ("viewport_inside", {(q, r) for q in range(-8, 9) for r in range(-8, 9)}, (160.0, 120.0), 1.0),
        ("left_clip", {(0, 0), (1, 0)}, (-10.0, 120.0), 1.0),
        ("right_clip", {(0, 0), (1, 0)}, (310.0, 120.0), 1.0),
        ("top_clip", {(0, 0), (0, 1)}, (160.0, -10.0), 1.0),
        ("bottom_clip", {(0, 0), (0, 1)}, (160.0, 230.0), 1.0),
        ("top_left_clip", {(0, 0)}, (-10.0, -10.0), 1.0),
        ("bottom_right_clip", {(0, 0)}, (330.0, 250.0), 1.0),
        ("fully_outside", {(0, 0), (1, 0)}, (900.0, 700.0), 1.0),
    )
    cases.extend(
        (name, tiles, True, offset, zoom, orientation, (320, 240))
        for name, tiles, offset, zoom in viewport_cases
        for orientation in orientations
    )
    return tuple(cases)


def evaluate_direct_correctness_matrix() -> Dict[str, object]:
    """Exercise broad deterministic geometry, clipping, and topology cases."""
    cases = direct_correctness_cases()

    mismatches = []
    exact = 0
    supported_mismatches = 0
    unsupported_mismatches = 0
    category_counts: Counter[str] = Counter()
    for name, tiles, supported, offset, zoom, orientation, viewport in cases:
        converter = HexConverter(GameConfig.HEX_SIZE, orientation)
        legacy = legacy_presentation_bounds(
            tiles, converter, offset, zoom, viewport
        )
        candidate = candidate_presentation_bounds(
            tiles, converter, offset, zoom, viewport
        )
        if candidate["rect"] == legacy["rect"]:
            exact += 1
            continue
        categories = classify_mismatch(
            visible_tiles=frozenset(tiles),
            legacy_rect=legacy["rect"],
            recomputed_legacy_rect=legacy["rect"],
            recomputed_legacy_unclipped=legacy["unclipped_rect"],
            candidate_rect=candidate["rect"],
            candidate_unclipped=candidate["unclipped_rect"],
            set_changed=False,
        )
        category_counts.update(categories)
        supported_mismatches += int(supported)
        unsupported_mismatches += int(not supported)
        mismatches.append(
            {
                "case": name,
                "supported_production_topology": supported,
                "camera_offset": list(offset),
                "zoom": zoom,
                "orientation": orientation.value,
                "viewport": list(viewport),
                "visible_tiles_count": len(tiles),
                "legacy_rect": _rect_values(legacy["rect"]),
                "candidate_rect": _rect_values(candidate["rect"]),
                "categories": categories,
            }
        )
    return {
        "comparison_count": len(cases),
        "exact_match_count": exact,
        "mismatch_count": len(cases) - exact,
        "supported_production_topology_mismatches": supported_mismatches,
        "unsupported_synthetic_topology_mismatches": unsupported_mismatches,
        "mismatch_category_counts": dict(category_counts),
        "mismatches": mismatches,
    }


__all__ = [
    "PresentationBoundsCollector",
    "candidate_presentation_bounds",
    "canonical_world_bounds",
    "classify_mismatch",
    "direct_correctness_cases",
    "evaluate_direct_correctness_matrix",
    "legacy_presentation_bounds",
]
