"""Rule BOT activation must be explicit, never an agent fallback."""

from rotk_env.prefabs.config import Faction, GameMode, PlayerType
from rotk_env.prefabs.world_builder import build_skirmish_world
from rotk_env.systems.mock_llm_ai_system import MockLLMAISystem


PLAYERS = {
    Faction.WEI: PlayerType.AI,
    Faction.SHU: PlayerType.AI,
    Faction.WU: PlayerType.AI,
}


def _mock_systems(world):
    return [system for system in world.systems if isinstance(system, MockLLMAISystem)]


def test_ai_slots_do_not_mount_rule_bot_by_default():
    """AI-labelled benchmark slots may wait for external agents without moving."""
    world = build_skirmish_world(
        players=PLAYERS,
        mode=GameMode.REAL_TIME,
        seed=1,
        hub_url=None,
        display="none",
    )
    assert _mock_systems(world) == []


def test_rule_bot_is_mounted_only_when_explicitly_enabled():
    world = build_skirmish_world(
        players=PLAYERS,
        mode=GameMode.REAL_TIME,
        seed=1,
        hub_url=None,
        display="none",
        enable_mock_ai=True,
    )
    assert len(_mock_systems(world)) == 1
