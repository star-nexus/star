"""Directed modulo-two Fog raster phase generalization experiment."""

from __future__ import annotations

import math
from typing import Dict, Optional, Sequence, Tuple

import numpy as np
import pygame

from .fog_pan_translation_feasibility import _rect_values, _surface_rgba
from .fog_phase_raster_feasibility import (
    _compare_same_phase_rgba,
    _rounded_units,
    _stable_token,
)

Offset = Tuple[float, float]
DirectedPhaseKey = Tuple[object, ...]


def directed_phase_key(
    camera_offset: Sequence[float],
    zoom: float,
    orientation,
    viewport: Sequence[int],
    view_faction,
) -> DirectedPhaseKey:
    """Preserve the directed side of each millipixel phase boundary."""
    x_millipixels = math.floor(float(camera_offset[0]) * 1000)
    y_millipixels = math.floor(float(camera_offset[1]) * 1000)
    return (
        x_millipixels % 2000,
        y_millipixels % 2000,
        _rounded_units(zoom, 5),
        _stable_token(orientation),
        int(viewport[0]),
        int(viewport[1]),
        _stable_token(view_faction),
    )


def directed_phase_key_details(key: DirectedPhaseKey) -> Dict[str, object]:
    return {
        "phase_x_millipixels": int(key[0]),
        "phase_y_millipixels": int(key[1]),
        "phase_x_pixels": int(key[0]) / 1000.0,
        "phase_y_pixels": int(key[1]) / 1000.0,
        "zoom_1e5": int(key[2]),
        "orientation": str(key[3]),
        "viewport": [int(key[4]), int(key[5])],
        "view_faction": str(key[6]),
    }


class DirectedPhaseRasterCollector:
    """Compare first and rolling anchors for each directed raster phase."""

    def __init__(self):
        self._first_anchors: Dict[DirectedPhaseKey, Dict[str, object]] = {}
        self._rolling_anchors: Dict[DirectedPhaseKey, Dict[str, object]] = {}
        self._initial_seeded = False
        self._max_phase_surfaces = 0
        self.frames: list[Dict[str, object]] = []
        self.phase_key_sequence: list[Dict[str, object]] = []
        self.first_anchor_comparisons: list[Dict[str, object]] = []
        self.rolling_anchor_comparisons: list[Dict[str, object]] = []

    @property
    def initial_seeded(self) -> bool:
        return self._initial_seeded

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
        canonical = _surface_rgba(surface)
        offset = (float(camera_offset[0]), float(camera_offset[1]))
        zoom_value = float(zoom)
        key = directed_phase_key(
            offset, zoom_value, orientation, viewport, view_faction
        )
        if not self._initial_seeded:
            anchor = self._anchor(
                canonical,
                presentation_rect,
                offset,
                zoom_value,
                frame_index=0,
                phase_key=key,
            )
            self._first_anchors[key] = anchor
            self._rolling_anchors[key] = anchor
            self._initial_seeded = True
            self._max_phase_surfaces = 1
            return

        frame_index = len(self.frames) + 1
        key_details = directed_phase_key_details(key)
        self.phase_key_sequence.append(dict(key_details))
        first_anchor = self._first_anchors.get(key)
        rolling_anchor = self._rolling_anchors.get(key)
        if first_anchor is None:
            cache_status = "miss"
            first_comparison = None
            rolling_comparison = None
            first_anchor = self._anchor(
                canonical,
                presentation_rect,
                offset,
                zoom_value,
                frame_index=frame_index,
                phase_key=key,
            )
            self._first_anchors[key] = first_anchor
        else:
            cache_status = "hit"
            first_comparison = self._compare_anchor(
                first_anchor,
                canonical,
                presentation_rect,
                offset,
                key,
                relation="first_anchor",
                current_frame_index=frame_index,
            )
            rolling_comparison = self._compare_anchor(
                rolling_anchor,
                canonical,
                presentation_rect,
                offset,
                key,
                relation="rolling_anchor",
                current_frame_index=frame_index,
            )
            self.first_anchor_comparisons.append(first_comparison)
            self.rolling_anchor_comparisons.append(rolling_comparison)

        current_anchor = self._anchor(
            canonical,
            presentation_rect,
            offset,
            zoom_value,
            frame_index=frame_index,
            phase_key=key,
        )
        self._rolling_anchors[key] = current_anchor
        self._max_phase_surfaces = max(
            self._max_phase_surfaces, len(self._first_anchors)
        )
        self.frames.append(
            {
                "frame_index": frame_index,
                "camera_offset": list(offset),
                "rounded_camera_offset": [
                    round(offset[0], 3),
                    round(offset[1], 3),
                ],
                "zoom": zoom_value,
                "phase_key": key_details,
                "phase_cache_status": cache_status,
                "first_anchor_comparison": first_comparison,
                "rolling_anchor_comparison": rolling_comparison,
            }
        )

    @staticmethod
    def _anchor(
        pixels: np.ndarray,
        presentation_rect: Optional[pygame.Rect],
        offset: Offset,
        zoom: float,
        *,
        frame_index: int,
        phase_key: DirectedPhaseKey,
    ) -> Dict[str, object]:
        return {
            "pixels": pixels,
            "presentation_rect": (
                presentation_rect.copy() if presentation_rect is not None else None
            ),
            "camera_offset": offset,
            "rounded_camera_offset": (
                round(offset[0], 3),
                round(offset[1], 3),
            ),
            "diagnostic_millipixels": (
                math.floor(offset[0] * 1000),
                math.floor(offset[1] * 1000),
            ),
            "zoom": zoom,
            "frame_index": frame_index,
            "phase_key": phase_key,
        }

    def _compare_anchor(
        self,
        anchor: Dict[str, object],
        canonical: np.ndarray,
        presentation_rect: Optional[pygame.Rect],
        current_offset: Offset,
        phase_key: DirectedPhaseKey,
        *,
        relation: str,
        current_frame_index: int,
    ) -> Dict[str, object]:
        cached_offset = anchor["camera_offset"]
        raw_dx = current_offset[0] - cached_offset[0]
        raw_dy = current_offset[1] - cached_offset[1]
        current_millipixels = (
            math.floor(current_offset[0] * 1000),
            math.floor(current_offset[1] * 1000),
        )
        cached_millipixels = anchor["diagnostic_millipixels"]
        delta_millipixels = (
            current_millipixels[0] - cached_millipixels[0],
            current_millipixels[1] - cached_millipixels[1],
        )
        translation_is_integer = all(
            value % 1000 == 0 for value in delta_millipixels
        )
        translation = (
            delta_millipixels[0] // 1000,
            delta_millipixels[1] // 1000,
        )
        translation_is_even = (
            translation_is_integer
            and translation[0] % 2 == 0
            and translation[1] % 2 == 0
        )
        reusable = translation_is_integer and translation_is_even
        if reusable:
            comparison = _compare_same_phase_rgba(
                anchor["pixels"], canonical, translation[0], translation[1]
            )
        else:
            comparison = {
                "exact_pixel_match": False,
                "differing_pixel_count": None,
                "differing_pixel_fraction": None,
                "difference_bounding_rect": None,
                "max_per_channel_difference": None,
                "maximum_per_channel_difference": None,
                "maximum_channel_difference": None,
                "boundary_difference_count": None,
                "interior_difference_count": None,
                "differences_boundary_only": False,
                "translation_dx": translation[0],
                "translation_dy": translation[1],
            }

        previous_rect = anchor["presentation_rect"]
        viewport_rect = pygame.Rect(0, 0, canonical.shape[1], canonical.shape[0])
        translated_rect = (
            previous_rect.move(*translation) if previous_rect is not None else None
        )
        clipped_rect = (
            translated_rect.clip(viewport_rect) if translated_rect is not None else None
        )
        comparison.update(
            relation=relation,
            reusable=reusable,
            cached_frame_index=int(anchor["frame_index"]),
            current_frame_index=current_frame_index,
            frame_lag=current_frame_index - int(anchor["frame_index"]),
            phase_key=directed_phase_key_details(phase_key),
            cached_phase_key=directed_phase_key_details(anchor["phase_key"]),
            phase_keys_equal=anchor["phase_key"] == phase_key,
            cached_camera_offset=list(cached_offset),
            current_camera_offset=list(current_offset),
            cached_rounded_camera_offset=list(anchor["rounded_camera_offset"]),
            current_rounded_camera_offset=[
                round(current_offset[0], 3),
                round(current_offset[1], 3),
            ],
            cached_diagnostic_millipixels=list(cached_millipixels),
            current_diagnostic_millipixels=list(current_millipixels),
            raw_camera_dx=raw_dx,
            raw_camera_dy=raw_dy,
            translation_dx=translation[0],
            translation_dy=translation[1],
            translation_is_integer=translation_is_integer,
            translation_is_even=translation_is_even,
            cached_presentation_rect=_rect_values(previous_rect),
            current_presentation_rect=_rect_values(presentation_rect),
            translated_cached_presentation_rect=_rect_values(translated_rect),
            clipped_translated_cached_presentation_rect=_rect_values(clipped_rect),
            presentation_rect_translated_equivalent=clipped_rect
            == presentation_rect,
        )
        return comparison

    def result(self) -> Dict[str, object]:
        first = [item for item in self.first_anchor_comparisons if item["reusable"]]
        rolling = [
            item for item in self.rolling_anchor_comparisons if item["reusable"]
        ]
        return {
            "camera_changing_frames": len(self.frames),
            "unique_directed_phase_keys": len(self._first_anchors),
            "phase_cache_first_seen_misses": sum(
                frame["phase_cache_status"] == "miss" for frame in self.frames
            ),
            "phase_cache_hits": len(self.first_anchor_comparisons),
            "first_anchor": self._aggregate(first),
            "rolling_anchor": self._aggregate(rolling),
            "maximum_retained_phase_surfaces": self._max_phase_surfaces,
            "observed_directed_phase_key_sequence": self.phase_key_sequence,
            "frames": self.frames,
        }

    @staticmethod
    def _aggregate(comparisons: list[Dict[str, object]]) -> Dict[str, object]:
        total = len(comparisons)
        exact = sum(bool(item["exact_pixel_match"]) for item in comparisons)
        interior = sum(
            bool(item["interior_difference_count"])
            for item in comparisons
            if not item["exact_pixel_match"]
        )
        boundary_only = sum(
            bool(item["differences_boundary_only"])
            for item in comparisons
            if not item["exact_pixel_match"]
        )
        return {
            "reusable_hits": total,
            "exact_reusable_hits": exact,
            "exact_ratio": exact / total if total else None,
            "interior_failure_count": interior,
            "boundary_only_failure_count": boundary_only,
            "non_exact_failure_count": total - exact,
        }


def aggregate_generalization_results(
    workloads: list[Dict[str, object]],
) -> Dict[str, object]:
    first_total = sum(item["result"]["first_anchor"]["reusable_hits"] for item in workloads)
    first_exact = sum(
        item["result"]["first_anchor"]["exact_reusable_hits"]
        for item in workloads
    )
    rolling_total = sum(
        item["result"]["rolling_anchor"]["reusable_hits"]
        for item in workloads
    )
    rolling_exact = sum(
        item["result"]["rolling_anchor"]["exact_reusable_hits"]
        for item in workloads
    )
    interior = sum(
        item["result"][anchor]["interior_failure_count"]
        for item in workloads
        for anchor in ("first_anchor", "rolling_anchor")
    )
    boundary_only = sum(
        item["result"][anchor]["boundary_only_failure_count"]
        for item in workloads
        for anchor in ("first_anchor", "rolling_anchor")
    )
    total = first_total + rolling_total
    exact = first_exact + rolling_exact
    viable = bool(total) and exact == total and interior == 0
    recommendation = (
        "PHASE_RASTER_REUSE_VIABLE"
        if viable
        else "ABANDON_PHASE_RASTER_REUSE"
    )
    return {
        "workload_count": len(workloads),
        "first_anchor_reusable_comparisons": first_total,
        "first_anchor_exact": first_exact,
        "first_anchor_exact_ratio": first_exact / first_total if first_total else None,
        "rolling_anchor_reusable_comparisons": rolling_total,
        "rolling_anchor_exact": rolling_exact,
        "rolling_anchor_exact_ratio": (
            rolling_exact / rolling_total if rolling_total else None
        ),
        "total_reusable_comparisons": total,
        "total_exact": exact,
        "global_exact_ratio": exact / total if total else None,
        "interior_failure_count": interior,
        "boundary_only_failure_count": boundary_only,
        "any_claimed_reusable_hit_had_interior_mismatch": interior > 0,
        "structural_recommendation": recommendation,
        "next_architecture_if_abandoned": (
            "camera-independent / raster-phase-aware tile geometry caching"
            if not viable
            else None
        ),
    }


__all__ = [
    "DirectedPhaseRasterCollector",
    "aggregate_generalization_results",
    "directed_phase_key",
    "directed_phase_key_details",
]
