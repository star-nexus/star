import pytest

from rotk_env.prefabs.config import HexOrientation
from rotk_env.utils import hex_utils
from rotk_env.utils.hex_utils import HexConverter


@pytest.mark.parametrize(
    "orientation", [HexOrientation.FLAT_TOP, HexOrientation.POINTY_TOP]
)
@pytest.mark.parametrize("size", [1, 37.5, 50, 113])
@pytest.mark.parametrize(
    "tile", [(-101, -77), (-7, 3), (0, 0), (11, -9), (2048, 1536)]
)
def test_precomputed_corners_exactly_match_legacy(orientation, size, tile):
    converter = HexConverter(size, orientation)
    converter._set_precomputed_corner_offsets_enabled(False)
    legacy = converter.get_hex_corners(*tile)

    converter._set_precomputed_corner_offsets_enabled(True)
    precomputed = converter.get_hex_corners(*tile)

    assert precomputed == legacy
    assert converter._effective_corner_path() == "precomputed"


def test_precomputed_corner_offsets_are_reused_and_follow_mutable_geometry(
    monkeypatch,
):
    calls = {"radians": 0, "cos": 0, "sin": 0}
    originals = {name: getattr(hex_utils.math, name) for name in calls}

    for name, original in originals.items():
        def counted(value, *, _name=name, _original=original):
            calls[_name] += 1
            return _original(value)

        monkeypatch.setattr(hex_utils.math, name, counted)

    converter = HexConverter(50, HexOrientation.FLAT_TOP)
    first = converter.get_hex_corners(0, 0)
    repeated = converter.get_hex_corners(17, -23)
    assert len(first) == len(repeated) == 6
    assert calls == {"radians": 6, "cos": 6, "sin": 6}

    converter.size = 72
    size_changed = converter.get_hex_corners(17, -23)
    assert calls == {"radians": 12, "cos": 12, "sin": 12}

    converter.orientation = HexOrientation.POINTY_TOP
    orientation_changed = converter.get_hex_corners(17, -23)
    assert calls == {"radians": 18, "cos": 18, "sin": 18}

    converter._set_precomputed_corner_offsets_enabled(False)
    legacy_after_changes = converter.get_hex_corners(17, -23)
    assert orientation_changed == legacy_after_changes
    assert size_changed != orientation_changed


def test_legacy_corner_path_recomputes_offsets_each_call(monkeypatch):
    calls = 0
    original = hex_utils.math.radians

    def counted(value):
        nonlocal calls
        calls += 1
        return original(value)

    monkeypatch.setattr(hex_utils.math, "radians", counted)
    converter = HexConverter(50, HexOrientation.FLAT_TOP)
    converter._set_precomputed_corner_offsets_enabled(False)

    converter.get_hex_corners(0, 0)
    converter.get_hex_corners(1, 1)

    assert calls == 12
    assert converter._effective_corner_path() == "legacy"
