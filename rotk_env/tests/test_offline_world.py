"""Offline LLMSystem and the shared skirmish World builder. No hub, no window."""

from types import SimpleNamespace

from framework.ecs.world import World
from rotk_env.components import HexPosition, MovementPoints, Unit
from rotk_env.main import resolve_hub_url
from rotk_env.prefabs.config import Faction, GameMode, PlayerType
from rotk_env.prefabs.world_builder import DEFAULT_HUB_URL, build_skirmish_world
from rotk_env.systems.animation_system import AnimationSystem
from rotk_env.systems.input_system import InputHandlingSystem
from rotk_env.systems.llm_system import LLMSystem, NullEnvClient, SyncEnvClient
from rotk_env.utils.hex_utils import HexMath


def test_offline_llmsystem_does_not_construct_a_hub_client(monkeypatch):
    def _boom(*args, **kwargs):
        raise AssertionError("SyncEnvClient must not be constructed when hub_url is None")

    monkeypatch.setattr(
        "rotk_env.systems.llm_system.SyncEnvClient",
        _boom,
    )
    world = World()
    system = LLMSystem()
    world.add_system(system)
    assert isinstance(system.client, NullEnvClient)
    assert system.server_url is None
    world.update(0.0)


def test_online_llmsystem_uses_the_injected_url(monkeypatch):
    constructed = {}

    class _FakeClient:
        def __init__(self, server_url, env_id):
            constructed["server_url"] = server_url
            constructed["env_id"] = env_id
            self.connected_agents = {}

        def add_hub_listener(self, event, callback):
            return None

        def connect(self):
            constructed["connected"] = True
            return True

        def disconnect(self):
            return True

    monkeypatch.setattr("rotk_env.systems.llm_system.SyncEnvClient", _FakeClient)
    world = World()
    system = LLMSystem(server_url=DEFAULT_HUB_URL, env_id="env_test")
    world.add_system(system)
    assert constructed["server_url"] == DEFAULT_HUB_URL
    assert constructed["env_id"] == "env_test"
    assert constructed.get("connected") is True
    assert not isinstance(system.client, NullEnvClient)


def test_resolve_hub_url_axes(monkeypatch):
    monkeypatch.delenv("STAR_HUB_URL", raising=False)
    assert (
        resolve_hub_url(SimpleNamespace(no_hub=True, hub_url="ws://custom")) is None
    )
    assert (
        resolve_hub_url(SimpleNamespace(no_hub=False, hub_url="ws://custom"))
        == "ws://custom"
    )
    assert (
        resolve_hub_url(SimpleNamespace(no_hub=False, hub_url=None)) == DEFAULT_HUB_URL
    )
    monkeypatch.setenv("STAR_HUB_URL", "ws://from-env")
    assert (
        resolve_hub_url(SimpleNamespace(no_hub=False, hub_url=None)) == "ws://from-env"
    )
    monkeypatch.setenv("STAR_HUB_URL", "")
    assert (
        resolve_hub_url(SimpleNamespace(no_hub=False, hub_url=None)) == DEFAULT_HUB_URL
    )


def test_builder_world_is_offline_and_can_move():
    world = build_skirmish_world(
        players={Faction.WEI: PlayerType.AI, Faction.SHU: PlayerType.AI},
        mode=GameMode.REAL_TIME,
        seed=1,
        hub_url=None,
        display="none",
    )
    llm = next(s for s in world.systems if isinstance(s, LLMSystem))
    assert isinstance(llm.client, NullEnvClient)
    assert not isinstance(llm.client, SyncEnvClient)
    assert not any(isinstance(s, InputHandlingSystem) for s in world.systems)
    assert not any(isinstance(s, AnimationSystem) for s in world.systems)

    world.update(0.0)

    unit_id = None
    start = None
    for entity in world.query().with_all(Unit, HexPosition, MovementPoints).entities():
        unit = world.get_component(entity, Unit)
        if unit.faction != Faction.WEI:
            continue
        unit_id = entity
        pos = world.get_component(entity, HexPosition)
        start = (pos.col, pos.row)
        break
    assert unit_id is not None

    dest = None
    result = None
    for col, row in HexMath.hex_neighbors(*start):
        result = llm.action_handler.handle_move_action(
            {"unit_id": unit_id, "target_position": {"col": col, "row": row}}
        )
        if result.get("success"):
            dest = (col, row)
            break
    assert result is not None and result["success"] is True, result
    pos = world.get_component(unit_id, HexPosition)
    assert (pos.col, pos.row) == dest


def test_builder_world_can_construct_a_settlement_report():
    from rotk_env.components import GameState
    from rotk_env.components.settlement_report import SettlementReport
    from rotk_env.systems.settlement_report_system import SettlementReportSystem

    world = build_skirmish_world(
        players={Faction.WEI: PlayerType.AI, Faction.SHU: PlayerType.AI},
        mode=GameMode.REAL_TIME,
        seed=1,
        hub_url=None,
        display="none",
    )
    game_state = world.get_singleton_component(GameState)
    game_state.game_over = True
    game_state.winner = Faction.SHU
    system = next(s for s in world.systems if isinstance(s, SettlementReportSystem))
    report = SettlementReport(**system._collect_comprehensive_statistics())
    assert report.winner_faction == Faction.SHU
    assert "wei" in report.model_info
    assert "shu" in report.model_info

