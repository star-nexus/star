"""Chibi ASCII map covers the board and keeps spawns on land."""

from rotk_env.maps.ascii_map import MAPS_DIR, load_ascii_map
from rotk_env.prefabs.config import GameConfig, TerrainType
from rotk_env.utils.hex_utils import HexConverter


def test_chibi_ascii_is_15x15():
    terrain = load_ascii_map(MAPS_DIR / "chibi.map")
    assert len(terrain) == GameConfig.MAP_WIDTH * GameConfig.MAP_HEIGHT
    half = GameConfig.MAP_WIDTH // 2
    assert (0, 0) in terrain
    assert terrain[(0, 0)] is TerrainType.WATER


def test_chibi_spawns_are_not_water():
    terrain = load_ascii_map(MAPS_DIR / "chibi.map")
    conv = HexConverter()
    cells = list(GameConfig.WEI_FORMATION)
    cells.extend(conv.rotate_180(*c) for c in GameConfig.WEI_FORMATION)
    cells.extend(GameConfig.WU_FORMATION)
    for cell in cells:
        assert terrain[cell] is not TerrainType.WATER, cell
