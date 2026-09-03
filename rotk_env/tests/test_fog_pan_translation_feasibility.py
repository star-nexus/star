import pygame

from rotk_env.testing.fog_pan_translation_feasibility import (
    compare_surface_translation,
)


def _surface(size=(5, 4)):
    return pygame.Surface(size, pygame.SRCALPHA)


def test_identical_surfaces_have_zero_differences():
    first = _surface()
    first.fill((12, 34, 56, 78))
    second = first.copy()

    result = compare_surface_translation(first, second, 0, 0)

    assert result["exact_pixel_match"] is True
    assert result["differing_pixel_count"] == 0
    assert result["differing_pixel_fraction"] == 0.0
    assert result["difference_bounding_rect"] is None
    assert result["max_per_channel_difference"] == [0, 0, 0, 0]


def test_known_integer_translation_is_an_exact_match():
    previous = _surface()
    previous.set_at((1, 1), (255, 10, 20, 255))
    previous.set_at((2, 2), (30, 200, 40, 127))
    canonical = _surface()
    canonical.set_at((2, 1), (255, 10, 20, 255))
    canonical.set_at((3, 2), (30, 200, 40, 127))

    result = compare_surface_translation(previous, canonical, 1, 0)

    assert result["exact_pixel_match"] is True
    assert result["differing_pixel_count"] == 0


def test_one_pixel_edge_difference_is_reported_exactly():
    previous = _surface()
    canonical = previous.copy()
    canonical.set_at((4, 3), (1, 2, 3, 255))

    result = compare_surface_translation(previous, canonical, 0, 0)

    assert result["exact_pixel_match"] is False
    assert result["differing_pixel_count"] == 1
    assert result["differing_pixel_fraction"] == 1 / 20
    assert result["difference_bounding_rect"] == [4, 3, 1, 1]
    assert result["max_per_channel_difference"] == [1, 2, 3, 255]
    assert result["maximum_channel_difference"] == 255


def test_comparison_does_not_mutate_canonical_surfaces():
    previous = _surface()
    previous.fill((20, 40, 60, 80))
    canonical = _surface()
    canonical.fill((80, 60, 40, 20))
    previous_before = pygame.image.tobytes(previous, "RGBA")
    canonical_before = pygame.image.tobytes(canonical, "RGBA")

    compare_surface_translation(previous, canonical, -1, 1)

    assert pygame.image.tobytes(previous, "RGBA") == previous_before
    assert pygame.image.tobytes(canonical, "RGBA") == canonical_before
