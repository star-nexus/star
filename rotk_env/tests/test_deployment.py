"""Deployment: pixel-space 180° pairing and CLI three_kingdoms all-AI."""

from rotk_env.prefabs.config import Faction, PlayerType, PLAYER_PRESETS, GameConfig
from rotk_env.utils.hex_utils import HexConverter


def test_shu_is_pixel_180_of_wei_blob():
    """Odd-q stagger: Shu must be snapped from pixel 180°, not offset algebra."""
    conv = HexConverter()
    wei = GameConfig.WEI_FORMATION
    shu = [conv.rotate_180(*cell) for cell in wei]
    assert len(set(shu)) == len(wei)
    # Same cells the original hand-placed Shu used.
    assert set(shu) == {(-2, -3), (-1, -4), (-3, -4), (-2, -4), (-1, -5)}
    for cell in wei:
        assert conv.rotate_180(*conv.rotate_180(*cell)) == cell


def test_offset_algebra_does_not_match_screen_shu():
    wei = GameConfig.WEI_FORMATION
    anti = {(-r, -c) for c, r in wei}
    rot_offset = {(-c, -r) for c, r in wei}
    screen = {(-2, -3), (-1, -4), (-3, -4), (-2, -4), (-1, -5)}
    assert anti != screen
    assert rot_offset != screen


def test_wu_formation_is_five_unique():
    assert len(GameConfig.WU_FORMATION) == 5
    assert len(set(GameConfig.WU_FORMATION)) == 5


def test_three_kingdoms_preset_is_all_ai():
    preset = PLAYER_PRESETS["three_kingdoms"]
    assert set(preset) == {Faction.WEI, Faction.SHU, Faction.WU}
    assert all(kind is PlayerType.AI for kind in preset.values())


def test_human_vs_two_ai_keeps_wei_human():
    preset = PLAYER_PRESETS["human_vs_two_ai"]
    assert preset[Faction.WEI] is PlayerType.HUMAN
    assert preset[Faction.SHU] is PlayerType.AI
    assert preset[Faction.WU] is PlayerType.AI


def test_default_unit_mix_is_five():
    assert sum(GameConfig.UNIT_MIX) == 5
    assert GameConfig.UNIT_MIX == [1, 3, 1]
    assert len(GameConfig.WEI_FORMATION) == 5
