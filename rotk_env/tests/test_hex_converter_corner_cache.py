import math

import pytest

from rotk_env.prefabs.config import HexOrientation
from rotk_env.utils import hex_utils
from rotk_env.utils.hex_utils import HexConverter


def _canonical_corners(converter, col, row):
    center_x, center_y = converter.hex_to_pixel(col, row)
    start_angle = -30 if converter.orientation == HexOrientation.POINTY_TOP else 0
    return [
        (
            center_x
            + converter.size * math.cos(math.radians(60 * index + start_angle)),
            center_y
            + converter.size * math.sin(math.radians(60 * index + start_angle)),
        )
        for index in range(6)
    ]


@pytest.mark.parametrize(
    "orientation", [HexOrientation.FLAT_TOP, HexOrientation.POINTY_TOP]
)
@pytest.mark.parametrize("size", [1, 37.5, 50, 113])
@pytest.mark.parametrize("tile", [(-101, -77), (-7, 3), (0, 0), (11, -9)])
def test_cached_offsets_preserve_canonical_corner_values(orientation, size, tile):
    converter = HexConverter(size, orientation)
    assert converter.get_hex_corners(*tile) == _canonical_corners(
        converter, *tile
    )


def test_offset_cache_is_reused_and_tracks_mutable_geometry(monkeypatch):
    calls = {"radians": 0, "cos": 0, "sin": 0}
    originals = {name: getattr(hex_utils.math, name) for name in calls}

    for name, original in originals.items():
        def counted(value, *, _name=name, _original=original):
            calls[_name] += 1
            return _original(value)

        monkeypatch.setattr(hex_utils.math, name, counted)

    converter = HexConverter(50, HexOrientation.FLAT_TOP)
    converter.get_hex_corners(0, 0)
    converter.get_hex_corners(17, -23)
    assert calls == {"radians": 6, "cos": 6, "sin": 6}

    converter.size = 72
    converter.get_hex_corners(17, -23)
    assert calls == {"radians": 12, "cos": 12, "sin": 12}

    converter.orientation = HexOrientation.POINTY_TOP
    converter.get_hex_corners(17, -23)
    assert calls == {"radians": 18, "cos": 18, "sin": 18}
