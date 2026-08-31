"""Deployment: map-file formations and CLI three_kingdoms all-AI."""

from rotk_env.components import formation_center
from rotk_env.maps.map_file import MAPS_DIR, load_map
from rotk_env.prefabs.config import Faction, PlayerType, PLAYER_PRESETS, UnitType
from rotk_env.utils.hex_utils import HexConverter


def _river_split():
    return load_map(MAPS_DIR / "river_split.json")


def test_shu_is_pixel_180_of_wei_blob():
    """Odd-q stagger: Shu cells in the map file are pixel-space 180° of Wei."""
    conv = HexConverter()
    doc = _river_split()
    wei = doc.formations["wei"]
    shu = doc.formations["shu"]
    assert [conv.rotate_180(*cell) for cell in wei] == shu
    for cell in wei:
        assert conv.rotate_180(*conv.rotate_180(*cell)) == cell


def test_offset_algebra_does_not_match_screen_shu():
    wei = _river_split().formations["wei"]
    anti = {(-r, -c) for c, r in wei}
    rot_offset = {(-c, -r) for c, r in wei}
    screen = set(_river_split().formations["shu"])
    assert anti != screen
    assert rot_offset != screen


def test_wu_formation_is_five_unique():
    wu = _river_split().formations["wu"]
    assert len(wu) == 5
    assert len(set(wu)) == 5


def test_three_kingdoms_preset_is_all_ai():
    preset = PLAYER_PRESETS["three_kingdoms"]
    assert set(preset) == {Faction.WEI, Faction.SHU, Faction.WU}
    assert all(kind is PlayerType.AI for kind in preset.values())


def test_human_vs_two_ai_keeps_wei_human():
    preset = PLAYER_PRESETS["human_vs_two_ai"]
    assert preset[Faction.WEI] is PlayerType.HUMAN
    assert preset[Faction.SHU] is PlayerType.AI
    assert preset[Faction.WU] is PlayerType.AI


def test_river_split_unit_mix_lives_in_the_map_file():
    doc = _river_split()
    assert doc.unit_mix == [1, 3, 1]
    wei_types = doc.formation_types["wei"]
    assert wei_types == [
        UnitType.INFANTRY,
        UnitType.ARCHER,
        UnitType.ARCHER,
        UnitType.ARCHER,
        UnitType.CAVALRY,
    ]
    assert len(doc.formations["wei"]) == 5


def test_wei_formation_center_is_inside_the_blob():
    wei = _river_split().formations["wei"]
    center = formation_center(wei)
    assert center == (2, 3)
    assert center in wei
