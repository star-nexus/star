from rotk_env.components.start_menu import START_PLAYER_OPTIONS, start_panel_layout
from rotk_env.prefabs.config import Faction, PLAYER_PRESETS, PlayerType


def test_start_menu_three_faction_modes_match_cli_presets():
    human_cfg, human_label, human_mock_ai = START_PLAYER_OPTIONS[2]
    agent_cfg, agent_label, agent_mock_ai = START_PLAYER_OPTIONS[3]

    assert human_cfg == PLAYER_PRESETS["human_vs_two_ai"]
    assert human_cfg == {
        Faction.WEI: PlayerType.HUMAN,
        Faction.SHU: PlayerType.AI,
        Faction.WU: PlayerType.AI,
    }
    assert "Human Wei" in human_label
    assert human_mock_ai is True

    assert agent_cfg == PLAYER_PRESETS["three_kingdoms"]
    assert all(player_type == PlayerType.AI for player_type in agent_cfg.values())
    assert "AI/Agent" in agent_label
    assert agent_mock_ai is False


def test_player_option_stack_does_not_overlap_scenario_section():
    geom = start_panel_layout(catalog_len=8, screen_width=2480, screen_height=1268)
    last_player_bottom = (
        geom["player_y"]
        + 60
        + (len(START_PLAYER_OPTIONS) - 1) * 45
        + 30
    )

    assert geom["scenario_y"] >= last_player_bottom
    assert geom["scenario_option_y"] > geom["scenario_y"]
