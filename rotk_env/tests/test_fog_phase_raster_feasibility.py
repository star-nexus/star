import pygame

from rotk_env.testing.fog_phase_raster_feasibility import (
    FogPhaseRasterFeasibility,
    compare_same_phase_translation,
    diagnostic_phase_key,
)


def _surface(size=(8, 5)):
    return pygame.Surface(size, pygame.SRCALPHA)


def test_identical_same_phase_raster_with_even_translation_is_exact():
    previous = _surface()
    previous.set_at((1, 1), (255, 10, 20, 255))
    previous.set_at((3, 3), (30, 200, 40, 127))
    canonical = _surface()
    canonical.set_at((3, 1), (255, 10, 20, 255))
    canonical.set_at((5, 3), (30, 200, 40, 127))

    result = compare_same_phase_translation(previous, canonical, 2, 0)

    assert result["exact_pixel_match"] is True
    assert result["differing_pixel_count"] == 0
    assert result["interior_difference_count"] == 0


def test_viewport_clipping_difference_is_boundary_only():
    previous = _surface()
    previous.fill((10, 20, 30, 255))
    canonical = previous.copy()

    result = compare_same_phase_translation(previous, canonical, 2, 0)

    assert result["exact_pixel_match"] is False
    assert result["differing_pixel_count"] == 10
    assert result["boundary_difference_count"] == 10
    assert result["interior_difference_count"] == 0
    assert result["differences_boundary_only"] is True
    assert result["difference_bounding_rect"] == [0, 0, 2, 5]


def test_deliberate_interior_difference_is_not_boundary_only():
    previous = _surface()
    previous.fill((10, 20, 30, 255))
    canonical = previous.copy()
    canonical.set_at((4, 2), (200, 20, 30, 255))

    result = compare_same_phase_translation(previous, canonical, 2, 0)

    assert result["interior_difference_count"] == 1
    assert result["differences_boundary_only"] is False


def test_phase_key_preserves_fractional_phase_and_integer_parity():
    common = {
        "zoom": 0.15,
        "orientation": "flat",
        "viewport": (320, 240),
        "view_faction": "wei",
    }
    base = diagnostic_phase_key((100.5, -20.25), **common)
    even_translation = diagnostic_phase_key((102.5, -18.25), **common)
    odd_translation = diagnostic_phase_key((101.5, -20.25), **common)

    assert base == even_translation
    assert base != odd_translation
    assert base != diagnostic_phase_key(
        (100.5, -20.25), **{**common, "zoom": 0.16}
    )
    assert base != diagnostic_phase_key(
        (100.5, -20.25), **{**common, "orientation": "pointy"}
    )
    assert base != diagnostic_phase_key(
        (100.5, -20.25), **{**common, "viewport": (321, 240)}
    )
    assert base != diagnostic_phase_key(
        (100.5, -20.25), **{**common, "view_faction": "shu"}
    )


def test_same_phase_comparison_does_not_mutate_canonical_surfaces():
    previous = _surface()
    previous.fill((20, 40, 60, 80))
    canonical = _surface()
    canonical.fill((80, 60, 40, 20))
    previous_before = pygame.image.tobytes(previous, "RGBA")
    canonical_before = pygame.image.tobytes(canonical, "RGBA")

    compare_same_phase_translation(previous, canonical, 2, 0)

    assert pygame.image.tobytes(previous, "RGBA") == previous_before
    assert pygame.image.tobytes(canonical, "RGBA") == canonical_before


def test_phase_collector_records_exact_hit_and_lag_three_relationship():
    collector = FogPhaseRasterFeasibility()
    initial = _surface()
    initial.set_at((1, 2), (1, 2, 3, 255))
    collector.seed(
        initial,
        pygame.Rect(1, 2, 1, 1),
        (0.5, 0.0),
        1.0,
        orientation="flat",
        viewport=initial.get_size(),
        view_faction="wei",
    )

    for frame_index, offset in enumerate((1.1, 1.7, 2.5), start=1):
        current = _surface()
        if frame_index == 3:
            current.set_at((3, 2), (1, 2, 3, 255))
        collector.observe(
            surface=current,
            presentation_rect=(
                pygame.Rect(3, 2, 1, 1) if frame_index == 3 else None
            ),
            camera_offset=(offset, 0.0),
            zoom=1.0,
            visible_tiles=(),
            view_faction="wei",
            orientation="flat",
            viewport=current.get_size(),
        )

    result = collector.result()
    assert result["total_canonical_camera_frames"] == 3
    assert result["phase_cache_hits"] == 1
    assert result["exact_phase_cache_hits"] == 1
    assert result["lag_3_comparison_count"] == 1
    assert result["lag_3_exact_count"] == 1
    assert result["maximum_simultaneously_retained_phase_surfaces"] == 3
