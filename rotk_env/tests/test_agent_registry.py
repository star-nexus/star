"""Cross-faction unit control and multi-agent registry."""

from framework.ecs.world import World
from rotk_env.components import HexPosition, TeamCoordination, Unit, UnitCount, MapData, GameStats
from rotk_env.components.agent_info import AgentInfo, AgentInfoRegistry
from rotk_env.prefabs.config import Faction, UnitType
from rotk_env.systems.llm_action_handler import LLMActionHandler
from rotk_env.systems.llm_system import LLMSystem
from rotk_env.components.settlement_report import SettlementReport
from rotk_env.systems.settlement_report_system import SettlementReportSystem


def _spawn(world: World, faction: Faction, col: int = 0) -> int:
    entity = world.create_entity()
    world.add_component(
        entity, Unit(unit_type=UnitType.INFANTRY, faction=faction, name="u")
    )
    world.add_component(entity, HexPosition(col, 0))
    world.add_component(entity, UnitCount(current_count=100, max_count=100))
    return entity


def _gate(world: World) -> LLMSystem:
    gate = LLMSystem(server_url=None)
    world.add_system(gate)
    return gate


def test_registry_keeps_two_agents_on_the_same_faction():
    registry = AgentInfoRegistry()
    assert registry.register_agent(
        "wei", AgentInfo(provider="a", model_id="m1", agent_id="wei_1")
    )
    assert registry.register_agent(
        "wei", AgentInfo(provider="b", model_id="m2", agent_id="wei_2")
    )
    ids = [info.agent_id for info in registry.get_agents("wei")]
    assert ids == ["wei_1", "wei_2"]
    assert registry.has_agent("wei")
    assert registry.get_agent_info("wei").agent_id == "wei_2"


def test_registry_replaces_same_agent_id():
    registry = AgentInfoRegistry()
    registry.register_agent(
        "wei", AgentInfo(provider="a", model_id="old", agent_id="wei_1")
    )
    registry.register_agent(
        "wei", AgentInfo(provider="a", model_id="new", agent_id="wei_1")
    )
    infos = registry.get_agents("wei")
    assert len(infos) == 1
    assert infos[0].model_id == "new"


def test_shu_agent_cannot_move_wei_unit():
    world = World()
    wei_unit = _spawn(world, Faction.WEI)
    gate = _gate(world)
    denied = gate._check_agent_unit_faction(
        "move", Faction.SHU, {"unit_id": wei_unit}
    )
    assert denied is not None
    assert denied["error_code"] == 2005
    allowed = gate._check_agent_unit_faction(
        "move", Faction.WEI, {"unit_id": wei_unit}
    )
    assert allowed is None


def test_teammate_cannot_move_a_claimed_unit():
    world = World()
    claimed = _spawn(world, Faction.WEI)
    coord = TeamCoordination()
    world.add_singleton_component(coord)
    coord.claim_units("wei_vanguard", [claimed], exclusive=True)
    gate = _gate(world)
    denied = gate._check_unit_ownership(
        "move", "wei_rearguard", {"unit_id": claimed}
    )
    assert denied is not None
    assert denied["error_code"] == 2005
    assert (
        gate._check_unit_ownership("move", "wei_vanguard", {"unit_id": claimed})
        is None
    )


def test_observation_is_not_faction_gated():
    world = World()
    wei_unit = _spawn(world, Faction.WEI)
    gate = _gate(world)
    assert (
        gate._check_agent_unit_faction(
            "unit_observation", Faction.SHU, {"unit_id": wei_unit}
        )
        is None
    )


def test_settlement_lists_every_registered_agent():
    world = World()
    registry = AgentInfoRegistry()
    registry.register_agent(
        "wei", AgentInfo(provider="p1", model_id="m1", agent_id="wei_1")
    )
    registry.register_agent(
        "wei", AgentInfo(provider="p2", model_id="m2", agent_id="wei_2")
    )
    registry.register_agent(
        "shu", AgentInfo(provider="p3", model_id="m3", agent_id="shu_1")
    )
    world.add_singleton_component(registry)

    system = SettlementReportSystem()
    system.initialize(world)
    payload = system._collect_placeholder_data()
    ids = [row["agent_id"] for row in payload["registered_agents"]]
    assert ids == ["wei_1", "wei_2", "shu_1"]
    assert payload["model_info"]["wei"] == "m1 + m2"
    assert payload["model_info"]["shu"] == "m3"
    report = SettlementReport(**payload)
    assert report.model_info["wei"] == "m1 + m2"
    assert [row["agent_id"] for row in report.registered_agents] == ids


def test_faction_state_lists_full_units_with_commandable():
    from rotk_env.components import GameStats

    world = World()
    claimed_a = _spawn(world, Faction.WEI, 0)
    claimed_b = _spawn(world, Faction.WEI, 1)
    unclaimed = _spawn(world, Faction.WEI, 2)
    coord = TeamCoordination()
    world.add_singleton_component(coord)
    coord.claim_units("wei_vanguard", [claimed_a, claimed_b], exclusive=True)
    stats = GameStats()
    stats.agent_id_to_faction["wei_vanguard"] = Faction.WEI
    stats.agent_id_to_faction["wei_rearguard"] = Faction.WEI
    world.add_singleton_component(stats)

    handler = LLMActionHandler(world)
    vanguard = handler.handle_faction_state(
        {"faction": "wei", "agent_id": "wei_vanguard"}
    )
    rear = handler.handle_faction_state(
        {"faction": "wei", "agent_id": "wei_rearguard"}
    )
    solo = handler.handle_faction_state({"faction": "wei"})

    all_ids = {claimed_a, claimed_b, unclaimed}
    assert vanguard["success"] is True
    assert vanguard["total_units"] == 3
    assert rear["total_units"] == 3
    assert solo["total_units"] == 3
    assert {row["unit_id"] for row in vanguard["units"]} == all_ids
    assert {row["unit_id"] for row in rear["units"]} == all_ids
    assert {row["unit_id"] for row in solo["units"]} == all_ids

    by_id = {row["unit_id"]: row for row in rear["units"]}
    assert by_id[claimed_a]["owner"] == "wei_vanguard"
    assert by_id[claimed_a]["commandable"] is False
    assert by_id[unclaimed]["owner"] is None
    assert by_id[unclaimed]["commandable"] is True

    vanguard_by_id = {row["unit_id"]: row for row in vanguard["units"]}
    assert vanguard_by_id[claimed_a]["commandable"] is True
    assert vanguard_by_id[unclaimed]["commandable"] is True

    for row in solo["units"]:
        assert row["commandable"] is True
    for row in vanguard["units"]:
        assert "error" not in row


def test_registered_agent_cannot_census_another_faction():
    """Shu asking for Wei's Units is rejected; visible enemies come from own query."""
    from rotk_env.components import FogOfWar, GameStats, UIState

    world = World()
    claimed = _spawn(world, Faction.WEI, 0)
    free = _spawn(world, Faction.WEI, 1)
    _spawn(world, Faction.SHU, 2)
    coord = TeamCoordination()
    world.add_singleton_component(coord)
    coord.claim_units("wei_vanguard", [claimed], exclusive=True)
    stats = GameStats()
    stats.agent_id_to_faction["shu_1"] = Faction.SHU
    world.add_singleton_component(stats)
    world.add_singleton_component(UIState())
    world.add_singleton_component(FogOfWar(enabled=False))

    handler = LLMActionHandler(world)
    denied = handler.handle_faction_state(
        {"faction": "wei", "agent_id": "shu_1"}
    )
    assert denied["success"] is False
    assert denied["error_code"] == 2005

    own = handler.handle_faction_state(
        {"faction": "shu", "agent_id": "shu_1"}
    )
    visible_ids = {row["unit_id"] for row in own["visible_enemy_units"]}
    assert visible_ids == {claimed, free}
    for row in own["visible_enemy_units"]:
        assert "commandable" not in row
        assert "owner" not in row
        assert "capabilities" not in row


def test_faction_state_vlm_reuses_the_same_json():
    world = World()
    claimed = _spawn(world, Faction.WEI, 0)
    free = _spawn(world, Faction.WEI, 1)
    coord = TeamCoordination()
    world.add_singleton_component(coord)
    coord.claim_units("owner", [claimed], exclusive=True)

    handler = LLMActionHandler(world)
    payload = handler.handle_faction_state_vlm(
        {"faction": "wei", "agent_id": "other"}
    )
    assert payload["success"] is True
    assert payload["total_units"] == 2
    assert {row["unit_id"] for row in payload["units"]} == {claimed, free}
    assert "frame_base64" in payload


def test_register_returns_home_bases():
    world = World()
    world.add_singleton_component(
        MapData(
            width=15,
            height=15,
            home_bases={
                Faction.WEI: (2, 3),
                Faction.SHU: (-2, -4),
            },
        )
    )
    world.add_singleton_component(GameStats())
    result = _gate(world).handle_register_agent_info(
        {
            "faction": "wei",
            "provider": "probe",
            "model_id": "m",
            "base_url": "http://localhost",
            "agent_id": "agent_wei",
        }
    )
    assert result["success"] is True
    assert result["map"]["home_bases"]["wei"] == {
        "col": 2,
        "row": 3,
        "kind": "home_base",
    }
    assert result["map"]["home_bases"]["shu"]["col"] == -2
    assert "基地" in result["map"]["home_bases_meaning"]
    assert "bases" not in result["map"]
    assert result["game_actions"]["names"] == ["move", "attack", "get_faction_state"]
    assert "occupy" not in result["game_actions"]["docs"]
    assert "move" in result["game_actions"]["docs"]
    assert result["map"]["width"] == 15
    assert result["map"]["height"] == 15
    assert result["map"]["col_min"] == -7
    assert result["map"]["col_max"] == 7
    assert result["map"]["row_min"] == -7
    assert result["map"]["row_max"] == 7


def test_map_briefing_uses_tile_keys_for_bounds():
    from rotk_env.components import map_briefing

    sheet = map_briefing(
        MapData(width=15, height=15, tiles={(0, 0): 1, (4, -2): 2})
    )
    assert sheet["col_min"] == 0
    assert sheet["col_max"] == 4
    assert sheet["row_min"] == -2
    assert sheet["row_max"] == 0
