from rotk_env.utils.hex_utils import HexMath


def test_hex_in_range_has_standard_hex_disk_size_away_from_origin():
    radius = 12
    cells = HexMath.hex_in_range(21, -13, radius)

    assert len(cells) == 1 + 3 * radius * (radius + 1)
    assert (21, -13) in cells
    assert all(HexMath.hex_distance((21, -13), cell) <= radius for cell in cells)


def test_hex_in_range_is_translation_invariant_in_axial_space():
    radius = 5
    origin = HexMath.hex_in_range(0, 0, radius)
    center = (-26, -15)
    translated = HexMath.hex_in_range(*center, radius)

    center_q, center_r = HexMath.offset_to_axial(*center)
    expected = set()
    for cell in origin:
        q, r = HexMath.offset_to_axial(*cell)
        expected.add(HexMath.axial_to_offset(q + center_q, r + center_r))

    assert translated == expected


def test_hex_in_range_radius_zero_returns_only_center():
    assert HexMath.hex_in_range(37, -29, 0) == {(37, -29)}
