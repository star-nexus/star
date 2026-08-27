"""Chibi map file covers the board and keeps spawns on land."""

from rotk_env.maps.map_file import MAPS_DIR, load_map
from rotk_env.prefabs.config import TerrainType


def test_chibi_map_is_15x15():
    doc = load_map(MAPS_DIR / "chibi.json")
    assert doc.width == 15
    assert doc.height == 15
    assert len(doc.terrain) == 225
    assert (0, 0) in doc.terrain
    assert doc.terrain[(0, 0)] is TerrainType.WATER


def test_chibi_formations_are_not_water():
    doc = load_map(MAPS_DIR / "chibi.json")
    for cells in doc.formations.values():
        for cell in cells:
            assert doc.terrain[cell] is not TerrainType.WATER, cell
