"""Correctness-only feasibility checks for same-phase Fog raster reuse."""

from __future__ import annotations

import math
from collections import Counter, deque
from typing import Dict, Iterable, Optional, Sequence, Tuple

import numpy as np
import pygame

from .fog_pan_translation_feasibility import (
    _compare_rgba,
    _rect_values,
    _surface_rgba,
    _translate_rgba,
)

Hex = Tuple[int, int]
Offset = Tuple[float, float]
PhaseKey = Tuple[object, ...]


def _stable_token(value) -> str:
    enum_value = getattr(value, "value", None)
    if enum_value is not None:
        return str(enum_value)
    return str(value)


def _rounded_units(value: float, digits: int) -> int:
    scale = 10**digits
    return int(round(round(float(value), digits) * scale))


def diagnostic_phase_key(
    camera_offset: Sequence[float],
    zoom: float,
    orientation,
    viewport: Sequence[int],
    view_faction,
) -> PhaseKey:
    """Build a stable modulo-two key at the current Fog key resolutions."""
    rounded_x_millipixels = _rounded_units(camera_offset[0], 3)
    rounded_y_millipixels = _rounded_units(camera_offset[1], 3)
    return (
        rounded_x_millipixels % 2000,
        rounded_y_millipixels % 2000,
        _rounded_units(zoom, 5),
        _stable_token(orientation),
        int(viewport[0]),
        int(viewport[1]),
        _stable_token(view_faction),
    )


def phase_key_details(key: PhaseKey) -> Dict[str, object]:
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


def _newly_exposed_edge_mask(
    height: int, width: int, dx: int, dy: int
) -> np.ndarray:
    mask = np.zeros((height, width), dtype=bool)
    if dx > 0:
        mask[:, : min(dx, width)] = True
    elif dx < 0:
        mask[:, max(0, width + dx) :] = True
    if dy > 0:
        mask[: min(dy, height), :] = True
    elif dy < 0:
        mask[max(0, height + dy) :, :] = True
    return mask


def _compare_same_phase_rgba(
    previous: np.ndarray, canonical: np.ndarray, dx: int, dy: int
) -> Dict[str, object]:
    candidate = _translate_rgba(previous, dx, dy)
    result = _compare_rgba(candidate, canonical)
    differences = np.any(candidate != canonical, axis=2)
    boundary = _newly_exposed_edge_mask(
        canonical.shape[0], canonical.shape[1], dx, dy
    )
    boundary_differences = int(np.count_nonzero(differences & boundary))
    interior_differences = int(np.count_nonzero(differences & ~boundary))
    result.update(
        translation_dx=int(dx),
        translation_dy=int(dy),
        boundary_difference_count=boundary_differences,
        interior_difference_count=interior_differences,
        differences_boundary_only=(
            bool(result["differing_pixel_count"]) and interior_differences == 0
        ),
    )
    return result


def compare_same_phase_translation(
    previous: pygame.Surface,
    canonical: pygame.Surface,
    dx: int,
    dy: int,
) -> Dict[str, object]:
    """Compare a translated anchor and classify edge-only differences."""
    return _compare_same_phase_rgba(
        _surface_rgba(previous), _surface_rgba(canonical), int(dx), int(dy)
    )


class FogPhaseRasterFeasibility:
    """Retain canonical phase anchors and verify same-phase raster reuse."""

    def __init__(self):
        self._phase_cache: Dict[PhaseKey, Dict[str, object]] = {}
        self._history = deque(maxlen=3)
        self._last_phase_frame: Dict[PhaseKey, int] = {}
        self._initial_seeded = False
        self._max_phase_surfaces = 0
        self.frames: list[Dict[str, object]] = []
        self.phase_key_sequence: list[Dict[str, object]] = []
        self.phase_cache_hits: list[Dict[str, object]] = []
        self.lag_3_comparisons: list[Dict[str, object]] = []
        self.phase_recurrence_lags: Counter[int] = Counter()

    def seed(
        self,
        surface: pygame.Surface,
        presentation_rect: Optional[pygame.Rect],
        camera_offset: Sequence[float],
        zoom: float,
        *,
        orientation,
        viewport: Sequence[int],
        view_faction,
    ) -> None:
        canonical = _surface_rgba(surface)
        offset = (float(camera_offset[0]), float(camera_offset[1]))
        key = diagnostic_phase_key(
            offset, zoom, orientation, viewport, view_faction
        )
        anchor = self._anchor(
            canonical,
            presentation_rect,
            offset,
            float(zoom),
            frame_index=0,
            phase_key=key,
        )
        self._phase_cache[key] = anchor
        self._history.append(anchor)
        self._last_phase_frame[key] = 0
        self._initial_seeded = True
        self._max_phase_surfaces = 1

    def observe(
        self,
        *,
        surface: pygame.Surface,
        presentation_rect: Optional[pygame.Rect],
        camera_offset: Sequence[float],
        zoom: float,
        visible_tiles: Iterable[Hex],
        view_faction,
        orientation,
        viewport: Sequence[int],
    ) -> None:
        canonical = _surface_rgba(surface)
        offset = (float(camera_offset[0]), float(camera_offset[1]))
        zoom_value = float(zoom)
        frame_index = len(self.frames) + 1
        key = diagnostic_phase_key(
            offset, zoom_value, orientation, viewport, view_faction
        )
        key_details = phase_key_details(key)
        self.phase_key_sequence.append(dict(key_details))

        previous_phase_frame = self._last_phase_frame.get(key)
        if previous_phase_frame is not None:
            self.phase_recurrence_lags[frame_index - previous_phase_frame] += 1
        self._last_phase_frame[key] = frame_index

        cached = self._phase_cache.get(key)
        if cached is None:
            phase_status = "miss"
            phase_comparison = None
            cached = self._anchor(
                canonical,
                presentation_rect,
                offset,
                zoom_value,
                frame_index=frame_index,
                phase_key=key,
            )
            self._phase_cache[key] = cached
            self._max_phase_surfaces = max(
                self._max_phase_surfaces, len(self._phase_cache)
            )
        else:
            phase_status = "hit"
            phase_comparison = self._compare_anchor(
                cached,
                canonical,
                presentation_rect,
                offset,
                key,
                relation="phase_cache",
                current_frame_index=frame_index,
                use_rounded_offsets=True,
            )
            self.phase_cache_hits.append(phase_comparison)

        lag_3 = None
        if len(self._history) == 3:
            lag_3 = self._compare_anchor(
                self._history[0],
                canonical,
                presentation_rect,
                offset,
                key,
                relation="lag_3",
                current_frame_index=frame_index,
                use_rounded_offsets=False,
            )
            self.lag_3_comparisons.append(lag_3)

        current_anchor = self._anchor(
            canonical,
            presentation_rect,
            offset,
            zoom_value,
            frame_index=frame_index,
            phase_key=key,
        )
        self._history.append(current_anchor)
        self.frames.append(
            {
                "frame_index": frame_index,
                "camera_offset": list(offset),
                "zoom": zoom_value,
                "phase_key": key_details,
                "phase_cache_status": phase_status,
                "phase_cache_comparison": phase_comparison,
                "lag_3_comparison": lag_3,
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
        phase_key: PhaseKey,
    ) -> Dict[str, object]:
        return {
            "pixels": pixels,
            "presentation_rect": (
                presentation_rect.copy() if presentation_rect is not None else None
            ),
            "camera_offset": offset,
            "rounded_offset_millipixels": (
                _rounded_units(offset[0], 3),
                _rounded_units(offset[1], 3),
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
        phase_key: PhaseKey,
        *,
        relation: str,
        current_frame_index: int,
        use_rounded_offsets: bool,
    ) -> Dict[str, object]:
        cached_offset = anchor["camera_offset"]
        raw_dx = current_offset[0] - cached_offset[0]
        raw_dy = current_offset[1] - cached_offset[1]
        if use_rounded_offsets:
            cached_units = anchor["rounded_offset_millipixels"]
            current_units = (
                _rounded_units(current_offset[0], 3),
                _rounded_units(current_offset[1], 3),
            )
            delta_units = (
                current_units[0] - cached_units[0],
                current_units[1] - cached_units[1],
            )
            translation_is_integer = all(value % 1000 == 0 for value in delta_units)
            translation = (
                delta_units[0] // 1000,
                delta_units[1] // 1000,
            )
        else:
            translation = (int(round(raw_dx)), int(round(raw_dy)))
            translation_is_integer = math.isclose(
                raw_dx, translation[0], abs_tol=1e-9
            ) and math.isclose(raw_dy, translation[1], abs_tol=1e-9)

        if translation_is_integer:
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
            cached_frame_index=int(anchor["frame_index"]),
            current_frame_index=current_frame_index,
            frame_lag=current_frame_index - int(anchor["frame_index"]),
            cached_camera_offset=list(cached_offset),
            current_camera_offset=list(current_offset),
            raw_camera_dx=raw_dx,
            raw_camera_dy=raw_dy,
            phase_key=phase_key_details(phase_key),
            cached_phase_key=phase_key_details(anchor["phase_key"]),
            phase_keys_equal=anchor["phase_key"] == phase_key,
            translation_is_integer=translation_is_integer,
            translation_is_even=(
                translation_is_integer
                and translation[0] % 2 == 0
                and translation[1] % 2 == 0
            ),
            cached_presentation_rect=_rect_values(previous_rect),
            current_presentation_rect=_rect_values(presentation_rect),
            translated_cached_presentation_rect=_rect_values(translated_rect),
            clipped_translated_cached_presentation_rect=_rect_values(clipped_rect),
            presentation_rect_translated_equivalent=clipped_rect
            == presentation_rect,
        )
        return comparison

    def result(self) -> Dict[str, object]:
        hits = self.phase_cache_hits
        exact_hits = sum(bool(hit["exact_pixel_match"]) for hit in hits)
        failures = [hit for hit in hits if not hit["exact_pixel_match"]]
        miss_frames = [
            int(frame["frame_index"])
            for frame in self.frames
            if frame["phase_cache_status"] == "miss"
        ]
        warmup_end = max(miss_frames, default=0)
        warm_hits = [
            hit for hit in hits if int(hit["current_frame_index"]) > warmup_end
        ]
        warm_exact = sum(bool(hit["exact_pixel_match"]) for hit in warm_hits)
        lag_exact = sum(
            bool(comparison["exact_pixel_match"])
            for comparison in self.lag_3_comparisons
        )
        return {
            "total_canonical_camera_frames": len(self.frames),
            "total_surfaces_observed_including_initial_anchor": (
                len(self.frames) + int(self._initial_seeded)
            ),
            "initial_canonical_anchor_seeded": self._initial_seeded,
            "unique_diagnostic_phase_keys": len(self._phase_cache),
            "phase_cache_first_seen_misses": len(miss_frames),
            "phase_cache_hits": len(hits),
            "exact_phase_cache_hits": exact_hits,
            "exact_phase_cache_hit_ratio": exact_hits / len(hits) if hits else None,
            "phase_cache_warmup_end_frame": warmup_end,
            "phase_cache_hits_after_warmup": len(warm_hits),
            "exact_phase_cache_hits_after_warmup": warm_exact,
            "exact_phase_cache_hit_ratio_after_warmup": (
                warm_exact / len(warm_hits) if warm_hits else None
            ),
            "lag_3_comparison_count": len(self.lag_3_comparisons),
            "lag_3_comparison_count_excluding_initial_anchor": sum(
                int(comparison["cached_frame_index"]) > 0
                for comparison in self.lag_3_comparisons
            ),
            "lag_3_exact_count": lag_exact,
            "lag_3_exact_ratio": (
                lag_exact / len(self.lag_3_comparisons)
                if self.lag_3_comparisons
                else None
            ),
            "any_same_phase_hit_has_interior_differences": any(
                bool(hit["interior_difference_count"]) for hit in failures
            ),
            "all_same_phase_failures_boundary_only": (
                all(bool(hit["differences_boundary_only"]) for hit in failures)
                if failures
                else None
            ),
            "maximum_simultaneously_retained_phase_surfaces": (
                self._max_phase_surfaces
            ),
            "phase_recurrence_lag_counts": {
                str(lag): count
                for lag, count in sorted(self.phase_recurrence_lags.items())
            },
            "observed_phase_key_sequence": self.phase_key_sequence,
            "phase_cache_hit_details": hits,
            "lag_3_comparisons": self.lag_3_comparisons,
            "frames": self.frames,
        }


__all__ = [
    "FogPhaseRasterFeasibility",
    "compare_same_phase_translation",
    "diagnostic_phase_key",
    "phase_key_details",
]
