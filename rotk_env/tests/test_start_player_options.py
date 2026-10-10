from rotk_env.components.start_menu import (
    CONTROLLER_HUB,
    CONTROLLER_MOCK_AI,
    CONTROLLER_NONE,
    START_CONTROLLER_OPTIONS,
    START_PLAYER_OPTIONS,
    StartMenuConfig,
    controller_backend_flags,
    start_panel_layout,
)
from rotk_env.prefabs.config import Faction, PLAYER_PRESETS, PlayerType


def test_start_menu_three_faction_topologies_match_cli_presets():
    human_cfg, human_label = START_PLAYER_OPTIONS[2]
    agent_cfg, agent_label = START_PLAYER_OPTIONS[3]

    assert human_cfg == PLAYER_PRESETS["human_vs_two_ai"]
    assert human_cfg == {
        Faction.WEI: PlayerType.HUMAN,
        Faction.SHU: PlayerType.AI,
        Faction.WU: PlayerType.AI,
    }
    assert "Human Wei" in human_label

    assert agent_cfg == PLAYER_PRESETS["three_kingdoms"]
    assert all(player_type == PlayerType.AI for player_type in agent_cfg.values())
    assert "Agent" in agent_label


def test_controller_backend_is_independent_and_defaults_to_cli_like_none():
    config = StartMenuConfig()
    assert config.selected_controller_backend == CONTROLLER_NONE
    assert controller_backend_flags(CONTROLLER_NONE) == (False, False)
    assert controller_backend_flags(CONTROLLER_MOCK_AI) == (True, False)
    assert controller_backend_flags(CONTROLLER_HUB) == (False, True)
    assert [backend for backend, _ in START_CONTROLLER_OPTIONS] == [
        CONTROLLER_NONE,
        CONTROLLER_MOCK_AI,
        CONTROLLER_HUB,
    ]


def test_player_and_controller_stacks_do_not_overlap_scenario_section():
    geom = start_panel_layout(catalog_len=8, screen_width=2480, screen_height=1268)
    options = geom['mode_rects'] + geom['player_rects'] + geom['controller_rects']
    for i, rect in enumerate(options):
        assert rect.bottom <= geom['scenario_y']
        for other in options[i+1:]:
            assert not rect.colliderect(other)
    assert geom['scenario_option_y'] > geom['scenario_y']
    assert geom['scenario_clip'].bottom <= geom['summary_rect'].top
