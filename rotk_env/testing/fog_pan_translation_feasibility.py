"""Pixel-exact feasibility checks for translating canonical Fog surfaces."""

from __future__ import annotations

from collections import Counter
from statistics import median
from typing import Dict, Iterable, Optional, Sequence, Tuple

import numpy as np
import pygame

Hex = Tuple[int, int]
Offset = Tuple[float, float]


def _surface_rgba(surface: pygame.Surface) -> np.ndarray:
    width, height = surface.get_size()
    pixels = np.frombuffer(pygame.image.tobytes(surface, "RGBA"), dtype=np.uint8)
    return pixels.reshape((height, width, 4)).copy()


def _translate_rgba(pixels: np.ndarray, dx: int, dy: int) -> np.ndarray:
    translated = np.zeros_like(pixels)
    height, width = pixels.shape[:2]
    source_x = max(0, -dx)
    source_y = max(0, -dy)
    destination_x = max(0, dx)
    destination_y = max(0, dy)
    copy_width = min(width - source_x, width - destination_x)
    copy_height = min(height - source_y, height - destination_y)
    if copy_width > 0 and copy_height > 0:
        translated[
            destination_y : destination_y + copy_height,
            destination_x : destination_x + copy_width,
        ] = pixels[
            source_y : source_y + copy_height,
            source_x : source_x + copy_width,
        ]
    return translated


def _compare_rgba(candidate: np.ndarray, canonical: np.ndarray) -> Dict[str, object]:
    if candidate.shape != canonical.shape:
        raise ValueError("Fog surfaces must have identical dimensions")
    channel_differences = candidate != canonical
    pixel_differences = np.any(channel_differences, axis=2)
    differing_pixels = int(np.count_nonzero(pixel_differences))
    total_pixels = int(pixel_differences.size)
    if differing_pixels:
        ys, xs = np.nonzero(pixel_differences)
        min_x = int(xs.min())
        max_x = int(xs.max())
        min_y = int(ys.min())
        max_y = int(ys.max())
        difference_rect = [
            min_x,
            min_y,
            max_x - min_x + 1,
            max_y - min_y + 1,
        ]
        candidate_differences = candidate[pixel_differences].astype(np.int16)
        canonical_differences = canonical[pixel_differences].astype(np.int16)
        absolute = np.abs(candidate_differences - canonical_differences)
        max_per_channel = [int(value) for value in absolute.max(axis=0)]
    else:
        difference_rect = None
        max_per_channel = [0, 0, 0, 0]
    return {
        "exact_pixel_match": differing_pixels == 0,
        "differing_pixel_count": differing_pixels,
        "differing_pixel_fraction": (
            differing_pixels / total_pixels if total_pixels else 0.0
        ),
        "difference_bounding_rect": difference_rect,
        "max_per_channel_difference": max_per_channel,
        "maximum_per_channel_difference": max_per_channel,
        "maximum_channel_difference": max(max_per_channel),
    }


def compare_surface_translation(
    previous: pygame.Surface,
    canonical: pygame.Surface,
    dx: int,
    dy: int,
) -> Dict[str, object]:
    """Compare one integer translation without mutating either input surface."""
    previous_rgba = _surface_rgba(previous)
    canonical_rgba = _surface_rgba(canonical)
    result = _compare_rgba(_translate_rgba(previous_rgba, int(dx), int(dy)), canonical_rgba)
    result.update(translation_dx=int(dx), translation_dy=int(dy))
    return result


def _rect_values(rect: Optional[pygame.Rect]) -> Optional[list[int]]:
    return list(rect) if rect is not None else None


class FogPanTranslationFeasibility:
    """Compare each canonical camera frame with translated previous pixels."""

    def __init__(self, hex_converter, *, nearby_radius: int = 1):
        self.hex_converter = hex_converter
        self.nearby_radius = max(0, int(nearby_radius))
        self._previous_rgba: Optional[np.ndarray] = None
        self._previous_offset: Optional[Offset] = None
        self._previous_zoom: Optional[float] = None
        self._previous_rect: Optional[pygame.Rect] = None
        self.frames: list[Dict[str, object]] = []

    def seed(
        self,
        surface: pygame.Surface,
        presentation_rect: Optional[pygame.Rect],
        camera_offset: Sequence[float],
        zoom: float,
    ) -> None:
        self._previous_rgba = _surface_rgba(surface)
        self._previous_offset = (float(camera_offset[0]), float(camera_offset[1]))
        self._previous_zoom = float(zoom)
        self._previous_rect = (
            presentation_rect.copy() if presentation_rect is not None else None
        )

    def observe(
        self,
        *,
        surface: pygame.Surface,
        presentation_rect: Optional[pygame.Rect],
        camera_offset: Sequence[float],
        zoom: float,
        visible_tiles: Iterable[Hex],
        view_faction=None,
        orientation=None,
        viewport=None,
    ) -> None:
        canonical = _surface_rgba(surface)
        current_offset = (float(camera_offset[0]), float(camera_offset[1]))
        current_zoom = float(zoom)
        if self._previous_rgba is None or self._previous_offset is None:
            self._previous_rgba = canonical
            self._previous_offset = current_offset
            self._previous_zoom = current_zoom
            self._previous_rect = (
                presentation_rect.copy() if presentation_rect is not None else None
            )
            return

        previous_offset = self._previous_offset
        camera_dx = current_offset[0] - previous_offset[0]
        camera_dy = current_offset[1] - previous_offset[1]
        if camera_dx != 0.0 or camera_dy != 0.0 or current_zoom != self._previous_zoom:
            self.frames.append(
                self._compare_frame(
                    canonical,
                    surface.get_rect(),
                    presentation_rect,
                    previous_offset,
                    current_offset,
                    camera_dx,
                    camera_dy,
                    current_zoom,
                    visible_tiles,
                )
            )

        self._previous_rgba = canonical
        self._previous_offset = current_offset
        self._previous_zoom = current_zoom
        self._previous_rect = (
            presentation_rect.copy() if presentation_rect is not None else None
        )

    def _compare_frame(
        self,
        canonical: np.ndarray,
        viewport_rect: pygame.Rect,
        presentation_rect: Optional[pygame.Rect],
        previous_offset: Offset,
        current_offset: Offset,
        camera_dx: float,
        camera_dy: float,
        zoom: float,
        visible_tiles: Iterable[Hex],
    ) -> Dict[str, object]:
        natural = (int(round(camera_dx)), int(round(camera_dy)))
        rounded_offsets = (
            int(round(current_offset[0])) - int(round(previous_offset[0])),
            int(round(current_offset[1])) - int(round(previous_offset[1])),
        )
        policies = [
            ("round_camera_delta", natural),
            ("rounded_offset_delta", rounded_offsets),
        ]
        nearby = {
            (natural[0] + offset_x, natural[1] + offset_y)
            for offset_x in range(-self.nearby_radius, self.nearby_radius + 1)
            for offset_y in range(-self.nearby_radius, self.nearby_radius + 1)
        }
        candidates = []
        seen = set()
        for policy, translation in policies:
            candidates.append(
                self._candidate_result(
                    policy,
                    translation,
                    canonical,
                    viewport_rect,
                    presentation_rect,
                )
            )
            seen.add(translation)
        for translation in sorted(nearby):
            if translation in seen:
                continue
            candidates.append(
                self._candidate_result(
                    "nearby_round_camera_delta",
                    translation,
                    canonical,
                    viewport_rect,
                    presentation_rect,
                )
            )

        natural_result = candidates[0]
        point_vectors = self._point_translation_vectors(
            visible_tiles, previous_offset, current_offset, zoom
        )
        nearby_exact = [
            candidate
            for candidate in candidates
            if (candidate["translation_dx"], candidate["translation_dy"])
            in nearby
            and candidate["exact_pixel_match"]
        ]
        return {
            "frame_index": len(self.frames) + 1,
            "camera_dx": camera_dx,
            "camera_dy": camera_dy,
            "previous_camera_offset": list(previous_offset),
            "current_camera_offset": list(current_offset),
            "previous_zoom": self._previous_zoom,
            "current_zoom": zoom,
            "candidate_translation_dx": natural[0],
            "candidate_translation_dy": natural[1],
            "natural_translation_policy": "round_camera_delta",
            "exact_pixel_match": natural_result["exact_pixel_match"],
            "differing_pixel_count": natural_result["differing_pixel_count"],
            "differing_pixel_fraction": natural_result["differing_pixel_fraction"],
            "difference_bounding_rect": natural_result[
                "difference_bounding_rect"
            ],
            "max_per_channel_difference": natural_result[
                "max_per_channel_difference"
            ],
            "maximum_channel_difference": natural_result[
                "maximum_channel_difference"
            ],
            "presentation_rect_equal": natural_result[
                "presentation_rect_equal"
            ],
            "presentation_rect_translated_equivalent": natural_result[
                "presentation_rect_translated_equivalent"
            ],
            "canonical_point_translation_uniform": len(point_vectors) == 1,
            "canonical_point_translation_vectors": point_vectors,
            "any_tested_nearby_integer_translation_exact": bool(nearby_exact),
            "candidates": candidates,
        }

    def _candidate_result(
        self,
        policy: str,
        translation: Tuple[int, int],
        canonical: np.ndarray,
        viewport_rect: pygame.Rect,
        presentation_rect: Optional[pygame.Rect],
    ) -> Dict[str, object]:
        assert self._previous_rgba is not None
        dx, dy = translation
        result = _compare_rgba(
            _translate_rgba(self._previous_rgba, dx, dy), canonical
        )
        previous_rect = self._previous_rect
        translated_rect = previous_rect.move(dx, dy) if previous_rect else None
        clipped_rect = (
            translated_rect.clip(viewport_rect) if translated_rect is not None else None
        )
        result.update(
            policy=policy,
            translation_dx=dx,
            translation_dy=dy,
            previous_presentation_rect=_rect_values(previous_rect),
            current_presentation_rect=_rect_values(presentation_rect),
            translated_previous_presentation_rect=_rect_values(translated_rect),
            clipped_translated_previous_presentation_rect=_rect_values(clipped_rect),
            presentation_rect_equal=previous_rect == presentation_rect,
            presentation_rect_translated_equivalent=clipped_rect == presentation_rect,
        )
        return result

    def _point_translation_vectors(
        self,
        visible_tiles: Iterable[Hex],
        previous_offset: Offset,
        current_offset: Offset,
        zoom: float,
    ) -> list[Dict[str, int]]:
        vectors: Counter[Tuple[int, int]] = Counter()
        for q, r in visible_tiles:
            for x, y in self.hex_converter.get_hex_corners(q, r):
                previous_x = int(round(x * zoom + previous_offset[0]))
                previous_y = int(round(y * zoom + previous_offset[1]))
                current_x = int(round(x * zoom + current_offset[0]))
                current_y = int(round(y * zoom + current_offset[1]))
                vectors[(current_x - previous_x, current_y - previous_y)] += 1
        return [
            {"dx": dx, "dy": dy, "count": count}
            for (dx, dy), count in sorted(vectors.items())
        ]

    def result(self) -> Dict[str, object]:
        natural_nonmatches = [
            int(frame["differing_pixel_count"])
            for frame in self.frames
            if not frame["exact_pixel_match"]
        ]
        rule_exact = {
            policy: bool(self.frames)
            and all(
                next(
                    candidate
                    for candidate in frame["candidates"]
                    if candidate["policy"] == policy
                )["exact_pixel_match"]
                for frame in self.frames
            )
            for policy in ("round_camera_delta", "rounded_offset_delta")
        }
        exact_count = sum(bool(frame["exact_pixel_match"]) for frame in self.frames)
        nearby_exact_count = sum(
            bool(frame["any_tested_nearby_integer_translation_exact"])
            for frame in self.frames
        )
        nonuniform_points = any(
            not frame["canonical_point_translation_uniform"] for frame in self.frames
        )
        if any(rule_exact.values()):
            conclusion = "A_rigid_translation_is_pixel_exact"
        elif nonuniform_points:
            conclusion = "B_fractional_camera_phase_changes_pixel_rounding"
        else:
            conclusion = "C_other_unexpected_behavior"
        total = len(self.frames)
        return {
            "total_camera_changing_frames": total,
            "exact_match_frame_count": exact_count,
            "exact_match_ratio": exact_count / total if total else None,
            "non_matching_differing_pixels": {
                "min": min(natural_nonmatches) if natural_nonmatches else None,
                "median": median(natural_nonmatches) if natural_nonmatches else None,
                "max": max(natural_nonmatches) if natural_nonmatches else None,
            },
            "consistent_integer_translation_rule_exact_for_all_frames": rule_exact,
            "any_consistent_integer_translation_rule_exact_for_all_frames": any(
                rule_exact.values()
            ),
            "nearby_exact_frame_count": nearby_exact_count,
            "nearby_exact_ratio": nearby_exact_count / total if total else None,
            "any_tested_nearby_integer_translation_exact": nearby_exact_count > 0,
            "tested_nearby_integer_translation_exact_for_all_frames": (
                bool(total) and nearby_exact_count == total
            ),
            "frames_with_nonuniform_canonical_point_translation": sum(
                not frame["canonical_point_translation_uniform"]
                for frame in self.frames
            ),
            "conclusion": conclusion,
            "frames": self.frames,
        }


__all__ = ["FogPanTranslationFeasibility", "compare_surface_translation"]
